"""Blinded pilot packets stay opaque and round-trip through adjudication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from harness import normalization
from harness.adjudication import score_adjudication
from harness.pilot_data import line_starts
from harness.pilot import PilotError, export_pilot, import_annotations, pilot_status
from harness.pilot_types import REVIEW_SCHEMA_VERSION
from harness.trust import score_trust_diagnostics
from harness.entities import extract_entity_risk_candidates


def _unit(
    tmp_path: Path, *, engine: str = "engine-a", page: str = "dev_demo_0001"
) -> dict:
    image = tmp_path / "original-identifying-page-name.jpg"
    image.write_bytes(b"silver-image")
    hypothesis = "eins zwei drei fremder inhalt ohne bild jetzt"
    score = {
        **score_trust_diagnostics("eins zwei drei", hypothesis),
        **extract_entity_risk_candidates(hypothesis),
    }
    return {
        "engine": engine,
        "page": page,
        "stratum": "test",
        "image_path": str(image),
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "reference": "eins zwei drei",
        "hypothesis": hypothesis,
        "source_run": "/private/evals/silver/old-run-id",
        "source_record_sha256": "a" * 64,
        "silver_manifest_sha256": "b" * 64,
        "score": score,
    }


def _packets(pilot_dir: Path) -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted((pilot_dir / "packets").glob("*/packet.json"))
    ]


def _review_documents(
    pilot_dir: Path, *, labels: tuple[str, str] = ("supported", "supported")
) -> list[Path]:
    outputs = []
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
                    {"candidate_id": item["id"], "label": labels[index]}
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
        path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        outputs.append(path)
    return outputs


def test_export_is_deterministic_blinded_and_pending(tmp_path: Path):
    unit = _unit(tmp_path)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first = export_pilot([unit], first_dir, seed=20260906)
    second = export_pilot([unit], second_dir, seed=20260906)
    assert first["status"] == second["status"] == "pending"
    assert first["unit_count"] == 1
    assert [
        p.read_text(encoding="utf-8")
        for p in sorted(first_dir.glob("packets/*/packet.json"))
    ] == [
        p.read_text(encoding="utf-8")
        for p in sorted(second_dir.glob("packets/*/packet.json"))
    ]
    packet_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in first_dir.glob("packets/*/*")
        if path.is_file()
    )
    assert "engine-a" not in packet_text
    assert "old-run-id" not in packet_text
    assert "original-identifying-page-name" not in packet_text
    assert "fab_rate" not in packet_text
    assert "review_candidate_rate" not in packet_text
    assert "falsch sein" in packet_text
    html_text = next(first_dir.glob("packets/*/review.html")).read_text(
        encoding="utf-8"
    )
    assert "Datei für die Abgabe speichern" in html_text
    assert "Steht das so im Scan links?" in html_text
    assert "fluent_fabrication" in html_text
    assert (
        len(
            {
                unit["unit_id"]
                for packet in _packets(first_dir)
                for unit in packet["units"]
            }
        )
        == 1
    )
    assert pilot_status(first_dir)["status"] == "pending"


def test_export_rejects_nonmatching_image_hash_and_overwrite(tmp_path: Path):
    unit = _unit(tmp_path)
    unit["image_sha256"] = "0" * 64
    with pytest.raises(PilotError, match="image SHA-256"):
        export_pilot([unit], tmp_path / "pilot")
    out = tmp_path / "pilot"
    export_pilot([_unit(tmp_path, page="dev_demo_0002")], out)
    with pytest.raises(PilotError, match="not empty"):
        export_pilot([_unit(tmp_path, page="dev_demo_0003")], out)


def test_supported_labels_round_trip_through_existing_scorer(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    annotations = _review_documents(pilot_dir)
    result = import_annotations(pilot_dir, annotations)
    assert result["status"] == "complete"
    form_path = pilot_dir / "coordinator/adjudications/engine-a/dev_demo_0001.yml"
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))
    map_payload = json.loads(
        (pilot_dir / "coordinator/map.json").read_text(encoding="utf-8")
    )
    unit = next(iter(map_payload["units"].values()))
    scored = score_adjudication(
        form,
        engine="engine-a",
        page="dev_demo_0001",
        hyp_norm=unit["hypothesis_normalized"],
        page_score=unit["score"],
    )
    assert scored["adjudication_status"] == "complete"
    assert scored["fab_chars_adj"] == 0
    status = pilot_status(pilot_dir)
    unit_id = next(iter(status["units"]))
    assert status["status"] == "complete"
    assert status["review_count"] == 2
    assert status["complete_units"] == [unit_id]
    assert status["imported_units"] == [unit_id]


def test_import_requires_two_audited_independent_reviews_and_candidates(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    one = import_annotations(pilot_dir, reviews[:1])
    assert one["status"] == "pending"
    assert not list((pilot_dir / "coordinator").glob("adjudications/**/*.yml"))

    incomplete = json.loads(reviews[1].read_text(encoding="utf-8"))
    unit = next(iter(incomplete["units"].values()))
    unit["full_page_reviewed"] = False
    reviews[1].write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(PilotError, match="full-page"):
        import_annotations(pilot_dir, reviews)

    reviews = _review_documents(pilot_dir)
    duplicate = json.loads(reviews[1].read_text(encoding="utf-8"))
    duplicate["reviewer"] = " REVIEWER-1 "
    reviews[1].write_text(json.dumps(duplicate), encoding="utf-8")
    with pytest.raises(PilotError, match="distinct"):
        import_annotations(pilot_dir, reviews)


def test_import_rejects_saved_draft_even_if_complete(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    draft = json.loads(reviews[0].read_text(encoding="utf-8"))
    draft["draft"] = True
    reviews[0].write_text(json.dumps(draft), encoding="utf-8")
    with pytest.raises(PilotError, match="draft annotations"):
        import_annotations(pilot_dir, reviews)


def test_tampering_packet_annotation_or_image_is_rejected(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    packet_path = next((pilot_dir / "packets").glob("*/packet.json"))
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    packet["units"][0]["hypothesis_normalized"] += " changed"
    packet_path.write_text(json.dumps(packet), encoding="utf-8")
    with pytest.raises(PilotError, match="packet"):
        import_annotations(pilot_dir, reviews)

    export_pilot([_unit(tmp_path, page="dev_demo_0002")], tmp_path / "pilot2")
    reviews = _review_documents(tmp_path / "pilot2")
    tampered = json.loads(reviews[0].read_text(encoding="utf-8"))
    tampered["units"][next(iter(tampered["units"]))]["hypothesis_sha256"] = "0" * 64
    reviews[0].write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(PilotError, match="binding"):
        import_annotations(tmp_path / "pilot2", reviews)

    export_pilot([_unit(tmp_path, page="dev_demo_0003")], tmp_path / "pilot3")
    reviews = _review_documents(tmp_path / "pilot3")
    map_payload = json.loads((tmp_path / "pilot3/coordinator/map.json").read_text())
    image = Path(next(iter(map_payload["units"].values()))["image_path"])
    image.write_bytes(b"different silver image")
    with pytest.raises(PilotError, match="image binding"):
        import_annotations(tmp_path / "pilot3", reviews)


def test_disagreement_stays_pending_until_distinct_resolver(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir, labels=("supported", "perception_error"))
    pending = import_annotations(pilot_dir, reviews)
    assert pending["status"] == "pending"
    assert pending["pending_units"]
    template = json.loads(
        (pilot_dir / "coordinator/resolution-template.json").read_text()
    )
    unit_id = next(iter(template["units"]))
    candidate_id = template["units"][unit_id]["candidate_labels"][0]["candidate_id"]
    resolution = {
        "schema_version": "fabrication-pilot-resolution-v01",
        "units": {
            unit_id: {
                "resolver": "reviewer-3",
                "candidate_labels": [
                    {"candidate_id": candidate_id, "label": "supported"}
                ],
                "manual_spans": [],
                "entity_labels": [],
                "manual_entities": [],
            }
        },
    }
    resolution_path = tmp_path / "resolution.json"
    resolution_path.write_text(json.dumps(resolution), encoding="utf-8")
    complete = import_annotations(pilot_dir, reviews, resolutions=resolution_path)
    assert complete["status"] == "complete"
    with pytest.raises(PilotError, match="overwrite"):
        import_annotations(pilot_dir, reviews, resolutions=resolution_path)
    assert (
        import_annotations(
            pilot_dir, reviews, resolutions=resolution_path, allow_existing=True
        )["status"]
        == "complete"
    )
    status = pilot_status(pilot_dir)
    assert status["status"] == "complete"
    assert status["review_count"] == 2
    assert status["units"][unit_id]["resolver"] == "reviewer-3"
    assert status["units"][unit_id]["disagreements"] == 1
    assert pilot_status(pilot_dir, reviews)["status"] == "complete"


def test_status_rejects_tampered_imported_adjudication(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    import_annotations(pilot_dir, reviews)
    form_path = pilot_dir / "coordinator/adjudications/engine-a/dev_demo_0001.yml"
    form = yaml.safe_load(form_path.read_text(encoding="utf-8"))
    form["hypothesis_sha256"] = "0" * 64
    form_path.write_text(yaml.safe_dump(form, sort_keys=False), encoding="utf-8")

    status = pilot_status(pilot_dir)

    unit_id = next(iter(status["units"]))
    assert status["status"] == "pending"
    assert status["review_count"] == 0
    assert status["complete_units"] == []
    assert status["pending_units"] == [unit_id]
    assert unit_id in status["invalid_imports"]


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_list_units_are_rejected_before_overwrite(
    tmp_path: Path, reverse: bool
):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    document = json.loads(reviews[0].read_text(encoding="utf-8"))
    unit_id, review = next(iter(document["units"].items()))
    first = {**review}
    second = {**review}
    first["candidate_labels"] = [dict(item) for item in review["candidate_labels"]]
    second["candidate_labels"] = [dict(item) for item in review["candidate_labels"]]
    first["candidate_labels"][0]["label"] = "supported"
    second["candidate_labels"][0]["label"] = "perception_error"
    entries = [
        {"unit_id": unit_id, **first},
        {"unit_id": unit_id, **second},
    ]
    if reverse:
        entries.reverse()
    document["units"] = entries
    reviews[0].write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PilotError, match="duplicate unit ID"):
        import_annotations(pilot_dir, reviews)


def test_unique_list_units_round_trip(tmp_path: Path):
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path)], pilot_dir)
    reviews = _review_documents(pilot_dir)
    for path in reviews:
        document = json.loads(path.read_text(encoding="utf-8"))
        document["units"] = [
            {"unit_id": unit_id, **review}
            for unit_id, review in document["units"].items()
        ]
        path.write_text(json.dumps(document), encoding="utf-8")

    assert import_annotations(pilot_dir, reviews)["status"] == "complete"


def test_line_breaks_follow_output_lines_through_normalization():
    # Failure modes: a dehyphenated join or a dropped stroke shifts every later
    # break; blank lines or stray spaces add breaks; a mismatch must not invent
    # breaks past the point where the walk lost the text.
    raw = "  Kauf-\nbrief über\n\n 12-\n13 Gulden  \nZeuge"
    normalized = normalization.normalize(raw)
    breaks = line_starts(raw, normalized)
    assert [normalized[start:].split(" ")[0] for start in breaks] == [
        "brief",
        "12",
        "13",
        "Zeuge",
    ]
    assert normalized[breaks[0] - 1] != " "
    # A stroke alone on a line vanishes; of a doubled stroke only one goes.
    raw = "Zins\n⸗\nfrei und t⸗⸗\nA"
    normalized = normalization.normalize(raw)
    assert [normalized[start:] for start in line_starts(raw, normalized)] == [
        "frei und t⸗ A",
        "A",
    ]
    assert line_starts("eins\nzwei", "eins drei") == []
    assert line_starts("eine Zeile", "eine Zeile") == []


def test_export_carries_line_breaks_into_validated_packets(tmp_path: Path):
    unit = _unit(tmp_path)
    unit["hypothesis"] = "eins zwei drei\nfremder inhalt\nohne bild jetzt"
    unit.pop("score")
    pilot_dir = tmp_path / "pilot"
    export_pilot([unit], pilot_dir, seed=20260906)
    packet_units = [packet["units"][0] for packet in _packets(pilot_dir)]
    for public in packet_units:
        text = public["hypothesis_normalized"]
        assert [text[start:].split(" ")[0] for start in public["line_breaks"]] == [
            "fremder",
            "ohne",
        ]
    documents = _review_documents(pilot_dir)
    result = import_annotations(pilot_dir, documents)
    assert result["status"] == "complete"
