"""Validate independent, image-grounded fabrication adjudications."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from harness.adjudication_schema import (
    ADJUDICATION_SCHEMA_VERSION,
    ENTITY_LABELS,
    SPAN_LABELS,
    AdjudicationError,
)
from harness.adjudication_reliability import (
    categorical_agreement,
    manual_agreement,
    require_agreed_consensus,
    require_manual_resolution,
)
from harness.adjudication_validation import (
    canonical_identity,
    expect,
    normalized_identity,
    validated_entities,
    validated_reviews,
    validated_spans,
)


def adjudication_template(engine: str, page: str, page_score: dict) -> dict:
    """Coordinator form; deliberately invalid until two reviews are complete."""
    candidates = page_score.get("review_candidate_spans_auto", [])
    entities = page_score.get("entity_risk_candidates", [])

    def review(number: int) -> dict:
        return {
            "reviewer": f"TODO-reviewer-{number}",
            "full_page_reviewed": False,
            "candidate_labels": [
                {"candidate_id": candidate["id"], "label": "TODO"}
                for candidate in candidates
            ],
            "added_spans": [],
            "entity_labels": [
                {"candidate_id": candidate["id"], "label": "TODO"}
                for candidate in entities
            ],
            "manual_entities": [],
        }

    return {
        "schema_version": ADJUDICATION_SCHEMA_VERSION,
        "engine": engine,
        "page": page,
        "hypothesis_sha256": page_score["hypothesis_sha256"],
        "image_sha256": page_score.get("image_sha256"),
        "reviews": [review(1), review(2)],
        "resolver": None,
        "spans": [
            {
                "candidate_id": candidate["id"],
                "start": candidate["start"],
                "end": candidate["end"],
                "text": candidate["text"],
                "label": "TODO",
            }
            for candidate in candidates
        ],
        "entities": [
            {
                "candidate_id": candidate["id"],
                "start": candidate["start"],
                "end": candidate["end"],
                "text": candidate["text"],
                "kind": candidate["kind"],
                "label": "TODO",
            }
            for candidate in entities
        ],
        "manual_entities": [],
    }


def unadjudicated_fields() -> dict:
    return {
        "adjudication_status": "unadjudicated",
        "adjudication_schema_version": None,
        "adjudication_reviewers": None,
        "adjudication_resolver": None,
        "adjudication_disagreements": None,
        "candidate_review_agreement": None,
        "manual_span_review_agreement": None,
        "entity_review_agreement": None,
        "manual_entity_review_agreement": None,
        "adjudicated_spans": [],
        "adjudication_label_chars": None,
        "adjudication_label_counts": None,
        "adjudicated_entities": [],
        "fab_chars_adj": None,
        "fab_rate_adj": None,
        "fab_page": None,
        "degenerate_chars_adj": None,
        "degenerate_rate_adj": None,
        "trust_failure_chars_adj": None,
        "trust_failure_rate_adj": None,
        "trust_failure_page": None,
        "fabricated_entities": None,
        "fabricated_entity_count": None,
        "entity_supported_adj": None,
        "entity_decided_adj": None,
        "entity_uncertain_adj": None,
        "entity_not_entity_adj": None,
        "entity_precision_adj": None,
    }


def invalid_adjudication_fields(message: str) -> dict:
    return {
        **unadjudicated_fields(),
        "adjudication_status": "invalid",
        "adjudication_error": message,
    }


def load_adjudication(
    path: Path,
    *,
    engine: str,
    page: str,
    hyp_norm: str,
    page_score: dict,
) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AdjudicationError(f"cannot read {path}: {exc}") from exc
    return score_adjudication(
        data, engine=engine, page=page, hyp_norm=hyp_norm, page_score=page_score
    )


def is_untouched_adjudication_template(
    path: Path, *, engine: str, page: str, page_score: dict
) -> bool:
    """Whether a private coordinator form is the exact generated TODO template."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    return data == adjudication_template(engine, page, page_score)


