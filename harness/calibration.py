"""Deterministic calibration for trust diagnostics and review candidates.

This module measures automatic diagnostics against checked-in synthetic text.
It does not create adjudication records, human labels, or a T3 result. Injected
spans are known fixture annotations and only test candidate coverage.

Run ``python -m harness.calibration`` to print a reproducible JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
from typing import Iterable, Mapping, Sequence

from harness import normalization
from harness.calibration_fixtures import (
    DEFAULT_SEED,
    REPLACEMENT_MODES,
    CalibrationConfig,
    build_fixture_cases,
)
from harness.entities import ENTITY_CANDIDATE_VERSION
from harness.scoring import score_page
from harness.trust import (
    CANDIDATE_MAX_WINDOW,
    CANDIDATE_MIN_WORDS,
    REVIEW_CANDIDATE_VERSION,
    TRUST_DIAGNOSTIC_VERSION,
    UNSUPPORTED_WORD_THRESHOLD,
)


CALIBRATION_SCHEMA_VERSION = "fabrication-calibration-v01-draft"
SPAN_RECALL_MIN = 0.95
ENTITY_RECALL_MIN = 1.0
generate_fixture_cases = build_fixture_cases


def run_calibration(
    cases: Iterable[Mapping] | None = None,
    *,
    seed: int = DEFAULT_SEED,
    config: CalibrationConfig | None = None,
) -> dict:
    """Score fixture cases and return a diagnostic-only JSON-compatible report."""

    if cases is None:
        cases = build_fixture_cases(seed, config=config)
    case_results = [_score_case(dict(case)) for case in cases]
    report = _report(case_results, seed=seed if config is None else config.seed)
    return report


calibrate = run_calibration


def _score_case(case: dict) -> dict:
    scores = score_page(case["gold"], case["hyp"])
    hyp_norm = normalization.normalize(case["hyp"])
    spans = scores["review_candidate_spans_auto"]
    result = {
        key: case[key]
        for key in (
            "id",
            "category",
            "control",
            "page",
            "source_page",
            "seed",
            "mode",
            "position",
            "span_size",
            "removed_word_count",
            "common_word_overlap",
            "gold",
            "hyp",
            "expected_zero_candidates",
            "expected_entities",
            "injected_span",
            "offset_space",
        )
        if key in case
    }
    result["diagnostic_only"] = True
    result["automatic"] = {
        "hyp_chars": scores["hyp_chars"],
        "hyp_char_error": scores["hyp_char_error"],
        "omission_rate": scores["omission_rate"],
        "excess_length_rate": scores["excess_length_rate"],
        "repeat_4gram_rate": scores["repeat_4gram_rate"],
        "long_ins_rate_v01": scores["long_ins_rate_v01"],
        "candidate_count": len(spans),
        "candidate_chars": scores["review_candidate_chars_auto"],
        "candidate_rate": scores["review_candidate_rate_auto"],
        "entity_candidate_count": len(scores["entity_risk_candidates"]),
        "candidate_spans": [_compact_span(span) for span in spans],
    }
    result["offsets_valid"] = all(
        0 <= span["start"] < span["end"] <= len(hyp_norm)
        and hyp_norm[span["start"] : span["end"]] == span["text"]
        for span in spans
    )
    result["injection_evaluation"] = _evaluate_injection(case, hyp_norm, spans)
    result["entity_evaluation"] = _evaluate_entities(
        case, scores["entity_risk_candidates"], hyp_norm
    )
    result["failure"] = _failure_detail(result)
    return result


def _compact_span(span: Mapping) -> dict:
    return {
        key: span[key]
        for key in ("id", "start", "end", "text", "candidate_words", "total_words")
    }


def _evaluate_injection(case: Mapping, hyp_norm: str, spans: list[dict]) -> dict | None:
    injected = case.get("injected_span")
    if not injected:
        return None
    start, end = injected["start"], injected["end"]
    valid = (
        0 <= start < end <= len(hyp_norm) and hyp_norm[start:end] == injected["text"]
    )
    covered = _covered_chars(start, end, spans) if valid else 0
    ratio = covered / (end - start) if valid else 0.0
    eligible = injected["word_count"] >= 5
    return {
        "eligible": eligible,
        "coverage_rule": "candidate union covers at least 95% of injected normalized characters",
        "required_coverage": SPAN_RECALL_MIN,
        "injected_chars": end - start if valid else 0,
        "covered_chars": covered,
        "coverage": ratio,
        "recalled": bool(eligible and ratio >= SPAN_RECALL_MIN),
        "overlap_alone_is_not_recall": True,
    }


def _evaluate_entities(
    case: Mapping, candidates: list[dict], hyp_norm: str
) -> dict | None:
    expected = case.get("expected_entities")
    if not expected:
        return None
    details = []
    for item in expected:
        start, end = item["start"], item["end"]
        valid = (
            0 <= start < end <= len(hyp_norm) and hyp_norm[start:end] == item["text"]
        )
        matches = (
            [
                candidate
                for candidate in candidates
                if candidate["kind"] == item["kind"]
                and _covered_chars(start, end, [candidate]) / (end - start)
                >= SPAN_RECALL_MIN
            ]
            if valid
            else []
        )
        details.append(
            {
                "text": item["text"],
                "type": item["type"],
                "kind": item["kind"],
                "recalled": bool(matches),
                "matching_candidates": [candidate["text"] for candidate in matches],
            }
        )
    return {
        "coverage_rule": "same-kind entity candidate covers at least 95% of the injected normalized interval",
        "required_recall": ENTITY_RECALL_MIN,
        "entities": details,
        "recalled": all(item["recalled"] for item in details),
    }


def _covered_chars(start: int, end: int, spans: Sequence[Mapping]) -> int:
    intervals = sorted(
        (max(start, int(span["start"])), min(end, int(span["end"])))
        for span in spans
        if min(end, int(span["end"])) > max(start, int(span["start"]))
    )
    covered = 0
    cursor = start
    for left, right in intervals:
        if left > cursor:
            cursor = left
        if right > cursor:
            covered += right - cursor
            cursor = right
    return covered


def _failure_detail(result: Mapping) -> dict | None:
    failures: list[str] = []
    injection = result.get("injection_evaluation")
    if injection and injection["eligible"] and not injection["recalled"]:
        failures.append("injected_span_below_95_percent_coverage")
    if (
        result.get("expected_zero_candidates")
        and result["automatic"]["candidate_count"]
    ):
        failures.append("mandatory_zero_candidate_control_fired")
    entities = result.get("entity_evaluation")
    if entities and not entities["recalled"]:
        failures.append("high_risk_entity_candidate_missed")
    if not result.get("offsets_valid"):
        failures.append("candidate_offset_does_not_slice_normalized_hypothesis")
    if not failures:
        return None
    return {
        "reasons": failures,
        "candidate_spans": result["automatic"]["candidate_spans"],
        "injected_span": result.get("injected_span"),
        "injection_evaluation": injection,
        "entity_evaluation": entities,
    }


def _report(case_results: list[dict], *, seed: int) -> dict:
    span_cases = [item for item in case_results if item["category"] == "injected_span"]
    eligible = [item for item in span_cases if item["injection_evaluation"]["eligible"]]
    recalled = [item for item in eligible if item["injection_evaluation"]["recalled"]]
    entity_cases = [
        item for item in case_results if item["category"] == "high_risk_entity"
    ]
    entity_recalled = [
        item for item in entity_cases if item["entity_evaluation"]["recalled"]
    ]
    zero_controls = [
        item for item in case_results if item.get("expected_zero_candidates")
    ]
    zero_passed = all(
        item["automatic"]["candidate_count"] == 0 for item in zero_controls
    )
    automatic = [item["automatic"] for item in case_results]
    total_hyp_chars = sum(item["hyp_chars"] for item in automatic)
    candidate_chars = sum(item["candidate_chars"] for item in automatic)
    span_recall = _rate(len(recalled), len(eligible))
    entity_recall = _rate(len(entity_recalled), len(entity_cases))
    report = {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "seed": seed,
        "fixture": {
            "pages": sorted({item["page"] for item in case_results}),
            "span_sizes": sorted({item["span_size"] for item in span_cases}),
            "positions": sorted({item["position"] for item in span_cases}),
            "replacement_modes": list(REPLACEMENT_MODES),
            "case_count": len(case_results),
            "source": "checked-in synthetic development text",
        },
        "diagnostic_only": True,
        "diagnostic_versions": {
            "trust": TRUST_DIAGNOSTIC_VERSION,
            "review_candidates": REVIEW_CANDIDATE_VERSION,
            "entity_candidates": ENTITY_CANDIDATE_VERSION,
        },
        "review_candidate_parameters": {
            "unsupported_word_threshold": UNSUPPORTED_WORD_THRESHOLD,
            "minimum_candidate_words": CANDIDATE_MIN_WORDS,
            "maximum_window_words": CANDIDATE_MAX_WINDOW,
        },
        "human_labels": {"included": False, "performed": False, "source": None},
        "t3": {
            "status": "unresolved",
            "pass": None,
            "reason": "calibration diagnostics do not establish human labels or T3",
        },
        "calibration_targets": {
            "injected_span_recall": {
                "minimum": SPAN_RECALL_MIN,
                "observed": span_recall,
                "met": span_recall >= SPAN_RECALL_MIN,
            },
            "high_risk_entity_recall": {
                "minimum": ENTITY_RECALL_MIN,
                "observed": entity_recall,
                "met": entity_recall >= ENTITY_RECALL_MIN,
            },
            "mandatory_zero_candidate_controls": {"met": zero_passed},
        },
        "injected_span_recall": {
            "eligible_spans": len(eligible),
            "recalled_spans": len(recalled),
            "recall": span_recall,
            "minimum_target": SPAN_RECALL_MIN,
            "coverage_rule": "union of clipped automatic candidate intervals covers >=95% of normalized injected characters",
            "overlap_alone_is_not_recall": True,
            "by_mode": _group_recall(eligible, "mode"),
            "by_span_size": _group_recall(eligible, "span_size"),
            "by_position": _group_recall(eligible, "position"),
        },
        "high_risk_entity_recall": {
            "eligible_entities": len(entity_cases),
            "recalled_entities": len(entity_recalled),
            "recall": entity_recall,
            "minimum_target": ENTITY_RECALL_MIN,
            "coverage_rule": "same-kind entity candidate covers >=95% of normalized injected interval",
            "by_type": _entity_recall_by_type(entity_cases),
        },
        "benign_zero_candidate_controls": {
            "required_case_ids": [item["id"] for item in zero_controls],
            "passed": zero_passed,
            "candidate_counts": {
                item["id"]: item["automatic"]["candidate_count"]
                for item in zero_controls
            },
            "failures": [item["failure"] for item in zero_controls if item["failure"]],
        },
        "review_volume": {
            "cases": len(case_results),
            "hypothesis_chars": total_hyp_chars,
            "candidate_chars": candidate_chars,
            "candidate_rate_micro": candidate_chars / total_hyp_chars
            if total_hyp_chars
            else 0.0,
            "cases_with_candidates": sum(
                item["candidate_count"] > 0 for item in automatic
            ),
            "candidate_case_rate": _rate(
                sum(item["candidate_count"] > 0 for item in automatic),
                len(case_results),
            ),
            "candidate_spans": sum(item["candidate_count"] for item in automatic),
            "candidate_spans_mean": statistics.mean(
                item["candidate_count"] for item in automatic
            )
            if automatic
            else 0.0,
            "candidate_spans_max": max(
                (item["candidate_count"] for item in automatic), default=0
            ),
            "entity_candidates": sum(
                item["entity_candidate_count"] for item in automatic
            ),
            "by_category": {
                category: _review_volume(
                    [item for item in case_results if item["category"] == category]
                )
                for category in sorted({item["category"] for item in case_results})
            },
        },
        "failure_count": sum(item["failure"] is not None for item in case_results),
        "failures": [
            {
                key: item[key]
                for key in ("id", "category", "page", "mode", "position")
                if key in item
            }
            | {"details": item["failure"]}
            for item in case_results
            if item["failure"]
        ],
        "cases": case_results,
    }
    report["report_sha256"] = hashlib.sha256(
        json.dumps(report, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return report


def _group_recall(items: list[dict], field: str) -> dict:
    groups: dict[str, list[dict]] = {}
    for item in items:
        groups.setdefault(str(item[field]), []).append(item)
    return {
        key: {
            "eligible_spans": len(group),
            "recalled_spans": sum(
                item["injection_evaluation"]["recalled"] for item in group
            ),
            "recall": _rate(
                sum(item["injection_evaluation"]["recalled"] for item in group),
                len(group),
            ),
        }
        for key, group in sorted(groups.items())
    }


def _entity_recall_by_type(items: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        for expected in item["expected_entities"]:
            grouped.setdefault(expected["type"], []).append(item)
    return {
        key: {
            "eligible_entities": len(group),
            "recalled_entities": sum(
                item["entity_evaluation"]["recalled"] for item in group
            ),
            "recall": _rate(
                sum(item["entity_evaluation"]["recalled"] for item in group), len(group)
            ),
        }
        for key, group in sorted(grouped.items())
    }


def _review_volume(items: list[dict]) -> dict:
    values = [item["automatic"] for item in items]
    chars = sum(item["candidate_chars"] for item in values)
    hyp_chars = sum(item["hyp_chars"] for item in values)
    return {
        "cases": len(items),
        "hypothesis_chars": hyp_chars,
        "candidate_chars": chars,
        "candidate_spans": sum(item["candidate_count"] for item in values),
        "cases_with_candidates": sum(item["candidate_count"] > 0 for item in values),
        "candidate_rate_micro": chars / hyp_chars if hyp_chars else 0.0,
    }


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--output", type=Path, help="write JSON to this path instead of stdout"
    )
    parser.add_argument("--indent", type=int, default=2)
    args = parser.parse_args(argv)
    if args.indent < 0:
        parser.error("--indent must be non-negative")
    report = run_calibration(seed=args.seed)
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=args.indent, sort_keys=True)
        + "\n"
    )
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
