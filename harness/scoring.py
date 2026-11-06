"""Per-page metric computation — protocol §5, pre-registered.

score_page() produces every §5 metric for one (gold, hypothesis) pair:
  §5.1 cer_dipl, cer_norm (+_lc), wer_norm, nls_norm
  §5.2 ro_cost (Hungarian line matching, unmatched lines counted whole)
  draft §5.3 trust diagnostics + fabrication review candidates
  §5.4 seg_fail (cer_norm > 0.75 or empty output)
  §5.5 entity recall (entities.py) + name-like precision candidates
  §5.6 abstention behavior over gold [unleserlich] spans / annex pages
  §5.7 correction-time bucket
"""

from __future__ import annotations

import re

from harness import normalization
from harness.adjudication import unadjudicated_fields
from harness.alignment import (
    DEL,
    EQUAL,
    INS,
    SUB,
    align_ops,
    assignment_cost_with_unmatched,
    cer,
    levenshtein,
    nls,
    wer,
)
from harness.entities import extract_entity_risk_candidates, score_entities
from harness.gold import Entity
from harness.trust import score_trust_diagnostics

SEG_FAIL_CER = 0.75  # §5.4
CORRECTION_BUCKETS = ((0.05, "<5%"), (0.15, "5-15%"), (0.30, "15-30%"))  # §5.7

_NAME_LIKE = re.compile(r"^[A-ZÄÖÜ][a-zäöüß]{2,}")


def coverage_lengths(gold_text: str, hyp_text: str) -> tuple[int, int]:
    """Normalized reference and hypothesis lengths (R, H) of the pair that cer_norm scores.

    Omission guard, model-track EXP-20261029-page-dev-set amendment A8: coverage is H / R.
    An empty normalized reference is an invalid input.
    """
    gold_scored, hyp_scored = normalization.scoring_texts(gold_text, hyp_text)
    ref_len = len(normalization.normalize(gold_scored))
    if ref_len == 0:
        raise ValueError("reference is empty after normalization")
    return ref_len, len(normalization.normalize(hyp_scored))


def score_page(
    gold_text: str,
    hyp_text: str,
    entities: list[Entity] | None = None,
) -> dict:
    """All §5 metrics for one scored page. Annex pages go to score_annex()."""
    gold_scored, hyp_scored = normalization.scoring_texts(gold_text, hyp_text)
    gold_norm = normalization.normalize(gold_scored)
    hyp_norm = normalization.normalize(hyp_scored)
    scores: dict = {
        "cer_dipl": cer(
            normalization.diplomatic(gold_scored), normalization.diplomatic(hyp_scored)
        ),
        "cer_norm": cer(gold_norm, hyp_norm),
        "cer_norm_lc": cer(gold_norm.lower(), hyp_norm.lower()),
        "wer_norm": wer(gold_norm.split(), hyp_norm.split()),
        "nls_norm": nls(gold_norm, hyp_norm),
    }
    # Clamped at 0 (§5.2 "≥ ~0"): a hypothesis with perfect text but different
    # line wrapping has positive assignment cost at cer_norm 0, which is a
    # wrapping difference, not an ordering error.
    scores["ro_cost"] = max(
        0.0, scores["cer_norm"] - _order_insensitive_cer(gold_scored, hyp_scored)
    )
    scores.update(score_trust_diagnostics(gold_norm, hyp_norm))
    scores.update(extract_entity_risk_candidates(hyp_norm))
    scores.update(unadjudicated_fields())
    # Deprecated v0.1 manual-precision aid. Official v0.2 entity review uses
    # independently extracted candidates, added below.
    scores["fab_name_candidates"] = _name_candidates(scores["fab_spans"])
    scores["seg_fail"] = (not hyp_norm.strip()) or scores["cer_norm"] > SEG_FAIL_CER
    scores["correction_bucket"] = _correction_bucket(scores["cer_norm"])
    scores.update(_abstention(gold_norm.split(), hyp_norm.split()))
    # entity_annotated tracks annotation coverage separately from recall:
    # an annotated page with zero entities has entity_recall None but still
    # counts as covered for the §8 completeness requirement.
    scores["entity_annotated"] = entities is not None
    if entities is not None:
        scores.update(score_entities(entities, hyp_norm))
    return scores


