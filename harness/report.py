"""Aggregation over page scores + the §8 kill-criterion check + markdown report."""

from __future__ import annotations

from collections import Counter
from math import comb
from statistics import mean, median

from harness.adjudication_validation import canonical_identity
from harness.gold import GoldPage, hard_strata_pages
from harness.report_markdown import render_report as render_report

# §8 kill criterion, frozen: applies to open CRNN end-to-end configs on the
# hard-strata set. KILL if median cer_norm <= 0.25 AND median entity recall
# >= 0.50 AND segmentation-failure rate <= 20%.
KILL_MAX_CER = 0.25
KILL_MIN_ENTITY_RECALL = 0.50
KILL_MAX_SEG_FAIL_RATE = 0.20
KILL_ELIGIBLE_ENGINE_TYPES = {"calamari", "kraken", "pylaia"}

REPORT_SEVERITY_CUTS = (0.01, 0.05, 0.10)
_AGG_METRICS = (
    "cer_dipl",
    "cer_norm",
    "wer_norm",
    "nls_norm",
    "ro_cost",
    "hyp_char_error",
    "omission_rate",
    "excess_length_rate",
    "repeat_4gram_rate",
    "long_ins_rate_v01",
    "review_candidate_rate_auto",
    "fab_rate_adj",
    "degenerate_rate_adj",
    "trust_failure_rate_adj",
)


def _stats(pages_scores: list[dict]) -> dict:
    out: dict = {"n": len(pages_scores)}
    for metric in _AGG_METRICS:
        values = [s[metric] for s in pages_scores if s.get(metric) is not None]
        out[f"{metric}_median"] = median(values) if values else None
        out[f"{metric}_mean"] = mean(values) if values else None
        out[f"{metric}_max"] = max(values) if values else None
    recalls = [
        s["entity_recall"] for s in pages_scores if s.get("entity_recall") is not None
    ]
    out["entity_recall_median"] = median(recalls) if recalls else None
    # Coverage = annotated pages (an empty entity list is still an annotation).
    out["entity_pages"] = sum(1 for s in pages_scores if s.get("entity_annotated"))
    seg = [s["seg_fail"] for s in pages_scores if "seg_fail" in s]
    out["seg_fail_rate"] = (sum(seg) / len(seg)) if seg else None
    _add_diagnostic_micro_rates(out, pages_scores)
    _add_adjudication_stats(out, pages_scores)
    return out


def _add_diagnostic_micro_rates(out: dict, pages_scores: list[dict]) -> None:
    counts = [score.get("alignment_counts", {}) for score in pages_scores]
    hyp_errors = sum(item.get("sub", 0) + item.get("ins", 0) for item in counts)
    hyp_chars = sum(
        item.get("equal", 0) + item.get("sub", 0) + item.get("ins", 0)
        for item in counts
    )
    omissions = sum(item.get("del", 0) for item in counts)
    gold_chars = sum(
        item.get("equal", 0) + item.get("sub", 0) + item.get("del", 0)
        for item in counts
    )
    out["hyp_char_error_micro"] = hyp_errors / hyp_chars if hyp_chars else 0.0
    out["omission_rate_micro"] = omissions / gold_chars if gold_chars else 0.0
    excess_chars = sum(
        max(0, item.get("ins", 0) - item.get("del", 0)) for item in counts
    )
    out["excess_length_rate_micro"] = excess_chars / hyp_chars if hyp_chars else 0.0
    out["long_ins_rate_v01_micro"] = _micro_rate(
        pages_scores, "long_ins_chars_v01", "hyp_chars"
    )
    out["review_candidate_rate_auto_micro"] = _micro_rate(
        pages_scores, "review_candidate_chars_auto", "hyp_chars"
    )


