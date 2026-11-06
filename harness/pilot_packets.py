"""Private coordinator-map and reviewer-packet validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Sequence

from harness.adjudication_schema import ENTITY_LABELS, SPAN_LABELS
from harness.adjudication_validation import (
    _validated_manual_entities,
    _validated_manual_spans,
    normalized_identity,
)
from harness.pilot_data import (
    candidate_spans_from_score,
    entity_candidates_from_score,
    binding_payload_from_map,
    validate_line_breaks,
)
from harness.pilot_types import (
    PACKET_COUNT,
    PILOT_SCHEMA_VERSION,
    REVIEW_SCHEMA_VERSION,
    PilotError,
    digest_value,
    overlap,
    sha256_file,
)


def load_map(pilot_dir: Path) -> dict:
    path = pilot_dir / "coordinator" / "map.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read coordinator map: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != PILOT_SCHEMA_VERSION
    ):
        raise PilotError("coordinator map schema is not recognized")
    stored = value.get("map_sha256")
    payload = {key: item for key, item in value.items() if key != "map_sha256"}
    if stored != digest_value(payload):
        raise PilotError("coordinator map digest mismatch")
    sidecar = path.with_name("map.sha256")
    if not sidecar.is_file() or sidecar.read_text(encoding="utf-8").strip() != stored:
        raise PilotError("coordinator map sidecar digest mismatch")
    units = value.get("units")
    packets = value.get("packets")
    if (
        not isinstance(units, dict)
        or not units
        or not isinstance(packets, dict)
        or len(packets) != PACKET_COUNT
    ):
        raise PilotError("coordinator map is incomplete")
    for unit_id, unit in units.items():
        if not isinstance(unit, dict) or unit.get("binding_sha256") != digest_value(
            binding_payload_from_map(unit_id, unit)
        ):
            raise PilotError(f"coordinator binding is invalid for {unit_id}")
        _validate_map_unit(unit_id, unit)
    return value


def _validate_map_unit(unit_id: str, unit: dict) -> None:
    hypothesis = unit.get("hypothesis_normalized")
    expected_hyp_sha = hashlib.sha256(str(hypothesis).encode("utf-8")).hexdigest()
    if not isinstance(hypothesis, str) or expected_hyp_sha != unit.get(
        "hypothesis_sha256"
    ):
        raise PilotError(f"coordinator hypothesis binding is invalid for {unit_id}")
    image_path = Path(unit.get("image_path", ""))
    if not image_path.is_file() or sha256_file(image_path) != unit.get("image_sha256"):
        raise PilotError(f"coordinator image binding is invalid for {unit_id}")
    candidate_spans_from_score(unit.get("candidate_spans"), hypothesis)
    if "line_breaks" in unit:
        validate_line_breaks(unit["line_breaks"], hypothesis)
    entity_candidates_from_score(unit.get("entity_candidates"), hypothesis)
    score = unit.get("score")
    if (
        not isinstance(score, dict)
        or score.get("hypothesis_sha256") != unit.get("hypothesis_sha256")
        or score.get("image_sha256") != unit.get("image_sha256")
    ):
        raise PilotError(f"coordinator score binding is invalid for {unit_id}")
    source = unit.get("source")
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("engine"), str)
        or not isinstance(source.get("page"), str)
    ):
        raise PilotError(f"coordinator source identity is invalid for {unit_id}")


def load_packets(pilot_dir: Path, map_payload: dict) -> dict[str, dict]:
    result = {}
    for packet_id, metadata in map_payload["packets"].items():
        relative = metadata.get("path") if isinstance(metadata, dict) else None
        if (
            not isinstance(relative, str)
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
        ):
            raise PilotError(f"packet path is invalid: {packet_id}")
        packet_path = pilot_dir / relative
        try:
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PilotError(f"cannot read packet {packet_id}: {exc}") from exc
        if not isinstance(packet, dict) or packet.get("packet_id") != packet_id:
            raise PilotError(f"packet ID mismatch: {packet_id}")
        payload = {key: item for key, item in packet.items() if key != "packet_sha256"}
        if packet.get("packet_sha256") != digest_value(payload) or packet.get(
            "packet_sha256"
        ) != metadata.get("packet_sha256"):
            raise PilotError(f"packet does not match coordinator map: {packet_id}")
        unit_ids = packet.get("unit_ids")
        units = packet.get("units")
        actual_ids = (
            [item.get("unit_id") for item in units if isinstance(item, dict)]
            if isinstance(units, list)
            else []
        )
        if (
            not isinstance(unit_ids, list)
            or not isinstance(units, list)
            or actual_ids != unit_ids
        ):
            raise PilotError(f"packet unit ordering is invalid: {packet_id}")
        if set(unit_ids) != set(map_payload["units"]):
            raise PilotError(f"packet coverage is invalid: {packet_id}")
        for public in units:
            _validate_public_unit(public, packet_id, pilot_dir, map_payload)
        result[packet_id] = packet
    return result


def _validate_public_unit(
    public: object, packet_id: str, pilot_dir: Path, map_payload: dict
) -> None:
    if (
        not isinstance(public, dict)
        or public.get("unit_id") not in map_payload["units"]
    ):
        raise PilotError(f"packet contains an unknown unit: {packet_id}")
    unit_id = public["unit_id"]
    unit = map_payload["units"][unit_id]
    packet_binding = unit.get("packet_bindings", {}).get(packet_id)
    expected = {
        "unit_id": unit_id,
        "binding_sha256": unit["binding_sha256"],
        "image_sha256": unit["image_sha256"],
        "hypothesis_sha256": unit["hypothesis_sha256"],
        "image_file": packet_binding.get("image_file")
        if isinstance(packet_binding, dict)
        else None,
        "hypothesis_normalized": unit["hypothesis_normalized"],
        "silver_reference": unit["reference_normalized"],
        "candidate_spans": unit["candidate_spans"],
        "entity_candidates": unit["entity_candidates"],
    }
    # Pilot v1 packets predate the display-only line breaks.
    if "line_breaks" in unit:
        expected["line_breaks"] = unit["line_breaks"]
    if public != expected:
        raise PilotError(f"packet binding mismatch for {unit_id}")
    image_file = public["image_file"]
    packet_dir = pilot_dir / "packets" / packet_id
    image_path = packet_dir / image_file
    if (
        Path(image_file).is_absolute()
        or ".." in Path(image_file).parts
        or not image_path.is_file()
        or sha256_file(image_path) != unit["image_sha256"]
    ):
        raise PilotError(f"packet image binding is invalid for {unit_id}")


def load_review_documents(
    pilot_dir: Path, annotations: Sequence[Path]
) -> tuple[dict, dict[str, dict], list[dict]]:
    """Load the map, the packets, and at most two independent review exports."""
    map_payload = load_map(pilot_dir)
    packet_index = load_packets(pilot_dir, map_payload)
    if len(annotations) > PACKET_COUNT:
        raise PilotError("at most two independent annotation files are supported")
    documents = [
        load_review_document(Path(path), map_payload, packet_index)
        for path in annotations
    ]
    if len({document["packet_id"] for document in documents}) != len(documents):
        raise PilotError("independent reviewers must use distinct packet exports")
    if len({document["reviewer"].casefold() for document in documents}) != len(
        documents
    ):
        raise PilotError("reviewer IDs must be distinct")
    return map_payload, packet_index, documents


def load_review_document(
    path: Path, map_payload: dict, packet_index: dict[str, dict]
) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read annotations {path}: {exc}") from exc
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != REVIEW_SCHEMA_VERSION
    ):
        raise PilotError(f"{path}: unrecognized review schema")
    if document.get("draft") is True:
        raise PilotError(f"{path}: draft annotations must be completed before import")
    packet_id = document.get("packet_id")
    if (
        packet_id not in packet_index
        or document.get("packet_sha256") != packet_index[packet_id]["packet_sha256"]
    ):
        raise PilotError(f"{path}: packet binding is invalid")
    reviewer = normalized_identity(document.get("reviewer"), f"{path}.reviewer")
    raw_units = document.get("units")
    if isinstance(raw_units, list):
        listed_units = {}
        for index, item in enumerate(raw_units):
            if not isinstance(item, dict):
                raise PilotError(f"{path}: review entry {index} must be an object")
            unit_id = item.get("unit_id")
            if not isinstance(unit_id, str) or not unit_id:
                raise PilotError(f"{path}: review entry {index} must have a unit_id")
            if unit_id in listed_units:
                raise PilotError(f"{path}: duplicate unit ID {unit_id}")
            listed_units[unit_id] = item
        raw_units = listed_units
    if not isinstance(raw_units, dict):
        raise PilotError(f"{path}: units must be an object")
    packet_unit_ids = set(packet_index[packet_id]["unit_ids"])
    if not set(raw_units).issubset(packet_unit_ids):
        raise PilotError(f"{path}: annotations contain unknown units")
    reviews = {}
    for unit_id, raw in raw_units.items():
        if not isinstance(raw, dict):
            raise PilotError(f"{path}: review for {unit_id} must be an object")
        expected = map_payload["units"][unit_id]
        if (
            raw.get("binding_sha256") != expected["binding_sha256"]
            or raw.get("hypothesis_sha256") != expected["hypothesis_sha256"]
            or raw.get("image_sha256") != expected["image_sha256"]
        ):
            raise PilotError(
                f"{path}: exact hypothesis/image binding failed for {unit_id}"
            )
        if raw.get("full_page_reviewed") is not True:
            raise PilotError(f"{path}: full-page audit is incomplete for {unit_id}")
        try:
            candidate_labels = _label_map(
                raw.get("candidate_labels"),
                {item["id"] for item in expected["candidate_spans"]},
                SPAN_LABELS,
                f"{path}:{unit_id}:candidate_labels",
            )
            entity_labels = _label_map(
                raw.get("entity_labels"),
                {item["id"] for item in expected["entity_candidates"]},
                ENTITY_LABELS,
                f"{path}:{unit_id}:entity_labels",
            )
            hypothesis = expected["hypothesis_normalized"]
            added_spans = _validated_manual_spans(
                raw.get("added_spans", []), hypothesis, f"{path}:{unit_id}:added_spans"
            )
            manual_entities = _validated_manual_entities(
                raw.get("manual_entities", []),
                hypothesis,
                f"{path}:{unit_id}:manual_entities",
            )
        except (ValueError, TypeError) as exc:
            raise PilotError(str(exc)) from exc
        if any(
            overlap(span["start"], span["end"], item["start"], item["end"])
            for span in added_spans
            for item in expected["candidate_spans"]
        ):
            raise PilotError(
                f"{path}: manual span duplicates automatic candidate for {unit_id}"
            )
        if any(
            overlap(entity["start"], entity["end"], item["start"], item["end"])
            for entity in manual_entities
            for item in expected["entity_candidates"]
        ):
            raise PilotError(
                f"{path}: manual entity duplicates automatic candidate for {unit_id}"
            )
        reviews[unit_id] = {
            "reviewer": reviewer,
            "full_page_reviewed": True,
            "candidate_labels": candidate_labels,
            "added_spans": added_spans,
            "entity_labels": entity_labels,
            "manual_entities": manual_entities,
        }
    return {
        "path": str(path),
        "packet_id": packet_id,
        "reviewer": reviewer,
        "units": reviews,
    }


def label_map(
    value: object, expected: set[str], labels: frozenset[str], field: str
) -> dict[str, str]:
    if isinstance(value, dict):
        value = [{"candidate_id": key, "label": label} for key, label in value.items()]
    if not isinstance(value, list):
        raise PilotError(f"{field} must label every candidate")
    result = {}
    for index, raw in enumerate(value):
        if (
            not isinstance(raw, dict)
            or raw.get("candidate_id") not in expected
            or raw["candidate_id"] in result
            or raw.get("label") not in labels
        ):
            raise PilotError(f"{field}[{index}] is unknown, repeated, or unlabeled")
        result[str(raw["candidate_id"])] = str(raw["label"])
    if set(result) != expected:
        raise PilotError(
            f"{field} leaves {len(expected - set(result))} candidates unlabeled"
        )
    return result


# Keep the private helper name useful to the forms module without exposing it
# as part of the public packet format.
_label_map = label_map
