"""Validation and agreement helpers for fabrication adjudication."""

from __future__ import annotations

from harness.adjudication_schema import (
    ENTITY_KINDS,
    ENTITY_LABELS,
    SPAN_LABELS,
    AdjudicationError,
)


def validated_reviews(value: object, page_score: dict, hyp_norm: str) -> list[dict]:
    if not isinstance(value, list) or len(value) != 2:
        raise AdjudicationError("reviews must contain exactly two independent reviews")
    expected_candidates = {
        item["id"] for item in page_score.get("review_candidate_spans_auto", [])
    }
    expected_entities = {
        item["id"] for item in page_score.get("entity_risk_candidates", [])
    }
    candidate_ranges = [
        (item["start"], item["end"])
        for item in page_score.get("review_candidate_spans_auto", [])
    ]
    entity_ranges = [
        (item["start"], item["end"])
        for item in page_score.get("entity_risk_candidates", [])
    ]
    reviews = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"reviews[{index}] must be a mapping")
        reviewer = normalized_identity(
            raw.get("reviewer"), f"reviews[{index}].reviewer"
        )
        if raw.get("full_page_reviewed") is not True:
            raise AdjudicationError(f"reviews[{index}].full_page_reviewed must be true")
        added_spans = _validated_manual_spans(
            raw.get("added_spans", []), hyp_norm, f"reviews[{index}].added_spans"
        )
        manual_entities = _validated_manual_entities(
            raw.get("manual_entities", []),
            hyp_norm,
            f"reviews[{index}].manual_entities",
        )
        if any(
            overlap(span["start"], span["end"], start, end)
            for span in added_spans
            for start, end in candidate_ranges
        ):
            raise AdjudicationError(
                "reviewer-added spans must not overlap automatic candidates"
            )
        if any(
            overlap(entity["start"], entity["end"], start, end)
            for entity in manual_entities
            for start, end in entity_ranges
        ):
            raise AdjudicationError(
                "manual entities must not duplicate automatic candidates"
            )
        reviews.append(
            {
                "reviewer": reviewer,
                "candidate_labels": _validated_label_map(
                    raw.get("candidate_labels"),
                    expected_candidates,
                    SPAN_LABELS,
                    f"reviews[{index}].candidate_labels",
                ),
                "added_spans": added_spans,
                "entity_labels": _validated_label_map(
                    raw.get("entity_labels"),
                    expected_entities,
                    ENTITY_LABELS,
                    f"reviews[{index}].entity_labels",
                ),
                "manual_entities": manual_entities,
            }
        )
    if canonical_identity(reviews[0]["reviewer"]) == canonical_identity(
        reviews[1]["reviewer"]
    ):
        raise AdjudicationError("the two reviews must have distinct reviewer IDs")
    return reviews


def validated_spans(value: object, hyp_norm: str, page_score: dict) -> list[dict]:
    if not isinstance(value, list):
        raise AdjudicationError("spans must be a list")
    expected = {
        item["id"]: item for item in page_score.get("review_candidate_spans_auto", [])
    }
    seen: set[str] = set()
    spans = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"spans[{index}] must be a mapping")
        span = _validated_span(raw, hyp_norm, f"spans[{index}]")
        candidate_id = raw.get("candidate_id")
        if candidate_id is not None:
            if candidate_id not in expected:
                raise AdjudicationError(f"spans[{index}].candidate_id is unknown")
            if candidate_id in seen:
                raise AdjudicationError(f"duplicate candidate decision: {candidate_id}")
            candidate = expected[candidate_id]
            if (span["start"], span["end"]) != (candidate["start"], candidate["end"]):
                raise AdjudicationError(
                    f"spans[{index}] does not match candidate offsets"
                )
            seen.add(str(candidate_id))
        span["candidate_id"] = candidate_id
        spans.append(span)
    missing = set(expected) - seen
    if missing:
        raise AdjudicationError(
            f"spans leave {len(missing)} automatic candidates unlabeled"
        )
    _require_nonoverlapping(spans, "adjudicated spans")
    return sorted(spans, key=lambda item: (item["start"], item["end"]))


def validated_entities(
    value: object, manual_value: object, page_score: dict, hyp_norm: str
) -> list[dict]:
    if not isinstance(value, list):
        raise AdjudicationError("entities must label every automatic entity candidate")
    expected = {
        item["id"]: item for item in page_score.get("entity_risk_candidates", [])
    }
    seen: set[str] = set()
    entities: list[dict] = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"entities[{index}] must be a mapping")
        candidate_id = raw.get("candidate_id")
        if not isinstance(candidate_id, str) or candidate_id not in expected:
            raise AdjudicationError(f"entities[{index}].candidate_id is unknown")
        if candidate_id in seen:
            raise AdjudicationError(f"duplicate entity candidate label: {candidate_id}")
        candidate = expected[candidate_id]
        for field in ("start", "end", "text", "kind"):
            if raw.get(field) != candidate[field]:
                raise AdjudicationError(
                    f"entities[{index}].{field} does not match the automatic candidate"
                )
        entities.append(
            {
                **candidate,
                "label": _entity_label(raw.get("label"), f"entities[{index}].label"),
                "source": "automatic",
            }
        )
        seen.add(str(candidate_id))
    missing = set(expected) - seen
    if missing:
        raise AdjudicationError(
            f"{len(missing)} automatic entity candidates are unlabeled"
        )
    manual = _validated_manual_entities(manual_value, hyp_norm, "manual_entities")
    automatic_ranges = [(item["start"], item["end"]) for item in expected.values()]
    if any(
        overlap(entity["start"], entity["end"], start, end)
        for entity in manual
        for start, end in automatic_ranges
    ):
        raise AdjudicationError(
            "manual entities must not duplicate automatic candidates"
        )
    entities.extend({**entity, "source": "manual"} for entity in manual)
    return entities


