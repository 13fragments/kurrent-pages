"""Independent-review alignment, reliability, and consensus checks."""

from __future__ import annotations

from collections import Counter

from harness.adjudication_schema import (
    ENTITY_LABELS,
    MISSING_REVIEW_LABEL,
    SPAN_LABELS,
    AdjudicationError,
)
from harness.adjudication_validation import entity_key, overlap, span_key


def categorical_agreement(
    first: dict[str, str], second: dict[str, str], labels: frozenset[str]
) -> dict:
    pairs = [
        (
            first.get(key, MISSING_REVIEW_LABEL),
            second.get(key, MISSING_REVIEW_LABEL),
            True,
        )
        for key in sorted(set(first) | set(second))
    ]
    return _agreement_from_pairs(pairs, labels)


def manual_agreement(first: list[dict], second: list[dict], *, entity: bool) -> dict:
    pairs = manual_alignment(first, second, entity=entity)
    labeled_pairs = [
        (
            left["label"] if left is not None else MISSING_REVIEW_LABEL,
            right["label"] if right is not None else MISSING_REVIEW_LABEL,
            left is not None
            and right is not None
            and _manual_key(left, entity) == _manual_key(right, entity),
        )
        for left, right in pairs
    ]
    labels = ENTITY_LABELS if entity else SPAN_LABELS
    return _agreement_from_pairs(labeled_pairs, labels | {MISSING_REVIEW_LABEL})


def require_manual_resolution(
    consensus: list[dict], first: list[dict], second: list[dict], *, entity: bool
) -> None:
    pairs = manual_alignment(first, second, entity=entity)
    field = "manual entities" if entity else "manual spans"
    possible: list[list[int]] = []
    for left, right in pairs:
        references = [item for item in (left, right) if item is not None]
        possible.append(
            [
                index
                for index, resolved in enumerate(consensus)
                if all(_same_manual_claim(resolved, item) for item in references)
            ]
        )
    matching = _perfect_matching(possible, len(consensus))
    if matching is None or len(consensus) != len(pairs):
        raise AdjudicationError(
            f"consensus {field} must resolve each independently proposed claim once"
        )
    for pair_index, consensus_index in enumerate(matching):
        left, right = pairs[pair_index]
        if left is None or right is None:
            continue
        if left["label"] == right["label"]:
            resolved = consensus[consensus_index]
            if resolved["label"] != left["label"]:
                raise AdjudicationError(
                    f"consensus {field} contradicts agreeing reviewers"
                )
            if _manual_key(left, entity) == _manual_key(right, entity) and _manual_key(
                resolved, entity
            ) != _manual_key(left, entity):
                raise AdjudicationError(
                    f"consensus {field} contradicts agreeing reviewers"
                )


def require_agreed_consensus(
    consensus: dict[str, str], first: dict[str, str], second: dict[str, str], field: str
) -> None:
    for item in set(first) | set(second):
        left = first.get(item, MISSING_REVIEW_LABEL)
        right = second.get(item, MISSING_REVIEW_LABEL)
        if left == right and consensus.get(item) != left:
            raise AdjudicationError(
                f"consensus {field} label contradicts agreeing reviewers"
            )


def manual_alignment(
    first: list[dict], second: list[dict], *, entity: bool
) -> list[tuple[dict | None, dict | None]]:
    """Pair exact or overlapping independent proposals one-to-one."""
    remaining_second = set(range(len(second)))
    pairs: list[tuple[dict | None, dict | None]] = []
    for left in first:
        exact = next(
            (
                index
                for index in remaining_second
                if _manual_key(left, entity) == _manual_key(second[index], entity)
            ),
            None,
        )
        if exact is not None:
            pairs.append((left, second[exact]))
            remaining_second.remove(exact)
            continue
        compatible = [
            index
            for index in remaining_second
            if _same_manual_claim(left, second[index])
        ]
        if compatible:
            best = max(
                compatible,
                key=lambda index: (
                    _intersection(left, second[index]),
                    -second[index]["start"],
                    -second[index]["end"],
                ),
            )
            pairs.append((left, second[best]))
            remaining_second.remove(best)
        else:
            pairs.append((left, None))
    pairs.extend((None, second[index]) for index in sorted(remaining_second))
    return pairs


def _agreement_from_pairs(
    pairs: list[tuple[str, str, bool]], labels: frozenset[str]
) -> dict:
    first_counts = Counter(left for left, _, _ in pairs)
    second_counts = Counter(right for _, right, _ in pairs)
    confusion: dict[str, dict[str, int]] = {}
    for left, right, _ in pairs:
        row = confusion.setdefault(left, {})
        row[right] = row.get(right, 0) + 1
    items = len(pairs)
    label_agreements = sum(left == right for left, right, _ in pairs)
    agreements = sum(
        left == right and same_boundary for left, right, same_boundary in pairs
    )
    raw = agreements / items if items else None
    label_raw = label_agreements / items if items else None
    expected = (
        sum(first_counts[label] * second_counts[label] for label in labels) / items**2
        if items
        else None
    )
    kappa = (
        (label_raw - expected) / (1 - expected)
        if label_raw is not None and expected is not None and expected < 1
        else None
    )
    return {
        "items": items,
        "agreements": agreements,
        "raw_agreement": raw,
        "label_agreements": label_agreements,
        "label_raw_agreement": label_raw,
        "cohen_kappa": kappa,
        "class_counts": {
            "reviewer_1": dict(sorted(first_counts.items())),
            "reviewer_2": dict(sorted(second_counts.items())),
        },
        "confusion": {
            key: dict(sorted(value.items())) for key, value in sorted(confusion.items())
        },
    }


def _perfect_matching(
    possible: list[list[int]], consensus_count: int
) -> list[int] | None:
    if len(possible) != consensus_count or any(not choices for choices in possible):
        return None
    order = sorted(range(len(possible)), key=lambda index: len(possible[index]))
    assigned = [-1] * len(possible)

    def visit(position: int, used: set[int]) -> bool:
        if position == len(order):
            return True
        pair_index = order[position]
        for consensus_index in possible[pair_index]:
            if consensus_index in used:
                continue
            assigned[pair_index] = consensus_index
            if visit(position + 1, used | {consensus_index}):
                return True
        assigned[pair_index] = -1
        return False

    return assigned if visit(0, set()) else None


def _manual_key(item: dict, entity: bool) -> str:
    return entity_key(item) if entity else span_key(item)


def _same_manual_claim(first: dict, second: dict) -> bool:
    # Overlap denotes one textual claim even when reviewers disagree on entity kind.
    return overlap(first["start"], first["end"], second["start"], second["end"])


def _intersection(first: dict, second: dict) -> int:
    return max(
        0, min(first["end"], second["end"]) - max(first["start"], second["start"])
    )
