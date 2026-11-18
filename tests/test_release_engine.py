"""Opt-in engine keys of §10 2026-11-13: `preprocess: furniture_fp_v16` and `loop_policy: run_removal_v1`.

Failure modes, written before the code:
1. An engine without the keys sends other bytes than the frozen file, or its records or scores change.
2. An unknown step or policy runs instead of failing at engine construction.
3. The harness copy of the image step differs from the pinned fp-v16 copy.
4. A page the step leaves alone is re-encoded instead of sent as the original file.
5. A painted page is not recorded (step, boxes, hash of the bytes sent).
6. Run removal differs from the frozen rule R2 (model track `scripts/loop_cut.py`) on some input.
7. Run removal runs on a token-limited output, or the guard on a normally finished one; an engine without the key
   gets run removal; the incomplete flag appears for an engine without the key.
8. The T3 packet text differs from the scored text.
9. For an engine with an output map (§10 2026-11-15), the T3 packet text differs from the scored text: the map
   must come before the loop guard and run removal, as in scoring.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest
from PIL import Image

from harness.engines import create_engine
from harness.engines.base import EngineUnavailable
from harness.engines.image_steps import STEPS
from harness.gold import GoldPage, sha256_file
from harness.run_removal import removed_text

ROOT = Path(__file__).resolve().parent.parent


def _vlm(**extra):
    return create_engine("vlm", {"type": "vlm_openai", "base_url": "https://api.example.test/v1", "model": "m",
                                 "prompt_file": "configs/prompts/vlm_default.txt", "image_only": True, **extra})


def _sent(engine, image, monkeypatch):
    seen = {}

    def fake_post(payload):
        seen["payload"] = payload
        return {"choices": [{"message": {"content": "ok"}}], "usage": {"completion_tokens": 1}}

    monkeypatch.setattr(engine, "_post", fake_post)
    out = engine.transcribe(image)
    url = seen["payload"]["messages"][0]["content"][0]["image_url"]["url"]
    import base64

    return base64.b64decode(url.split(",", 1)[1]), out


def _page_with_footer(path: Path) -> None:
    """A cream leaf on a dark surround with a grey footer band (the MKN layout)."""
    img = Image.new("RGB", (600, 900), (20, 20, 20))
    for y in range(40, 780):
        for x in range(40, 560, 4):
            img.putpixel((x, y), (215, 210, 180))
    leaf = Image.new("RGB", (520, 740), (215, 210, 180))
    img.paste(leaf, (40, 40))
    band = Image.new("RGB", (600, 60), (134, 134, 134))
    img.paste(band, (0, 840))
    img.save(path, quality=95)


def _plain_page(path: Path) -> None:
    Image.new("RGB", (400, 600), (240, 238, 230)).save(path, quality=95)


# 1, 4, 5
def test_engine_without_key_sends_the_file(monkeypatch, tmp_path):
    image = tmp_path / "p.jpg"
    _page_with_footer(image)
    data, out = _sent(_vlm(), image, monkeypatch)
    assert data == image.read_bytes()
    assert "preprocess" not in out.meta


def test_unchanged_page_is_sent_as_the_file(monkeypatch, tmp_path):
    image = tmp_path / "p.jpg"
    _plain_page(image)
    data, out = _sent(_vlm(preprocess="furniture_fp_v16"), image, monkeypatch)
    assert data == image.read_bytes()
    assert out.meta["preprocess"]["boxes"] == []
    assert out.meta["preprocess"]["sent_sha256"] == hashlib.sha256(data).hexdigest()


def test_painted_page_is_recorded(monkeypatch, tmp_path):
    image = tmp_path / "p.jpg"
    _page_with_footer(image)
    data, out = _sent(_vlm(preprocess="furniture_fp_v16"), image, monkeypatch)
    rec = out.meta["preprocess"]
    assert data != image.read_bytes()
    assert rec["step"] == "furniture_fp_v16" and rec["version"] == "fp-v16"
    assert any(box["rule"] == "band_bottom" for box in rec["boxes"])
    assert rec["sent_sha256"] == hashlib.sha256(data).hexdigest()
    with Image.open(io.BytesIO(data)) as sent:
        assert sent.size == (600, 900)
        assert sent.getpixel((300, 880))[0] != 215  # the band area is painted, not leaf


# 2
def test_unknown_step_or_policy_fails_at_construction():
    with pytest.raises(EngineUnavailable):
        _vlm(preprocess="furniture_v0")
    with pytest.raises(EngineUnavailable):
        _vlm(loop_policy="cut_everything")


# 3
def test_furniture_copy_is_pinned():
    spec = STEPS["furniture_fp_v16"]
    assert hashlib.sha256((ROOT / "harness" / spec["module"]).read_bytes()).hexdigest() == spec["sha256"]


# 6: fixtures of the frozen rule R2
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Anfang " + "abcdefghijklmnopqrstuvwxy " * 6 + "Ende", "Anfang Ende"),
        ("Zeile eins\n" + "die gleiche Zeile kommt wieder\n" * 5 + "Schluss", "Zeile eins\nSchluss"),
        ("ohne Wiederholung, nur Text auf der Seite.", None),
        ("abc " * 3, None),  # block shorter than 20 code points
        ("x" * 3 + ("Blockzeichen mit Laenge zwanzig!" * 3), None),  # only 3 copies
    ],
)
def test_run_removal_matches_rule_r2(text, expected):
    assert removed_text(text) == expected


def test_run_removal_normalizes_to_nfc_first():
    decomposed = "über die Brücke gehen wir. "  # ü decomposed in the first copy only
    text = decomposed + "über die Brücke gehen wir. " * 4 + "Ende"
    assert removed_text(text) == "Ende"


# 7, 8
def _scored(tmp_path, config, text, completion_tokens):
    from harness.runner import score_run

    images = tmp_path / "images"
    images.mkdir(parents=True)
    (images / "G01.jpg").write_bytes(b"img")
    page = GoldPage(id="G01", image_name="G01.jpg", strata=("suetterlin",), scored=True)
    image_hash = sha256_file(images / "G01.jpg")
    run_dir = tmp_path / "run"
    out = run_dir / "outputs" / "eng"
    out.mkdir(parents=True)
    (out / "G01.json").write_text(json.dumps({"page": "G01", "text": text, "image_sha256": image_hash,
                                              "meta": {"usage": {"completion_tokens": completion_tokens}}}))
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{image_hash}  G01.jpg\n")
    (run_dir / "run.json").write_text(json.dumps({"freeze_sha_path": str(freeze), "freeze_sha256": sha256_file(freeze),
                                                  "engines": {"eng": {"type": "vlm_openai", "config": config}}}))
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("Anfang Ende")
    return score_run(run_dir, [page], gt, tmp_path / "entities")["eng"]


RUN_TEXT = "Anfang " + "abcdefghijklmnopqrstuvwxy " * 6 + "Ende"


def test_scoring_removes_runs_only_with_the_key(tmp_path):
    keyed = _scored(tmp_path / "a", {"max_tokens": 100, "loop_policy": "run_removal_v1"}, RUN_TEXT, 50)
    plain = _scored(tmp_path / "b", {"max_tokens": 100}, RUN_TEXT, 50)
    assert keyed["loop_policy_pages"] == ["G01"]
    assert keyed["pages"]["G01"]["cer_norm"] == 0.0
    assert "loop_policy_pages" not in plain and "loop_policy" not in plain["pages"]["G01"]
    assert plain["pages"]["G01"]["cer_norm"] > 0


def test_token_limited_output_gets_the_guard_not_run_removal(tmp_path):
    keyed = _scored(tmp_path / "a", {"max_tokens": 100, "loop_policy": "run_removal_v1"}, RUN_TEXT, 100)
    plain = _scored(tmp_path / "b", {"max_tokens": 100}, RUN_TEXT, 100)
    assert keyed["loop_policy_pages"] == []
    assert keyed["pages"]["G01"]["incomplete"] == "repetition"
    assert "incomplete" not in plain["pages"]["G01"]
    assert keyed["pages"]["G01"]["cer_norm"] == plain["pages"]["G01"]["cer_norm"]


def test_output_record_flags_a_token_limited_reply(tmp_path):
    from harness.engines.base import EngineOutput
    from harness.runner import run_engines

    images = tmp_path / "images"
    images.mkdir()
    (images / "G01.jpg").write_bytes(b"img")
    page = GoldPage(id="G01", image_name="G01.jpg", strata=("suetterlin",), scored=True)

    class Capped:
        def __init__(self, config):
            self.name, self.config = "eng", config

        def transcribe(self, image):
            return EngineOutput(text="t", model_id="m", duration_s=0.0, meta={"usage": {"completion_tokens": 100}})

        def describe(self):
            return {"type": "vlm_openai", "config": self.config}

    for config, flagged in (({"max_tokens": 100, "loop_policy": "run_removal_v1"}, True), ({"max_tokens": 100}, False)):
        run_dir = tmp_path / f"run{flagged}"
        run_engines({"eng": Capped(config)}, [page], images, run_dir)
        record = json.loads((run_dir / "outputs" / "eng" / "G01.json").read_text())
        assert (record.get("incomplete") == "repetition") is flagged


def test_t3_packet_holds_the_scored_text(tmp_path):
    from harness.pilot_gold import load_gold_units
    from harness.runner import score_run

    images = tmp_path / "images"
    images.mkdir()
    (images / "G01.jpg").write_bytes(b"img")
    image_hash = sha256_file(images / "G01.jpg")
    selection = tmp_path / "selection.yml"
    selection.write_text("selection:\n  - {id: G01, strata: [suetterlin], primary: suetterlin}\n")
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{image_hash}  G01.jpg\n")
    run_dir = tmp_path / "run"
    out = run_dir / "outputs" / "eng"
    out.mkdir(parents=True)
    (out / "G01.json").write_text(json.dumps({"page": "G01", "text": RUN_TEXT, "image_sha256": image_hash,
                                              "meta": {"usage": {"completion_tokens": 50}}}))
    (run_dir / "run.json").write_text(json.dumps({
        "freeze_sha_path": str(freeze), "freeze_sha256": sha256_file(freeze),
        "selection_sha256": sha256_file(selection),
        "engines": {"eng": {"type": "vlm_openai", "config": {"max_tokens": 100, "loop_policy": "run_removal_v1"}}}}))
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("Anfang Ende")
    from harness.gold import load_selection

    score_run(run_dir, load_selection(selection), gt, tmp_path / "entities")
    units = load_gold_units(run_dir, ["eng"], selection=selection, sha=freeze, images=images, gt_dir=gt)
    assert units[0]["hypothesis"] == "Anfang Ende"  # the run is removed, as in scoring (the hash check binds them)


# 9
def test_t3_packet_holds_the_mapped_scored_text(tmp_path):
    from harness.gold import load_selection
    from harness.output_maps import lighton_marks
    from harness.pilot_gold import load_gold_units
    from harness.runner import score_run

    images = tmp_path / "images"
    images.mkdir()
    (images / "G01.jpg").write_bytes(b"img")
    image_hash = sha256_file(images / "G01.jpg")
    selection = tmp_path / "selection.yml"
    selection.write_text("selection:\n  - {id: G01, strata: [suetterlin], primary: suetterlin}\n")
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{image_hash}  G01.jpg\n")
    run_dir = tmp_path / "run"
    out = run_dir / "outputs" / "eng"
    out.mkdir(parents=True)
    raw = "⟦Anf⟧ang ▨↵" + "abcdefghijklmnopqrstuvwxy " * 6 + "Ende"
    (out / "G01.json").write_text(json.dumps({"page": "G01", "text": raw, "image_sha256": image_hash,
                                              "meta": {"usage": {"completion_tokens": 50}}}))
    config = {"max_tokens": 100, "loop_policy": "run_removal_v1", "output_map": "lighton-marks"}
    (run_dir / "run.json").write_text(json.dumps({
        "freeze_sha_path": str(freeze), "freeze_sha256": sha256_file(freeze),
        "selection_sha256": sha256_file(selection), "engines": {"eng": {"type": "vlm_openai", "config": config}}}))
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("Anfang [unleserlich]\nEnde")
    score_run(run_dir, load_selection(selection), gt, tmp_path / "entities")
    units = load_gold_units(run_dir, ["eng"], selection=selection, sha=freeze, images=images, gt_dir=gt)
    expected = removed_text(lighton_marks(raw))
    assert expected is not None and "⟦" not in expected and "abcdefghijklmnopqrstuvwxy" not in expected
    assert units[0]["hypothesis"] == expected  # mapped, then the run removed, as in scoring
