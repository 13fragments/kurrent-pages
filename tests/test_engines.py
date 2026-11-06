import pytest

from harness.engines import create_engine
from harness.engines.base import EngineError, EngineUnavailable


def _vlm_config(**overrides):
    config = {
        "type": "vlm_openai",
        "base_url": "https://api.example.test/v1",
        "model": "test-model",
        "prompt_file": "configs/prompts/vlm_default.txt",
    }
    config.update(overrides)
    return config


def test_vlm_check_sends_auth_header(monkeypatch):
    monkeypatch.setenv("TEST_VLM_KEY", "sk-secret")
    engine = create_engine("vlm", _vlm_config(api_key_env="TEST_VLM_KEY"))
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["auth"] = request.get_header("Authorization")

        class Response:
            def read(self):
                return b"{}"

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        return Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    engine.check()
    assert seen["auth"] == "Bearer sk-secret"


def test_vlm_single_attempt_by_default(monkeypatch, tmp_path):
    """Protocol §6: no per-page retries in scored runs — default is ONE POST."""
    import urllib.error

    engine = create_engine("vlm", _vlm_config())
    attempts = []

    def fake_urlopen(request, timeout=None):
        attempts.append(1)
        raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    image = tmp_path / "p.jpg"
    image.write_bytes(b"x")
    with pytest.raises(Exception):
        engine.transcribe(image)
    assert len(attempts) == 1


def test_vlm_sends_image_before_text(monkeypatch, tmp_path):
    engine = create_engine("vlm", _vlm_config())
    seen = {}

    def fake_post(payload):
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(engine, "_post", fake_post)
    image = tmp_path / "p.png"
    image.write_bytes(b"x")
    engine.transcribe(image)

    content = seen["payload"]["messages"][0]["content"]
    assert [part["type"] for part in content] == ["image_url", "text"]


def test_vlm_missing_api_key_env_fails_at_check(monkeypatch):
    monkeypatch.delenv("TEST_VLM_KEY", raising=False)
    engine = create_engine("vlm", _vlm_config(api_key_env="TEST_VLM_KEY"))
    with pytest.raises(EngineUnavailable, match="TEST_VLM_KEY"):
        engine.check()


def test_vlm_missing_config_key_rejected():
    with pytest.raises(EngineUnavailable, match="base_url"):
        create_engine("vlm", _vlm_config(base_url=""))


def test_unknown_engine_type_rejected():
    with pytest.raises(EngineUnavailable, match="unknown type"):
        create_engine("x", {"type": "nonexistent"})


def test_calamari_missing_checkpoint_fails_preflight(tmp_path):
    engine = create_engine(
        "cal", {"type": "calamari", "checkpoint": str(tmp_path / "nope" / "model")}
    )
    with pytest.raises(EngineUnavailable, match="not found on disk"):
        engine.check()


def test_calamari_checkpoint_prefix_accepted(tmp_path):
    (tmp_path / "model.ckpt.json").write_text("{}", encoding="utf-8")
    engine = create_engine("cal", {"type": "calamari", "checkpoint": str(tmp_path / "model")})
    assert engine._checkpoint() == str(tmp_path / "model")


def test_kraken_describe_fingerprints_model_file(monkeypatch, tmp_path):
    import hashlib

    model = tmp_path / "german_kurrent.mlmodel"
    model.write_bytes(b"model-v1")
    engine = create_engine("kr", {"type": "kraken", "model": str(model)})
    monkeypatch.setattr("harness.engines.kraken.command_version", lambda command: "kraken 5")

    description = engine.describe()

    assert description["model_files"] == [
        {"path": str(model), "sha256": hashlib.sha256(b"model-v1").hexdigest()}
    ]