def _add_adjudication_stats(out: dict, pages_scores: list[dict]) -> None:
    complete = [
        score
        for score in pages_scores
        if score.get("adjudication_status") == "complete"
    ]
    out["adjudicated_pages"] = len(complete)
    out["invalid_adjudication_pages"] = sum(
        score.get("adjudication_status") == "invalid" for score in pages_scores
    )
    out["adjudication_disagreements"] = sum(
        score.get("adjudication_disagreements", 0) for score in complete
    )
    reviewer_pairs = sorted(
        {
            tuple(
                canonical_identity(reviewer)
                for reviewer in score["adjudication_reviewers"]
            )
            for score in complete
        }
    )
    out["reviewer_pair_consistent"] = len(reviewer_pairs) <= 1
    reliability_scores = complete if out["reviewer_pair_consistent"] else []
    for field in (
        "candidate_review_agreement",
        "manual_span_review_agreement",
        "entity_review_agreement",
        "manual_entity_review_agreement",
    ):
        out[field] = _pooled_agreement(reliability_scores, field)
    out["fab_chars_adj_total"] = sum(score["fab_chars_adj"] for score in complete)
    out["degenerate_chars_adj_total"] = sum(
        score["degenerate_chars_adj"] for score in complete
    )
    out["trust_failure_chars_adj_total"] = sum(
        score["trust_failure_chars_adj"] for score in complete
    )
    out["hyp_chars_adjudicated_total"] = sum(score["hyp_chars"] for score in complete)
    out["fab_rate_adj_micro"] = _micro_rate(complete, "fab_chars_adj", "hyp_chars")
    out["degenerate_rate_adj_micro"] = _micro_rate(
        complete, "degenerate_chars_adj", "hyp_chars"
    )
    out["trust_failure_rate_adj_micro"] = _micro_rate(
        complete, "trust_failure_chars_adj", "hyp_chars"
    )
    out["fab_page_count"] = sum(bool(score["fab_page"]) for score in complete)
    out["fab_page_rate_adj"] = (
        out["fab_page_count"] / len(complete) if complete else None
    )
    out["fab_page_rate_adj_upper95"] = _binomial_upper_bound(
        out["fab_page_count"], len(complete)
    )
    out["trust_failure_page_count"] = sum(
        bool(score["trust_failure_page"]) for score in complete
    )
    out["fabricated_entity_count"] = sum(
        score["fabricated_entity_count"] for score in complete
    )
    supported = sum(score["entity_supported_adj"] for score in complete)
    decided = sum(score["entity_decided_adj"] for score in complete)
    out["entity_precision_adj_micro"] = supported / decided if decided else None
    out["entity_uncertain_adj_total"] = sum(
        score["entity_uncertain_adj"] for score in complete
    )
    out["entity_not_entity_adj_total"] = sum(
        score["entity_not_entity_adj"] for score in complete
    )
    entity_claims = decided + out["entity_uncertain_adj_total"]
    out["entity_decision_coverage_adj"] = (
        decided / entity_claims if entity_claims else None
    )
    out["entity_candidate_count_adj_total"] = (
        entity_claims + out["entity_not_entity_adj_total"]
    )
    out["adjudication_label_counts"] = dict(
        sorted(
            sum(
                (
                    Counter(score.get("adjudication_label_counts", {}))
                    for score in complete
                ),
                Counter(),
            ).items()
        )
    )
    out["entity_label_counts"] = {
        "fabricated": out["fabricated_entity_count"],
        "supported": supported,
        "uncertain": out["entity_uncertain_adj_total"],
        "not_entity": out["entity_not_entity_adj_total"],
    }
    for metric in ("fab_rate_adj", "degenerate_rate_adj", "trust_failure_rate_adj"):
        values = [score[metric] for score in complete]
        out[f"{metric}_above"] = {
            f">{cut:.2f}": sum(value > cut for value in values)
            for cut in REPORT_SEVERITY_CUTS
        }


