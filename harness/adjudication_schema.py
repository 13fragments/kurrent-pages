"""Shared schema constants for image-grounded adjudication."""

ADJUDICATION_SCHEMA_VERSION = "fabrication-adjudication-v01-draft"
SPAN_LABELS = frozenset(
    {
        "supported",
        "perception_error",
        "convention_error",
        "order_layout_error",
        "fluent_fabrication",
        "degenerate_generation",
        "gt_or_image_uncertain",
    }
)
ENTITY_LABELS = frozenset({"supported", "fabricated", "uncertain", "not_entity"})
ENTITY_KINDS = frozenset(
    {"name_or_place", "person", "place", "date", "amount", "identifier"}
)
MISSING_REVIEW_LABEL = "not_found"


class AdjudicationError(ValueError):
    """An adjudication cannot be bound safely to its scored hypothesis."""