def span_key(span: dict) -> str:
    return f"{span['start']}:{span['end']}"


def entity_key(entity: dict) -> str:
    return f"{entity['kind']}:{entity['start']}:{entity['end']}"


def canonical_identity(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalized_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdjudicationError(f"{field} must be a non-empty ID")
    normalized = " ".join(value.split())
    placeholder = normalized.casefold()
    if placeholder == "todo" or placeholder.startswith("todo-"):
        raise AdjudicationError(f"{field} must replace the template placeholder")
    return normalized


def expect(data: dict, field: str, expected: object) -> None:
    if data.get(field) != expected:
        raise AdjudicationError(
            f"{field} does not match scored output ({data.get(field)!r})"
        )


def _validated_label_map(
    value: object, expected: set[str], labels: frozenset[str], field: str
) -> dict[str, str]:
    if not isinstance(value, list):
        raise AdjudicationError(f"{field} must be a list")
    found: dict[str, str] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"{field}[{index}] must be a mapping")
        candidate_id = raw.get("candidate_id")
        if candidate_id not in expected:
            raise AdjudicationError(f"{field}[{index}].candidate_id is unknown")
        if candidate_id in found:
            raise AdjudicationError(f"{field} repeats candidate {candidate_id}")
        label = raw.get("label")
        if label not in labels:
            raise AdjudicationError(f"{field}[{index}].label is not recognized")
        found[str(candidate_id)] = str(label)
    missing = expected - set(found)
    if missing:
        raise AdjudicationError(f"{field} leaves {len(missing)} candidates unlabeled")
    return found


def _validated_manual_spans(value: object, hyp_norm: str, field: str) -> list[dict]:
    if not isinstance(value, list):
        raise AdjudicationError(f"{field} must be a list")
    spans = []
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"{field}[{index}] must be a mapping")
        spans.append(_validated_span(raw, hyp_norm, f"{field}[{index}]"))
    _require_nonoverlapping(spans, field)
    return sorted(spans, key=lambda item: (item["start"], item["end"]))


def _validated_span(raw: dict, hyp_norm: str, field: str) -> dict:
    start = _offset(raw.get("start"), f"{field}.start", len(hyp_norm))
    end = _offset(raw.get("end"), f"{field}.end", len(hyp_norm))
    label = raw.get("label")
    if start >= end:
        raise AdjudicationError(f"{field} must have start < end")
    if label not in SPAN_LABELS:
        raise AdjudicationError(f"{field}.label is not recognized")
    if "text" in raw and raw["text"] != hyp_norm[start:end]:
        raise AdjudicationError(f"{field}.text does not match hypothesis offsets")
    return {
        "start": start,
        "end": end,
        "label": str(label),
        "text": hyp_norm[start:end],
    }


def _validated_manual_entities(value: object, hyp_norm: str, field: str) -> list[dict]:
    if not isinstance(value, list):
        raise AdjudicationError(f"{field} must be a list")
    entities = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise AdjudicationError(f"{field}[{index}] must be a mapping")
        start = _offset(raw.get("start"), f"{field}[{index}].start", len(hyp_norm))
        end = _offset(raw.get("end"), f"{field}[{index}].end", len(hyp_norm))
        if start >= end:
            raise AdjudicationError(f"{field}[{index}] must have start < end")
        kind = raw.get("kind")
        if kind not in ENTITY_KINDS:
            raise AdjudicationError(f"{field}[{index}].kind is not recognized")
        entity = {
            "id": f"manual:{kind}:{start}:{end}",
            "kind": str(kind),
            "start": start,
            "end": end,
            "text": hyp_norm[start:end],
            "label": _entity_label(raw.get("label"), f"{field}[{index}].label"),
        }
        key = entity_key(entity)
        if key in seen:
            raise AdjudicationError(f"{field} repeats entity {key}")
        seen.add(key)
        entities.append(entity)
    _require_nonoverlapping(entities, field)
    return sorted(entities, key=lambda item: (item["start"], item["end"]))


def _require_nonoverlapping(items: list[dict], field: str) -> None:
    ordered = sorted(items, key=lambda item: (item["start"], item["end"]))
    for previous, current in zip(ordered, ordered[1:]):
        if current["start"] < previous["end"]:
            raise AdjudicationError(f"{field} must not overlap")


def overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and end > other_start


def _entity_label(value: object, field: str) -> str:
    if value not in ENTITY_LABELS:
        raise AdjudicationError(f"{field} is not recognized")
    return str(value)


def _offset(value: object, field: str, maximum: int) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise AdjudicationError(f"{field} must be an integer from 0 to {maximum}")
    return value