# §5.6 allows an explicit "illegible" *statement*; up to this many residual
# characters of boilerplate around the abstention marker still count as clean
# ("This page is illegible." etc.), provided the marker is present at all.
ANNEX_BOILERPLATE_CHARS = 60
# Same idea for a single gold [unleserlich] span: a few chars of alignment
# bleed are tolerated, invented content ("unleserlich Hans Müller") is not.
SPAN_BOILERPLATE_CHARS = 15


def _abstention_residual(text: str) -> tuple[bool, int]:
    """(abstention phrase present, residual chars after removing it + punctuation)."""
    abstained = bool(normalization.ABSTENTION_RE.search(text))
    residual = normalization.ABSTENTION_RE.sub("", text)
    residual = re.sub(r"[\[\]().:,;!\s]+", "", residual)
    return abstained, len(residual)


def score_annex(hyp_text: str) -> dict:
    """§5.6 fabrication probes (unscored annex pages): correct output ~= abstention.

    Returns {abstention_ok: bool, hallucinated_chars: int} — deliberately a
    different shape from score_page(); the two never mix downstream."""
    hyp_scored = normalization.strip_hyp_markers(hyp_text)
    abstained, residual = _abstention_residual(normalization.normalize(hyp_scored))
    ok = residual == 0 or (abstained and residual <= ANNEX_BOILERPLATE_CHARS)
    return {"abstention_ok": ok, "hallucinated_chars": residual}


def _order_insensitive_cer(gold_text: str, hyp_text: str) -> float:
    """§5.2: optimal assignment of hypothesis lines to gold lines; unmatched
    lines cost their full length. Result is a CER over gold line characters."""
    ref_lines = normalization.norm_lines(gold_text)
    hyp_lines = normalization.norm_lines(hyp_text)
    ref_chars = sum(len(line) for line in ref_lines)
    if ref_chars == 0:
        return 0.0
    pair_costs = [[float(levenshtein(r, h)) for h in hyp_lines] for r in ref_lines]
    total = assignment_cost_with_unmatched(
        pair_costs,
        [float(len(r)) for r in ref_lines],
        [float(len(h)) for h in hyp_lines],
    )
    return total / ref_chars


def _name_candidates(spans: list[str]) -> list[str]:
    """Contiguous capitalized-token runs for manual entity-precision adjudication."""
    candidates: set[str] = set()
    for span in spans:
        run: list[str] = []
        for token in span.split():
            cleaned = token.strip(".,;:!?()[]")
            if _NAME_LIKE.match(cleaned):
                run.append(cleaned)
                continue
            if run:
                candidates.add(" ".join(run))
                run = []
        if run:
            candidates.add(" ".join(run))
    return sorted(candidates)


def _abstention(gold_tokens: list[str], hyp_tokens: list[str]) -> dict:
    """§5.6 over gold [unleserlich] spans: for each marker token, look at the
    hypothesis tokens aligned to it (substitutions plus adjacent insertions);
    correct behavior = nothing there, or an abstention statement."""
    marker_positions = [
        i for i, tok in enumerate(gold_tokens) if tok == normalization.ABSTENTION_MARK
    ]
    if not marker_positions:
        return {"abstention_spans": 0, "abstention_ok": None}
    aligned: dict[int, list[str]] = {i: [] for i in marker_positions}
    targets = set(marker_positions)
    last_ref = -1
    for op, ref_index, hyp_index in align_ops(gold_tokens, hyp_tokens):
        if op in (EQUAL, SUB):
            last_ref = ref_index
            if ref_index in targets and op == SUB:
                aligned[ref_index].append(hyp_tokens[hyp_index])
        elif op == INS and (last_ref in targets or (last_ref + 1) in targets):
            key = last_ref if last_ref in targets else last_ref + 1
            aligned[key].append(hyp_tokens[hyp_index])
        elif op == DEL:
            last_ref = ref_index
    ok = 0
    for position in marker_positions:
        window = " ".join(aligned[position])
        abstained, residual = _abstention_residual(window)
        # A marker plus invented content ("unleserlich Hans Müller") is NOT
        # correct abstention — the window must be substantively empty.
        if residual == 0 or (abstained and residual <= SPAN_BOILERPLATE_CHARS):
            ok += 1
    return {
        "abstention_spans": len(marker_positions),
        "abstention_ok": ok / len(marker_positions),
    }


def _correction_bucket(cer_norm: float) -> str:
    for bound, label in CORRECTION_BUCKETS:
        if cer_norm < bound:
            return label
    return ">30%"