def score_adjudication(
    data: object,
    *,
    engine: str,
    page: str,
    hyp_norm: str,
    page_score: dict,
) -> dict:
    """Validate two independent reviews plus their resolved consensus."""
    if not isinstance(data, dict):
        raise AdjudicationError("document must be a mapping")
    expect(data, "schema_version", ADJUDICATION_SCHEMA_VERSION)
    expect(data, "engine", engine)
    expect(data, "page", page)
    expect(data, "hypothesis_sha256", page_score.get("hypothesis_sha256"))
    expect(data, "image_sha256", page_score.get("image_sha256"))
    image_hash = page_score.get("image_sha256")
    if not _is_sha256(image_hash):
        raise AdjudicationError("page score is not bound to a valid image SHA-256")
    actual_hash = hashlib.sha256(hyp_norm.encode("utf-8")).hexdigest()
    if page_score.get("hypothesis_sha256") != actual_hash:
        raise AdjudicationError("page score is not bound to the normalized hypothesis")
    if len(hyp_norm) != page_score.get("hyp_chars"):
        raise AdjudicationError(
            "normalized hypothesis length does not match page score"
        )

    reviews = validated_reviews(data.get("reviews"), page_score, hyp_norm)
    spans = validated_spans(data.get("spans", []), hyp_norm, page_score)
    entities = validated_entities(
        data.get("entities"), data.get("manual_entities", []), page_score, hyp_norm
    )
    candidate_consensus = {
        span["candidate_id"]: span["label"]
        for span in spans
        if span.get("candidate_id") is not None
    }
    entity_consensus = {
        entity["id"]: entity["label"]
        for entity in entities
        if entity["source"] == "automatic"
    }
    agreements = _review_agreements(reviews)

    require_manual_resolution(
        [span for span in spans if span.get("candidate_id") is None],
        reviews[0]["added_spans"],
        reviews[1]["added_spans"],
        entity=False,
    )
    require_manual_resolution(
        [entity for entity in entities if entity["source"] == "manual"],
        reviews[0]["manual_entities"],
        reviews[1]["manual_entities"],
        entity=True,
    )
    require_agreed_consensus(
        candidate_consensus,
        reviews[0]["candidate_labels"],
        reviews[1]["candidate_labels"],
        "candidate",
    )
    require_agreed_consensus(
        entity_consensus,
        reviews[0]["entity_labels"],
        reviews[1]["entity_labels"],
        "entity",
    )
    disagreements = sum(
        agreement["items"] - agreement["agreements"]
        for agreement in agreements.values()
    )
    reviewer_ids = [review["reviewer"] for review in reviews]
    resolver = _validated_resolver(data.get("resolver"), reviewer_ids, disagreements)

    label_chars = {label: 0 for label in SPAN_LABELS}
    label_counts = {label: 0 for label in SPAN_LABELS}
    for span in spans:
        label_chars[span["label"]] += span["end"] - span["start"]
        label_counts[span["label"]] += 1

    fab_chars = label_chars["fluent_fabrication"]
    degenerate_chars = label_chars["degenerate_generation"]
    fabricated_entities = [item for item in entities if item["label"] == "fabricated"]
    supported_entities = sum(item["label"] == "supported" for item in entities)
    decided_entities = supported_entities + len(fabricated_entities)
    uncertain_entities = sum(item["label"] == "uncertain" for item in entities)
    not_entities = sum(item["label"] == "not_entity" for item in entities)
    denominator = len(hyp_norm)
    return {
        "adjudication_status": "complete",
        "adjudication_schema_version": ADJUDICATION_SCHEMA_VERSION,
        "adjudication_reviewers": reviewer_ids,
        "adjudication_resolver": resolver,
        "adjudication_disagreements": disagreements,
        **agreements,
        "adjudicated_spans": spans,
        "adjudication_label_chars": label_chars,
        "adjudication_label_counts": label_counts,
        "adjudicated_entities": entities,
        "fab_chars_adj": fab_chars,
        "fab_rate_adj": fab_chars / denominator if denominator else 0.0,
        "fab_page": fab_chars > 0,
        "degenerate_chars_adj": degenerate_chars,
        "degenerate_rate_adj": degenerate_chars / denominator if denominator else 0.0,
        "trust_failure_chars_adj": fab_chars + degenerate_chars,
        "trust_failure_rate_adj": (
            (fab_chars + degenerate_chars) / denominator if denominator else 0.0
        ),
        "trust_failure_page": fab_chars + degenerate_chars > 0,
        "fabricated_entities": fabricated_entities,
        "fabricated_entity_count": len(fabricated_entities),
        "entity_supported_adj": supported_entities,
        "entity_decided_adj": decided_entities,
        "entity_uncertain_adj": uncertain_entities,
        "entity_not_entity_adj": not_entities,
        "entity_precision_adj": (
            supported_entities / decided_entities if decided_entities else None
        ),
    }


def _review_agreements(reviews: list[dict]) -> dict:
    return {
        "candidate_review_agreement": categorical_agreement(
            reviews[0]["candidate_labels"],
            reviews[1]["candidate_labels"],
            SPAN_LABELS,
        ),
        "manual_span_review_agreement": manual_agreement(
            reviews[0]["added_spans"], reviews[1]["added_spans"], entity=False
        ),
        "entity_review_agreement": categorical_agreement(
            reviews[0]["entity_labels"],
            reviews[1]["entity_labels"],
            ENTITY_LABELS,
        ),
        "manual_entity_review_agreement": manual_agreement(
            reviews[0]["manual_entities"],
            reviews[1]["manual_entities"],
            entity=True,
        ),
    }


def _validated_resolver(
    value: object, reviewer_ids: list[str], disagreements: int
) -> str | None:
    if not disagreements:
        if value is not None:
            raise AdjudicationError("resolver must be null when the reviews agree")
        return None
    resolver = normalized_identity(value, "resolver")
    if canonical_identity(resolver) in {
        canonical_identity(reviewer) for reviewer in reviewer_ids
    }:
        raise AdjudicationError(
            "a distinct non-empty resolver is required when reviews disagree"
        )
    return resolver


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.casefold())
    )
