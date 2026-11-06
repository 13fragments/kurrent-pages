import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
import yaml

from harness.gold import load_entities, load_selection, stratum_total_mismatches

REPO = Path(__file__).parents[1]
SCRIPT = REPO / "scripts" / "build_silver_selection.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("build_silver_selection", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _mini_silver(tmp_path: Path):
    """A 2-page silver fixture with manifest hashes that match the on-disk data."""
    gt = tmp_path / "gt"
    gt.mkdir()
    images = tmp_path / "pages"
    images.mkdir()
    manifest_pages = {}
    for page_id, stratum in (("dev_a", "suetterlin"), ("dev_b", "degraded_fraktur")):
        gt_bytes = f"silver transcript {page_id}".encode("utf-8")
        img_bytes = f"fake-jpeg-{page_id}".encode("utf-8")
        meta_bytes = json.dumps(
            {
                "id": page_id,
                "stratum": stratum,
                "confidence": "med",
                "entities": {
                    "persons": ["Anna Example"],
                    "places": ["Solingen"],
                    "dates": ["23. Januar"],
                },
                "notes": "model-generated fixture",
            }
        ).encode("utf-8")
        (gt / f"{page_id}.txt").write_bytes(gt_bytes)
        (images / f"{page_id}.jpg").write_bytes(img_bytes)
        (gt / f"{page_id}.meta.json").write_bytes(meta_bytes)
        manifest_pages[page_id] = {
            "stratum": stratum,
            "image_sha256": _sha(img_bytes),
            "gt_sha256": _sha(gt_bytes),
            "meta_sha256": _sha(meta_bytes),
        }
    manifest_path = tmp_path / "dev_manifest.json"
    manifest_path.write_text(
        json.dumps({"page_count": 2, "pages": manifest_pages}), encoding="utf-8"
    )
    return manifest_path, gt, images


def test_build_silver_selection_matches_harness_schema(tmp_path: Path):
    manifest_path, gt, images = _mini_silver(tmp_path)
    selection_path = tmp_path / "selection.yml"
    entities_dir = tmp_path / "entities"
    _load_script().build_silver_selection(manifest_path, gt, images, selection_path, entities_dir)

    pages = load_selection(selection_path)
    assert [p.id for p in pages] == ["dev_a", "dev_b"]
    assert pages[0].image_name == "dev_a.jpg"
    assert pages[0].primary_stratum == "suetterlin"
    assert stratum_total_mismatches(selection_path) == []

    document = yaml.safe_load(selection_path.read_text(encoding="utf-8"))
    assert "generated_at" not in document  # deterministic output
    assert document["strata_totals"] == {"degraded_fraktur": 1, "suetterlin": 1}
    entities = load_entities(entities_dir, "dev_a")
    assert entities is not None
    assert [(e.type, e.normalized) for e in entities] == [
        ("person", "Anna Example"),
        ("place", "Solingen"),
        ("date", "23. Januar"),
    ]


def test_build_silver_selection_is_deterministic(tmp_path: Path):
    manifest_path, gt, images = _mini_silver(tmp_path)
    mod = _load_script()
    first = tmp_path / "sel1.yml"
    second = tmp_path / "sel2.yml"
    mod.build_silver_selection(manifest_path, gt, images, first, tmp_path / "e1")
    mod.build_silver_selection(manifest_path, gt, images, second, tmp_path / "e2")
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    "drift",
    [
        ("dev_a.txt", "EDITED silver transcript"),
        ("dev_a.jpg", "EDITED image bytes"),
        ("dev_a.meta.json", '{"id": "dev_a", "entities": {"persons": ["Someone Else"]}}'),
    ],
)
def test_build_silver_selection_rejects_drifted_inputs(tmp_path: Path, drift):
    # Any unchecked drift in GT, image, OR meta (entities feed scoring) must fail closed.
    manifest_path, gt, images = _mini_silver(tmp_path)
    name, new_text = drift
    target = (images if name.endswith(".jpg") else gt) / name
    target.write_text(new_text, encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        _load_script().build_silver_selection(
            manifest_path, gt, images, tmp_path / "selection.yml", tmp_path / "entities"
        )
