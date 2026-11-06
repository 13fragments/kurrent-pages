"""Turn two opaque review exports into validated adjudication forms."""

from __future__ import annotations

import json
import re
from pathlib import Path

from harness.adjudication import score_adjudication
from harness.adjudication_schema import (
    ADJUDICATION_SCHEMA_VERSION,
    ENTITY_LABELS,
    SPAN_LABELS,
)
from harness.adjudication_validation import (
    _validated_manual_entities,
    _validated_manual_spans,
)
from harness.pilot_types import (
    RESOLUTION_SCHEMA_VERSION,
    PilotError,
    json_text,
    overlap,
)


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def forms_for_documents(
    map_payload: dict, documents: list[dict], resolution_map: dict
) -> tuple[dict, dict]:
    states = {}
    forms = {}
    for unit_id in sorted(map_payload["units"]):
        if len(documents) < 2:
            states[unit_id] = {
                "status": "pending",
                "reason": "two independent reviews required",
            }
            continue
        first = documents[0]["units"].get(unit_id)
        second = documents[1]["units"].get(unit_id)
        if first is None or second is None:
            states[unit_id] = {
                "status": "pending",
                "reason": "both reviewers must complete this unit",
            }
            continue
        disagreement = review_disagreement(first, second)
        resolution = resolution_map.get(unit_id)
        if disagreement and resolution is None:
            states[unit_id] = {
                "status": "pending",
                "reason": "third resolver required for disagreement",
            }
            continue
        try:
            form = build_form(
                map_payload["units"][unit_id], unit_id, first, second, resolution
            )
            unit = map_payload["units"][unit_id]
            score_adjudication(
                form,
                engine=unit["source"]["engine"],
                page=unit["source"]["page"],
                hyp_norm=unit["hypothesis_normalized"],
                page_score=unit["score"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            states[unit_id] = {"status": "pending", "reason": str(exc)}
            continue
        forms[unit_id] = form
        states[unit_id] = {
            "status": "complete",
            "reason": "validated two-review consensus",
        }
    return states, forms


def review_disagreement(first: dict, second: dict) -> bool:
    return (
        first["candidate_labels"] != second["candidate_labels"]
        or first["entity_labels"] != second["entity_labels"]
        or _canonical(first["added_spans"]) != _canonical(second["added_spans"])
        or _canonical(first["manual_entities"]) != _canonical(second["manual_entities"])
    )


def build_form(
    unit: dict, unit_id: str, first: dict, second: dict, resolution: dict | None
) -> dict:
    if resolution is not None:
        if not isinstance(resolution, dict):
            raise PilotError(f"resolution for {unit_id} must be an object")
        resolution = resolution.get("consensus", resolution)
        if not isinstance(resolution, dict):
            raise PilotError(f"resolution for {unit_id} must be an object")
    resolution_span_labels, resolution_entity_labels = _labels_from_full_claims(
        resolution
    )
    span_labels = consensus_labels(
        first["candidate_labels"],
        second["candidate_labels"],
        _merge_overrides(
            resolution_span_labels,
            resolution.get("candidate_labels") if resolution else None,
            "resolution candidate_labels",
        ),
        SPAN_LABELS,
        f"resolution {unit_id} candidate_labels",
    )
    entity_labels = consensus_labels(
        first["entity_labels"],
        second["entity_labels"],
        _merge_overrides(
            resolution_entity_labels,
            resolution.get("entity_labels") if resolution else None,
            "resolution entity_labels",
        ),
        ENTITY_LABELS,
        f"resolution {unit_id} entity_labels",
    )
    final_spans, final_entities = resolution_claims(unit, resolution)
    if final_spans is None:
        if _canonical(first["added_spans"]) != _canonical(second["added_spans"]):
            raise PilotError("resolution must provide consensus manual spans")
        final_spans = first["added_spans"]
    if final_entities is None:
        if _canonical(first["manual_entities"]) != _canonical(
            second["manual_entities"]
        ):
            raise PilotError("resolution must provide consensus manual entities")
        final_entities = first["manual_entities"]
    return {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "engine": unit["source"]["engine"],
        "page": unit["source"]["page"],
        "hypothesis_sha256": unit["hypothesis_sha256"],
        "image_sha256": unit["image_sha256"],
        "reviews": [_schema_review(first), _schema_review(second)],
        "resolver": resolution.get("resolver") if resolution else None,
        "spans": [
            {
                **candidate,
                "candidate_id": candidate["id"],
                "label": span_labels[candidate["id"]],
            }
            for candidate in unit["candidate_spans"]
        ]
        + [dict(span) for span in final_spans],
        "entities": [
            {
                **candidate,
                "candidate_id": candidate["id"],
                "label": entity_labels[candidate["id"]],
            }
            for candidate in unit["entity_candidates"]
        ],
        "manual_entities": [dict(entity) for entity in final_entities],
    }


def _schema_review(review: dict) -> dict:
    """Use the list-shaped review fields expected by the shared scorer."""
    return {
        "reviewer": review["reviewer"],
        "full_page_reviewed": review["full_page_reviewed"],
        "candidate_labels": [
            {"candidate_id": key, "label": value}
            for key, value in sorted(review["candidate_labels"].items())
        ],
        "added_spans": [dict(item) for item in review["added_spans"]],
        "entity_labels": [
            {"candidate_id": key, "label": value}
            for key, value in sorted(review["entity_labels"].items())
        ],
        "manual_entities": [dict(item) for item in review["manual_entities"]],
    }


def consensus_labels(
    first: dict, second: dict, override: object, labels: frozenset[str], field: str
) -> dict[str, str]:
    overrides = (
        _partial_label_map(override, set(first), labels, field)
        if override is not None
        else {}
    )
    result = {}
    for candidate_id, first_label in first.items():
        second_label = second.get(candidate_id)
        if first_label == second_label:
            result[candidate_id] = first_label
        elif candidate_id in overrides:
            result[candidate_id] = overrides[candidate_id]
        else:
            raise PilotError(f"{field} requires a third resolver")
    return result


def _partial_label_map(
    value: object, expected: set[str], labels: frozenset[str], field: str
) -> dict[str, str]:
    if isinstance(value, dict):
        value = [{"candidate_id": key, "label": label} for key, label in value.items()]
    if not isinstance(value, list):
        raise PilotError(f"{field} must be a list or object")
    result = {}
    for index, item in enumerate(value):
        if (
            not isinstance(item, dict)
            or item.get("candidate_id") not in expected
            or item["candidate_id"] in result
            or item.get("label") not in labels
        ):
            raise PilotError(f"{field}[{index}] is unknown, repeated, or unlabeled")
        result[item["candidate_id"]] = item["label"]
    return result


def _merge_overrides(first: dict, second: object, field: str) -> dict:
    merged = dict(first)
    if isinstance(second, dict):
        merged.update(second)
    elif isinstance(second, list):
        _validate_unique_candidate_ids(second, field)
        for item in second:
            if isinstance(item, dict) and "candidate_id" in item:
                merged[item["candidate_id"]] = item.get("label")
    return merged


def _labels_from_full_claims(resolution: dict | None) -> tuple[dict, dict]:
    if not resolution:
        return {}, {}
    spans = resolution.get("spans")
    entities = resolution.get("entities")
    return (
        _full_claim_label_map(spans, "resolution spans")
        if isinstance(spans, list)
        else {},
        _full_claim_label_map(entities, "resolution entities")
        if isinstance(entities, list)
        else {},
    )


def _full_claim_label_map(value: list, field: str) -> dict:
    _validate_unique_candidate_ids(value, field)
    return {
        item["candidate_id"]: item.get("label")
        for item in value
        if isinstance(item, dict) and item.get("candidate_id") is not None
    }


def _validate_unique_candidate_ids(value: list, field: str) -> None:
    seen = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        candidate_id = item.get("candidate_id")
        if candidate_id is None:
            continue
        try:
            repeated = candidate_id in seen
        except TypeError:
            continue
        if repeated:
            raise PilotError(f"{field}[{index}] repeats candidate {candidate_id}")
        seen.add(candidate_id)


def resolution_claims(
    unit: dict, resolution: dict | None
) -> tuple[list[dict] | None, list[dict] | None]:
    if resolution is None:
        return None, None
    manual_spans = resolution.get("manual_spans")
    manual_entities = resolution.get("manual_entities")
    full_spans = resolution.get("spans")
    if isinstance(full_spans, list):
        manual_spans = [
            item
            for item in full_spans
            if isinstance(item, dict) and item.get("candidate_id") is None
        ]
        _validate_full_automatic_spans(full_spans, unit)
    full_entities = resolution.get("entities")
    if isinstance(full_entities, list):
        manual_entities = [
            item
            for item in full_entities
            if isinstance(item, dict) and item.get("candidate_id") is None
        ]
        _validate_full_automatic_entities(full_entities, unit)
    hypothesis = unit["hypothesis_normalized"]
    if manual_spans is not None:
        try:
            manual_spans = _validated_manual_spans(
                manual_spans, hypothesis, "resolution.manual_spans"
            )
        except (ValueError, TypeError) as exc:
            raise PilotError(str(exc)) from exc
        ranges = [(item["start"], item["end"]) for item in unit["candidate_spans"]]
        if any(
            overlap(item["start"], item["end"], start, end)
            for item in manual_spans
            for start, end in ranges
        ):
            raise PilotError("resolution manual span duplicates automatic candidate")
    if manual_entities is not None:
        try:
            manual_entities = _validated_manual_entities(
                manual_entities, hypothesis, "resolution.manual_entities"
            )
        except (ValueError, TypeError) as exc:
            raise PilotError(str(exc)) from exc
        ranges = [(item["start"], item["end"]) for item in unit["entity_candidates"]]
        if any(
            overlap(item["start"], item["end"], start, end)
            for item in manual_entities
            for start, end in ranges
        ):
            raise PilotError("resolution manual entity duplicates automatic candidate")
    return manual_spans, manual_entities


def _validate_full_automatic_spans(value: list, unit: dict) -> None:
    expected = {item["id"]: item for item in unit["candidate_spans"]}
    for item in value:
        if not isinstance(item, dict) or item.get("candidate_id") is None:
            continue
        candidate = expected.get(item["candidate_id"])
        if candidate is None or (
            item.get("start"),
            item.get("end"),
            item.get("text"),
        ) != (candidate["start"], candidate["end"], candidate["text"]):
            raise PilotError("resolution automatic span does not match candidate")


def _validate_full_automatic_entities(value: list, unit: dict) -> None:
    expected = {item["id"]: item for item in unit["entity_candidates"]}
    for item in value:
        if not isinstance(item, dict) or item.get("candidate_id") is None:
            continue
        candidate = expected.get(item["candidate_id"])
        if candidate is None or any(
            item.get(field) != candidate[field]
            for field in ("start", "end", "text", "kind")
        ):
            raise PilotError("resolution automatic entity does not match candidate")


def load_resolutions(path: Path, map_sha256: str | None = None) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read resolutions {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PilotError("resolution document must be an object")
    # Resolver-page exports name the coordinator map they were built from.
    if map_sha256 is not None and value.get("map_sha256", map_sha256) != map_sha256:
        raise PilotError("resolution document belongs to a different pilot map")
    units = value.get("units")
    if units is None and value.get("schema_version") == RESOLUTION_SCHEMA_VERSION:
        units = {}
    if units is None:
        units = value
    if not isinstance(units, dict):
        raise PilotError("resolutions.units must be an object")
    return units


def write_resolution_template(pilot_dir: Path, map_payload: dict, states: dict) -> None:
    units = {}
    for unit_id, state in states.items():
        if state["status"] == "complete":
            continue
        unit = map_payload["units"][unit_id]
        units[unit_id] = {
            "reason": state["reason"],
            "resolver": None,
            "candidate_labels": [
                {"candidate_id": item["id"], "label": None}
                for item in unit["candidate_spans"]
            ],
            "manual_spans": [],
            "entity_labels": [
                {"candidate_id": item["id"], "label": None}
                for item in unit["entity_candidates"]
            ],
            "manual_entities": [],
        }
    path = pilot_dir / "coordinator" / "resolution-template.json"
    if not path.exists():
        path.write_text(
            json_text({"schema_version": RESOLUTION_SCHEMA_VERSION, "units": units}),
            encoding="utf-8",
        )


def form_path(target_dir: Path, unit: dict) -> Path:
    source = unit.get("source", {})
    engine, page = source.get("engine"), source.get("page")
    if (
        not isinstance(engine, str)
        or not isinstance(page, str)
        or not _SAFE_NAME.fullmatch(engine)
        or not _SAFE_NAME.fullmatch(page)
    ):
        raise PilotError("source engine/page cannot form a safe private output path")
    return target_dir / engine / f"{page}.yml"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
