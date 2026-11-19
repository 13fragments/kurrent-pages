"""TrOCR line pipeline (§10 2026-11-19): kraken baseline segmentation on the original page, line crops from the
original page in kraken's order, and a TrOCR recognizer run as a subprocess.

Failure modes covered before the code was written: segmentation runs on a binarized page; crops come from a
binarized page or lose colour; the line order changes; a page with no lines scores as a silent empty page; a line
without a reading is dropped instead of failing the page; a recognizer crash passes; missing config fails late;
generation settings are not passed or not recorded."""

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from harness.engines import create_engine
from harness.engines.base import EngineError, EngineUnavailable


def _config(tmp_path, **overrides):
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    config = {
        "type": "trocr_lines",
        "model": "dh-unibe/trocr-kurrent",
        "revision": "abc123",
        "python": str(python),
        "generate": {"num_beams": 4, "max_length": 128},
    }
    config.update(overrides)
    return config


def _page(tmp_path):
    image = tmp_path / "page.png"
    page = Image.new("RGB", (60, 40), (200, 180, 160))
    page.putpixel((5, 5), (10, 20, 30))
    page.save(image)
    return image


def _fake_run(segmentation, texts, calls, returncode=0):
    def fake_run(command, timeout=600):
        calls.append(command)
        if "segment" in command:
            Path(command[3]).write_text(json.dumps(segmentation), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(command, returncode, stdout=json.dumps({"texts": texts}), stderr="boom")

    return fake_run


SEG = {"lines": [
    {"boundary": [[0, 0], [30, 0], [30, 10], [0, 10]]},
    {"boundary": [[0, 20], [60, 20], [60, 40], [0, 40]]},
]}


def test_segments_the_original_page_without_binarizing(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("harness.engines.trocr_lines.run_command", _fake_run(SEG, ["eins", "zwei"], calls))
    image = _page(tmp_path)
    create_engine("t", _config(tmp_path)).transcribe(image)
    assert calls[0][1:3] == ["-i", str(image)]
    assert calls[0][-2:] == ["segment", "-bl"]
    assert not any("binarize" in c for c in calls)


def test_crops_come_from_the_original_page_in_kraken_order(monkeypatch, tmp_path):
    calls, seen = [], {}

    def fake_run(command, timeout=600):
        if "segment" not in command:
            crops = [Path(p) for p in command if p.endswith(".png")]
            seen["sizes"] = [Image.open(c).size for c in crops]
            seen["mode"] = Image.open(crops[0]).mode
            seen["pixel"] = Image.open(crops[0]).getpixel((5, 5))
        return _fake_run(SEG, ["eins", "zwei"], calls)(command, timeout)

    monkeypatch.setattr("harness.engines.trocr_lines.run_command", fake_run)
    out = create_engine("t", _config(tmp_path)).transcribe(_page(tmp_path))
    assert seen["sizes"] == [(30, 10), (60, 20)]
    assert seen["mode"] == "RGB" and seen["pixel"] == (10, 20, 30)
    assert out.text == "eins\nzwei"


def test_page_without_lines_is_an_error(monkeypatch, tmp_path):
    monkeypatch.setattr("harness.engines.trocr_lines.run_command", _fake_run({"lines": []}, [], []))
    with pytest.raises(EngineError, match="no lines"):
        create_engine("t", _config(tmp_path)).transcribe(_page(tmp_path))


def test_missing_line_reading_fails_the_page(monkeypatch, tmp_path):
    monkeypatch.setattr("harness.engines.trocr_lines.run_command", _fake_run(SEG, ["eins"], []))
    with pytest.raises(EngineError, match="2 lines, 1 readings"):
        create_engine("t", _config(tmp_path)).transcribe(_page(tmp_path))


def test_recognizer_failure_fails_the_page(monkeypatch, tmp_path):
    monkeypatch.setattr("harness.engines.trocr_lines.run_command", _fake_run(SEG, ["eins", "zwei"], [], returncode=1))
    with pytest.raises(EngineError, match="recognizer failed"):
        create_engine("t", _config(tmp_path)).transcribe(_page(tmp_path))


def test_missing_config_fails_at_creation(tmp_path):
    for key in ("model", "revision", "python", "generate"):
        config = _config(tmp_path)
        del config[key]
        with pytest.raises(EngineUnavailable):
            create_engine("t", config)
    with pytest.raises(EngineUnavailable, match="python"):
        create_engine("t", _config(tmp_path, python=str(tmp_path / "missing")))


def test_generation_settings_are_passed_and_recorded(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("harness.engines.trocr_lines.run_command", _fake_run(SEG, ["eins", "zwei"], calls))
    monkeypatch.setattr("harness.engines.trocr_lines.command_version", lambda command: "kraken, version 7.1.1")
    engine = create_engine("t", _config(tmp_path, generate={"num_beams": 4, "no_repeat_ngram_size": 3}))
    engine.transcribe(_page(tmp_path))
    predict = calls[1]
    assert json.loads(predict[predict.index("--generate") + 1]) == {"num_beams": 4, "no_repeat_ngram_size": 3}
    assert predict[predict.index("--model") + 1] == "dh-unibe/trocr-kurrent"
    assert predict[predict.index("--revision") + 1] == "abc123"
    described = engine.describe()
    assert described["type"] == "trocr_lines"
    assert described["kraken_version"] == "kraken, version 7.1.1"
    assert described["config"]["generate"] == {"num_beams": 4, "no_repeat_ngram_size": 3}
