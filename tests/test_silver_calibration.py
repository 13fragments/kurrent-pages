import hashlib
import json
import pytest

from harness.silver_calibration import (
    load_silver_units,
    score_silver_unit,
    summarize_silver_units,
)


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def silver(tmp_path):
    images, gt, run = (tmp_path / name for name in ("pages", "gt", "run"))
    images.mkdir()
    gt.mkdir()
    page = "dev_fixture"
    (images / f"{page}.jpg").write_bytes(b"synthetic image fixture")
    (gt / f"{page}.txt").write_text("eins zwei drei vier", encoding="utf-8")
    _write(gt / f"{page}.meta.json", {"id": page, "stratum": "fixture"})
    manifest = tmp_path / "manifest.json"
    image_hash = _hash(images / f"{page}.jpg")
    _write(
        manifest,
        {
            "purpose": "Silver development fixture",
            "quarantine": "not benchmark",
            "page_count": 1,
            "pages": {
                page: {
                    "stratum": "fixture",
                    "image_sha256": image_hash,
                    "gt_sha256": _hash(gt / f"{page}.txt"),
                    "meta_sha256": _hash(gt / f"{page}.meta.json"),
                }
            },
        },
    )
    _write(
        run / "run.json",
        {"engines": {"fixture_engine": {}}, "freeze_sha_path": "old/wrong/path"},
    )
    record = run / "outputs" / "fixture_engine" / f"{page}.json"
    _write(
        record,
        {
            "engine": "fixture_engine",
            "page": page,
            "image": f"{page}.jpg",
            "image_sha256": image_hash,
            "text": "eins zwei drei vier fremder inhalt ganz ohne bild",
        },
    )
    return manifest, gt, images, [run]


def test_load_preserves_archive_and_binds_actual_silver(silver):
    run_file = silver[3][0] / "run.json"
    before = run_file.read_bytes()
    units = load_silver_units(*silver)
    assert run_file.read_bytes() == before
    assert units[0]["source_run_sha256"] == hashlib.sha256(before).hexdigest()
    assert units[0]["silver_manifest_sha256"] == _hash(silver[0])
    result = summarize_silver_units([score_silver_unit(units[0])])
    engine = result["engines"]["fixture_engine"]
    assert engine["span_candidates"] == 1
    assert engine["real_output_recall"] is None
    assert result["t3_status"] == "unresolved"
    assert "hypothesis" not in result["source_evidence"][0]


@pytest.mark.parametrize(
    "kind", ["image", "reference", "metadata", "output_hash", "output_page", "coverage"]
)
def test_drift_and_misattribution_fail_closed(silver, kind):
    manifest, gt, images, runs = silver
    record_path = next((runs[0] / "outputs").glob("*/*.json"))
    if kind == "image":
        (images / "dev_fixture.jpg").write_bytes(b"changed")
    elif kind == "reference":
        (gt / "dev_fixture.txt").write_text("changed")
    elif kind == "metadata":
        _write(gt / "dev_fixture.meta.json", {"id": "different"})
    elif kind == "coverage":
        _write(record_path.parent / "dev_extra.json", {})
    else:
        record = json.loads(record_path.read_text())
        record["image_sha256" if kind == "output_hash" else "page"] = "wrong"
        _write(record_path, record)
    with pytest.raises(ValueError):
        load_silver_units(*silver)


def test_duplicate_engine_inputs_are_rejected(silver):
    with pytest.raises(ValueError, match="duplicate"):
        load_silver_units(*silver[:3], silver[3] * 2)


def test_held_out_page_names_cannot_be_silver(silver):
    manifest = json.loads(silver[0].read_text())
    manifest["pages"]["G01"] = manifest["pages"].pop("dev_fixture")
    _write(silver[0], manifest)
    with pytest.raises(ValueError, match="dev-prefixed"):
        load_silver_units(*silver)
