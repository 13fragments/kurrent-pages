"""Resolver input validation for the blinded pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from harness.entities import extract_entity_risk_candidates
from harness.pilot import export_pilot, import_annotations
from harness.pilot_types import REVIEW_SCHEMA_VERSION
from harness.trust import score_trust_diagnostics


def _unit(tmp_path: Path) -> dict:
    image = tmp_path / "page.jpg"
    image.write_bytes(b"silver-image")
    hypothesis = "eins zwei drei Berlin 12.03.1900 42 Euro"
    return {
        "engine": "engine-a",
        "page": "dev_demo_0001",
        "stratum": "test",
        "image_path": str(image),
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "reference": "eins zwei drei",
        "hypothesis": hypothesis,
        "source_run": "/private/evals/silver/dev-run",
        "source_record_sha256": "a" * 64,
        "silver_manifest_sha256": "b" * 64,
        "score": {
            **score_trust_diagnostics("eins zwei drei", hypothesis),
            **extract_entity_risk_candidates(hypothesis),
        },
    }


def _reviews(pilot_dir: Path) -> list[Path]:
    paths = []
    for index, packet_path in enumerate(
        sorted((pilot_dir / "packets").glob("*/packet.json"))
    ):
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        units = {}
        for unit in packet["units"]:
            units[unit["unit_id"]] = {
                "binding_sha256": unit["binding_sha256"],
                "image_sha256": unit["image_sha256"],
                "hypothesis_sha256": unit["hypothesis_sha256"],
                "full_page_reviewed": True,
                "candidate_labels": [
                    {"candidate_id": item["id"], "label": "supported"}
                    for item in unit["candidate_spans"]
                ],
                "added_spans": [],
                "entity_labels": [
                    {"candidate_id": item["id"], "label": "supported"}
                    for item in unit["entity_candidates"]
                ],
                "manual_entities": [],
            }
        output = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "reviewer": f"reviewer-{index + 1}",
            "units": units,
        }
        path = pilot_dir.parent / f"review-{index + 1}.json"
        path.write_text(json.dumps(output), encoding="utf-8")
        paths.append(path)
    return paths


@pytest.mark.parametrize(
    ("field", "labels"),
    [
        ("candidate_labels", ("supported", "fluent_fabrication")),
        ("entity_labels", ("supported", "fabricated")),
        ("spans", ("supported", "fluent_fabrication")),
        ("entities", ("supported", "fabricated")),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_conflicting_duplicate_resolver_entries_are_rejected(
    tmp_path: Path, field: str, labels: tuple[str, str], reverse: bool
):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _reviews(pilot_dir)
    map_payload = json.loads(
        (pilot_dir / "coordinator/map.json").read_text(encoding="utf-8")
    )
    unit_id, unit = next(iter(map_payload["units"].items()))
    candidate = (
        unit["candidate_spans"][0]
        if field in {"candidate_labels", "spans"}
        else unit["entity_candidates"][0]
    )
    entries = []
    for label in labels:
        if field in {"spans", "entities"}:
            entries.append(
                {**candidate, "candidate_id": candidate["id"], "label": label}
            )
        else:
            entries.append({"candidate_id": candidate["id"], "label": label})
    if reverse:
        entries.reverse()
    resolution = {
        "schema_version": "fabrication-pilot-resolution-v01",
        "units": {
            unit_id: {
                "resolver": "reviewer-3",
                "candidate_labels": entries if field == "candidate_labels" else [],
                "entity_labels": entries if field == "entity_labels" else [],
                "spans": entries if field == "spans" else [],
                "entities": entries if field == "entities" else [],
                "manual_spans": [],
                "manual_entities": [],
            }
        },
    }
    resolution_path = tmp_path / "resolution.json"
    resolution_path.write_text(json.dumps(resolution), encoding="utf-8")

    result = import_annotations(pilot_dir, reviews, resolutions=resolution_path)

    assert result["status"] == "pending"
    assert result["pending_units"] == [unit_id]
    assert "repeats candidate" in result["units"][unit_id]["reason"]