def test_kraken_default_pipeline_binarizes_before_segment(monkeypatch, tmp_path):
    import subprocess
    from pathlib import Path

    model = tmp_path / "german_kurrent.mlmodel"
    model.write_text("model", encoding="utf-8")
    image = tmp_path / "page.jpg"
    image.write_bytes(b"image")
    engine = create_engine("kr", {"type": "kraken", "model": str(model)})
    seen = {}

    def fake_run(command, timeout=600):
        seen["command"] = command
        Path(command[3]).write_text("recognized", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("harness.engines.kraken.run_command", fake_run)

    assert engine.transcribe(image).text == "recognized"
    assert seen["command"][4:8] == ["binarize", "segment", "-bl", "ocr"]


def test_calamari_describe_fingerprints_checkpoint_and_segmenter(monkeypatch, tmp_path):
    import hashlib

    (tmp_path / "model.ckpt.json").write_bytes(b"json")
    (tmp_path / "model.ckpt.h5").write_bytes(b"weights")
    engine = create_engine("cal", {"type": "calamari", "checkpoint": str(tmp_path / "model")})

    def fake_version(command):
        return f"{command[0]} 1.0"

    monkeypatch.setattr("harness.engines.calamari.command_version", fake_version)
    description = engine.describe()

    assert description["version"] == "calamari-predict 1.0"
    assert description["kraken_version"] == "kraken 1.0"
    assert description["checkpoint_files"] == [
        {
            "path": str(tmp_path / "model.ckpt.h5"),
            "sha256": hashlib.sha256(b"weights").hexdigest(),
        },
        {
            "path": str(tmp_path / "model.ckpt.json"),
            "sha256": hashlib.sha256(b"json").hexdigest(),
        },
    ]


def test_calamari_crops_get_empty_gt_sidecars(monkeypatch, tmp_path):
    import json
    import subprocess
    from pathlib import Path

    from PIL import Image

    engine = create_engine("cal", {"type": "calamari", "checkpoint": str(tmp_path / "model")})
    image = tmp_path / "page.png"
    Image.new("L", (40, 40), 255).save(image)
    calls = []

    def fake_run(command, timeout=600):
        calls.append(command)
        if command[-1] == "binarize":
            Image.new("L", (40, 40), 255).save(command[3])
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        seg_path = command[3]
        segmentation = {
            "lines": [
                {"bbox": [0, 0, 20, 20]},
                {"bbox": [20, 20, 40, 40]},
            ]
        }
        Path(seg_path).write_text(
            json.dumps(segmentation),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("harness.engines.calamari.run_command", fake_run)
    crop_dir = tmp_path / "crops"
    crop_dir.mkdir()
    crops = engine._segment_and_crop(image, crop_dir)
    assert len(crops) == 2
    assert calls[0][-1] == "binarize"
    assert Path(calls[1][2]).name == "binarized.png"
    assert calls[1][-2:] == ["segment", "-bl"]
    assert all(crop.with_suffix(".gt.txt").read_text(encoding="utf-8") == "" for crop in crops)


def test_calamari_missing_prediction_file_is_error(monkeypatch, tmp_path):
    import subprocess

    from harness.engines.base import EngineError

    checkpoint = tmp_path / "model.ckpt.json"
    checkpoint.write_text("{}", encoding="utf-8")
    crop = tmp_path / "line.png"
    crop.write_bytes(b"image")
    image = tmp_path / "page.png"
    image.write_bytes(b"image")
    engine = create_engine("cal", {"type": "calamari", "checkpoint": str(checkpoint)})

    monkeypatch.setattr(engine, "_segment_and_crop", lambda _image, _tmp: [crop])
    monkeypatch.setattr(
        "harness.engines.calamari.run_command",
        lambda command, timeout=600: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    with pytest.raises(EngineError, match="missing prediction files"):
        engine.transcribe(image)


def test_tesseract_check_rejects_missing_lang(monkeypatch):
    import subprocess

    engine = create_engine("tess", {"type": "tesseract", "lang": "deu_latf"})

    def fake_run(command, capture_output, text, timeout, check):
        return subprocess.CompletedProcess(command, 0, stdout="List of langs:\neng\nosd\n", stderr="")

    monkeypatch.setattr("harness.engines.tesseract.run_command", lambda c, timeout=600: fake_run(c, True, True, timeout, False))
    with pytest.raises(EngineUnavailable, match="deu_latf"):
        engine.check()


def test_tesseract_broken_tessdata_is_unavailable_not_error(monkeypatch, tmp_path):
    import subprocess

    engine = create_engine("tess", {"type": "tesseract", "lang": "deu_latf"})

    def fake_run(command, timeout=600):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="Failed loading language 'deu_latf'"
        )

    monkeypatch.setattr("harness.engines.tesseract.run_command", fake_run)
    image = tmp_path / "page.jpg"
    image.write_bytes(b"x")
    with pytest.raises(EngineUnavailable, match="language data broken"):
        engine.transcribe(image)


def test_stub_engines_fail_loudly():
    for stub in ("pylaia",):
        engine = create_engine(stub, {"type": stub})
        with pytest.raises(EngineUnavailable, match="not implemented"):
            engine.check()


def test_transkribus_reads_export_and_rejects_missing(tmp_path):
    exports = tmp_path / "exports"
    exports.mkdir()
    (exports / "D1.txt").write_bytes("\ufeffZeile eins\r\nZeile zwei\r\n".encode("utf-8"))
    config = {"type": "transkribus", "model": "Text Titan II", "model_id": 579509,
              "export_dir": str(exports), "credit_cap": 61}
    engine = create_engine("transkribus_text_titan_ii", config)
    engine.check()
    output = engine.transcribe(tmp_path / "D1.jpg")
    assert output.text == "Zeile eins\nZeile zwei\n"
    assert output.model_id == "transkribus:579509"
    with pytest.raises(EngineError, match="no Transkribus export"):
        engine.transcribe(tmp_path / "D2.jpg")


def test_transkribus_unavailable_without_config(tmp_path):
    engine = create_engine("transkribus", {"type": "transkribus"})
    with pytest.raises(EngineUnavailable, match="config missing"):
        engine.check()


def test_vlm_sends_repetition_penalty_only_when_configured(monkeypatch, tmp_path):
    image = tmp_path / "p.png"
    image.write_bytes(b"x")
    for extra, expected in (({}, None), ({"repetition_penalty": 1.1}, 1.1)):
        engine = create_engine("vlm", {**_vlm_config(), **extra})
        seen = {}

        def fake_post(payload, seen=seen):
            seen["payload"] = payload
            return {"choices": [{"message": {"content": "ok"}}]}

        monkeypatch.setattr(engine, "_post", fake_post)
        engine.transcribe(image)
        assert seen["payload"].get("repetition_penalty") == expected


def test_vlm_sends_chat_template_kwargs_when_configured(monkeypatch, tmp_path):
    image = tmp_path / "p.png"
    image.write_bytes(b"x")
    engine = create_engine("vlm", {**_vlm_config(), "chat_template_kwargs": {"enable_thinking": False}})
    seen = {}

    def fake_post(payload):
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}]}

    monkeypatch.setattr(engine, "_post", fake_post)
    engine.transcribe(image)
    assert seen["payload"]["chat_template_kwargs"] == {"enable_thinking": False}