def _pooled_agreement(scores: list[dict], field: str) -> dict:
    agreements = [score[field] for score in scores if score.get(field) is not None]
    items = sum(item["items"] for item in agreements)
    agreed = sum(item["agreements"] for item in agreements)
    label_agreed = sum(
        item.get("label_agreements", item["agreements"]) for item in agreements
    )
    first_counts: Counter = Counter()
    second_counts: Counter = Counter()
    confusion: dict[str, Counter] = {}
    for agreement in agreements:
        first_counts.update(agreement["class_counts"]["reviewer_1"])
        second_counts.update(agreement["class_counts"]["reviewer_2"])
        for left, row in agreement["confusion"].items():
            confusion.setdefault(left, Counter()).update(row)
    raw = agreed / items if items else None
    label_raw = label_agreed / items if items else None
    labels = set(first_counts) | set(second_counts)
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
        "agreements": agreed,
        "raw_agreement": raw,
        "label_agreements": label_agreed,
        "label_raw_agreement": label_raw,
        "cohen_kappa": kappa,
        "class_counts": {
            "reviewer_1": dict(sorted(first_counts.items())),
            "reviewer_2": dict(sorted(second_counts.items())),
        },
        "confusion": {
            label: dict(sorted(row.items())) for label, row in sorted(confusion.items())
        },
    }


def _micro_rate(scores: list[dict], numerator: str, denominator: str) -> float | None:
    total_denominator = sum(score.get(denominator, 0) for score in scores)
    if not scores:
        return None
    if not total_denominator:
        return 0.0
    return sum(score.get(numerator, 0) for score in scores) / total_denominator


def _binomial_upper_bound(
    affected: int, total: int, confidence: float = 0.95
) -> float | None:
    """One-sided exact Clopper-Pearson upper bound."""
    if total == 0:
        return None
    if affected >= total:
        return 1.0
    alpha = 1.0 - confidence
    low, high = affected / total, 1.0
    for _ in range(80):
        probability = (low + high) / 2
        cdf = sum(
            comb(total, count)
            * probability**count
            * (1 - probability) ** (total - count)
            for count in range(affected + 1)
        )
        if cdf > alpha:
            low = probability
        else:
            high = probability
    return high


def aggregate(
    page_scores: dict[str, dict],
    annex_scores: dict[str, dict],
    pages: list[GoldPage],
    engine_meta: dict | None = None,
) -> dict:
    """Overall / per-primary-stratum / hard-strata aggregates + kill check + annex.

    page_scores: scored pages only (score_page shape); annex_scores: fabrication
    probes (score_annex shape). The two dicts never mix."""
    by_id = {p.id: p for p in pages}
    strata: dict[str, list[dict]] = {}
    tags: dict[str, list[dict]] = {}
    for gid, scores in page_scores.items():
        strata.setdefault(by_id[gid].primary_stratum, []).append(scores)
        # All-tags cut: protocol strata like marginalia exist mostly as
        # secondary tags; pages count under every tag they carry here.
        for tag in by_id[gid].strata:
            tags.setdefault(tag, []).append(scores)

    hard_ids = {p.id for p in hard_strata_pages(pages)}
    hard = [s for gid, s in page_scores.items() if gid in hard_ids]
    hard_stats = _stats(hard)
    overall = _stats(list(page_scores.values()))
    expected_scored = sum(page.scored for page in pages)
    expected_annex = len(pages) - expected_scored

    return {
        "overall": overall,
        "per_stratum": {name: _stats(group) for name, group in sorted(strata.items())},
        "per_tag": {name: _stats(group) for name, group in sorted(tags.items())},
        "hard_strata": hard_stats,
        "kill_check": kill_check(
            hard_stats,
            expected_pages=len(hard_ids),
            eligible=_kill_eligible(engine_meta or {}),
        ),
        "trust_check": trust_check(
            overall,
            expected_pages=expected_scored,
            annex_scores=annex_scores,
            expected_annex=expected_annex,
        ),
        "hand_cluster_sensitivity": _hand_cluster_sensitivity(page_scores, pages),
        "annex": {
            "pages": len(annex_scores),
            "abstention_ok": sum(
                bool(s["abstention_ok"]) for s in annex_scores.values()
            ),
            "hallucinated_chars": {
                gid: s["hallucinated_chars"] for gid, s in annex_scores.items()
            },
        },
    }


def trust_check(
    overall: dict,
    *,
    expected_pages: int,
    annex_scores: dict[str, dict],
    expected_annex: int,
) -> dict:
    """Completeness only: draft T3 has no ratified numeric pass thresholds."""
    adjudications_complete = (
        expected_pages > 0
        and overall.get("n") == expected_pages
        and overall.get("adjudicated_pages") == expected_pages
        and overall.get("invalid_adjudication_pages") == 0
        and overall.get("reviewer_pair_consistent") is True
    )
    annex_complete = len(annex_scores) == expected_annex
    annex_clean = annex_complete and all(
        bool(score.get("abstention_ok")) for score in annex_scores.values()
    )
    return {
        "status": "unresolved",
        "pass": None,
        "thresholds_ratified": False,
        # Annex pages are reported only (§10, 2026-10-18): both contain real text.
        "complete": adjudications_complete,
        "adjudicated_pages": overall.get("adjudicated_pages", 0),
        "expected_pages": expected_pages,
        "annex_complete": annex_complete,
        "annex_clean": annex_clean,
        "reason": "T3 thresholds require a blinded pilot and protocol amendment",
    }


def _hand_cluster_sensitivity(
    page_scores: dict[str, dict], pages: list[GoldPage]
) -> dict:
    page_meta = {page.id: page for page in pages}
    clusters: dict[str, list[dict]] = {}
    for page_id, score in page_scores.items():
        if score.get("adjudication_status") != "complete":
            continue
        clusters.setdefault(page_meta[page_id].hand_cluster_id, []).append(score)
    affected = sum(
        any(score["fab_page"] for score in group) for group in clusters.values()
    )
    return {
        "clusters": len(clusters),
        "affected_clusters": affected,
        "affected_rate": affected / len(clusters) if clusters else None,
        "affected_rate_upper95": _binomial_upper_bound(affected, len(clusters)),
    }


def _kill_eligible(engine_meta: dict) -> bool:
    config = engine_meta.get("config") or {}
    if "kill_eligible" in config:
        return bool(config["kill_eligible"])
    return engine_meta.get("type") in KILL_ELIGIBLE_ENGINE_TYPES


def kill_check(hard_stats: dict, expected_pages: int, eligible: bool = True) -> dict:
    """§8 evaluation for one engine config. `kill` means: this config would
    trigger the kill criterion IF it is an open CRNN end-to-end pipeline.

    The verdict drives the Gate 0 project decision, so it can only fire on a
    COMPLETE hard-strata set: every hard page scored AND entity-annotated.
    Anything less reports `complete: false` and `kill: false`."""
    cer_med = hard_stats.get("cer_norm_median")
    recall_med = hard_stats.get("entity_recall_median")
    seg_rate = hard_stats.get("seg_fail_rate")
    complete = (
        expected_pages > 0
        and hard_stats.get("n") == expected_pages
        and hard_stats.get("entity_pages") == expected_pages
    )
    conditions = {
        f"median cer_norm <= {KILL_MAX_CER}": cer_med is not None
        and cer_med <= KILL_MAX_CER,
        f"median entity recall >= {KILL_MIN_ENTITY_RECALL}": recall_med is not None
        and recall_med >= KILL_MIN_ENTITY_RECALL,
        f"seg-failure rate <= {KILL_MAX_SEG_FAIL_RATE}": seg_rate is not None
        and seg_rate <= KILL_MAX_SEG_FAIL_RATE,
    }
    conditions_met = complete and all(conditions.values())
    return {
        "eligible": eligible,
        "complete": complete,
        "scored_pages": hard_stats.get("n"),
        "expected_pages": expected_pages,
        "conditions": conditions,
        "conditions_met": conditions_met,
        "kill": eligible and conditions_met,
    }
