"""Deterministic trust diagnostics and fabrication review candidates.

None of the automatic outputs in this module is an official fabrication label.
The headline fabrication metric is produced only by image-grounded adjudication.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib

from harness.alignment import (
    DEL,
    EQUAL,
    INS,
    SUB,
    align_ops,
    char_align_ops,
    linear_align_ops,
)

TRUST_DIAGNOSTIC_VERSION = "trust-diagnostics-v02-draft"
REVIEW_CANDIDATE_VERSION = "fabrication-review-v02-draft"
ALIGNMENT_VERSION = "levenshtein-hirschberg-ins-del-diag-v01"
LONG_INSERTION_MIN_WORDS = 5
LONG_INSERTION_WORD_FRACTION = 2 / 3
REPEAT_NGRAM_WORDS = 4
UNSUPPORTED_WORD_THRESHOLD = 0.3
CANDIDATE_MIN_WORDS = 4
CANDIDATE_MAX_WINDOW = 7


@dataclass(frozen=True)
class Word:
    text: str
    start: int
    end: int


def score_trust_diagnostics(gold_norm: str, hyp_norm: str) -> dict:
    """Score deterministic diagnostics and high-recall review candidates.

    The single global character alignment supplies the hypothesis-character
    error rate, omission rate, legacy long-insertion rate, and compound-split
    override used by the candidate generator.
    """
    char_ops = char_align_ops(gold_norm, hyp_norm)
    counts = {op: 0 for op in (EQUAL, SUB, DEL, INS)}
    exact_hyp = [False] * len(hyp_norm)
    inserted_hyp = [False] * len(hyp_norm)
    for op, _, hyp_index in char_ops:
        counts[op] += 1
        if hyp_index >= 0:
            exact_hyp[hyp_index] = op == EQUAL
            inserted_hyp[hyp_index] = op == INS

    hyp_denominator = counts[EQUAL] + counts[SUB] + counts[INS]
    gold_denominator = counts[EQUAL] + counts[SUB] + counts[DEL]
    legacy = _long_insertion_metrics(hyp_norm, inserted_hyp)
    candidates = _review_candidates(gold_norm, hyp_norm, exact_hyp)
    return {
        "trust_diagnostic_version": TRUST_DIAGNOSTIC_VERSION,
        "alignment_version": ALIGNMENT_VERSION,
        "alignment_counts": counts,
        "hypothesis_sha256": hashlib.sha256(hyp_norm.encode("utf-8")).hexdigest(),
        "hyp_chars": len(hyp_norm),
        "hyp_char_error": (
            (counts[SUB] + counts[INS]) / hyp_denominator if hyp_denominator else 0.0
        ),
        "omission_rate": counts[DEL] / gold_denominator if gold_denominator else 0.0,
        "excess_length_rate": (
            max(0, len(hyp_norm) - len(gold_norm)) / len(hyp_norm) if hyp_norm else 0.0
        ),
        "repeat_4gram_rate": _repeat_ngram_rate(hyp_norm, REPEAT_NGRAM_WORDS),
        **legacy,
        **candidates,
    }


def words_with_bounds(text: str) -> list[Word]:
    """Whitespace-delimited words with stable normalized-text offsets."""
    words: list[Word] = []
    start: int | None = None
    for index in range(len(text) + 1):
        inside = index < len(text) and not text[index].isspace()
        if inside and start is None:
            start = index
        elif not inside and start is not None:
            words.append(Word(text[start:index], start, index))
            start = None
    return words


def _long_insertion_metrics(hyp_norm: str, inserted: list[bool]) -> dict:
    """The exact v0.1 fabrication algorithm, retained under an honest name."""
    words = words_with_bounds(hyp_norm)
    insertion_words = [
        sum(inserted[word.start : word.end])
        >= (word.end - word.start) * LONG_INSERTION_WORD_FRACTION
        for word in words
    ]
    spans: list[str] = []
    chars = 0
    run_start: int | None = None
    for index in range(len(words) + 1):
        if index < len(words) and insertion_words[index]:
            if run_start is None:
                run_start = index
            continue
        if run_start is not None and index - run_start >= LONG_INSERTION_MIN_WORDS:
            text = hyp_norm[words[run_start].start : words[index - 1].end]
            spans.append(text)
            chars += len(text)
        run_start = None
    rate = chars / len(hyp_norm) if hyp_norm else 0.0
    return {
        "long_ins_rate_v01": rate,
        "long_ins_chars_v01": chars,
        "long_ins_spans_v01": spans,
        # Compatibility only. New reports name the diagnostic explicitly.
        "fab_rate": rate,
        "fab_chars": chars,
        "fab_spans": spans,
    }


def _review_candidates(gold_norm: str, hyp_norm: str, exact_hyp: list[bool]) -> dict:
    gold_words = words_with_bounds(gold_norm)
    hyp_words = words_with_bounds(hyp_norm)
    unsupported = [0.0] * len(hyp_words)
    evidence: list[dict] = [{} for _ in hyp_words]

    gold_tokens = [word.text for word in gold_words]
    hyp_tokens = [word.text for word in hyp_words]
    for op, gold_index, hyp_index in linear_align_ops(gold_tokens, hyp_tokens):
        if op == DEL:
            continue
        if op == EQUAL:
            unsupported[hyp_index] = 0.0
            evidence[hyp_index] = _word_evidence(
                op, gold_index, hyp_index, gold_words, hyp_words
            )
        elif op == INS:
            unsupported[hyp_index] = 1.0
            evidence[hyp_index] = _word_evidence(
                op, gold_index, hyp_index, gold_words, hyp_words
            )
        else:
            evidence[hyp_index] = _word_evidence(
                op, gold_index, hyp_index, gold_words, hyp_words
            )
            unsupported[hyp_index] = evidence[hyp_index]["unsupported_score_raw"]

    for index, word in enumerate(hyp_words):
        evidence[index]["global_char_exact_override"] = False
        if word.start < word.end and all(exact_hyp[word.start : word.end]):
            unsupported[index] = 0.0
            evidence[index]["global_char_exact_override"] = True
        evidence[index]["unsupported_score"] = unsupported[index]

    unsupported_indices = [
        index
        for index, score in enumerate(unsupported)
        if score >= UNSUPPORTED_WORD_THRESHOLD
    ]
    windows = [
        (
            unsupported_indices[index],
            unsupported_indices[index + CANDIDATE_MIN_WORDS - 1],
        )
        for index in range(len(unsupported_indices) - CANDIDATE_MIN_WORDS + 1)
        if unsupported_indices[index + CANDIDATE_MIN_WORDS - 1]
        - unsupported_indices[index]
        + 1
        <= CANDIDATE_MAX_WINDOW
    ]
    merged = _merge_overlapping(windows)
    spans = []
    chars = 0
    for first, last in merged:
        start, end = hyp_words[first].start, hyp_words[last].end
        chars += end - start
        spans.append(
            {
                "id": f"{REVIEW_CANDIDATE_VERSION}:{start}:{end}",
                "start": start,
                "end": end,
                "text": hyp_norm[start:end],
                "candidate_words": sum(
                    score >= UNSUPPORTED_WORD_THRESHOLD
                    for score in unsupported[first : last + 1]
                ),
                "total_words": last - first + 1,
                "words": [
                    {
                        "text": hyp_words[index].text,
                        "start": hyp_words[index].start,
                        "end": hyp_words[index].end,
                        **evidence[index],
                    }
                    for index in range(first, last + 1)
                ],
            }
        )
    return {
        "review_candidate_version": REVIEW_CANDIDATE_VERSION,
        "review_candidate_parameters": {
            "unsupported_word_threshold": UNSUPPORTED_WORD_THRESHOLD,
            "minimum_candidate_words": CANDIDATE_MIN_WORDS,
            "maximum_window_words": CANDIDATE_MAX_WINDOW,
        },
        "unsupported_word_rate_auto": (
            len(unsupported_indices) / len(hyp_words) if hyp_words else 0.0
        ),
        "review_candidate_rate_auto": chars / len(hyp_norm) if hyp_norm else 0.0,
        "review_candidate_chars_auto": chars,
        "review_candidate_spans_auto": spans,
    }


def _word_evidence(
    op: str,
    gold_index: int,
    hyp_index: int,
    gold_words: list[Word],
    hyp_words: list[Word],
) -> dict:
    hyp_word = hyp_words[hyp_index].text
    gold_word = gold_words[gold_index].text if gold_index >= 0 else None
    if op == EQUAL:
        counts = {EQUAL: len(hyp_word), SUB: 0, DEL: 0, INS: 0}
    elif op == INS:
        counts = {EQUAL: 0, SUB: 0, DEL: 0, INS: len(hyp_word)}
    else:
        counts = {name: 0 for name in (EQUAL, SUB, DEL, INS)}
        for char_op, _, _ in align_ops(gold_word or "", hyp_word):
            counts[char_op] += 1
    raw_score = (counts[SUB] + counts[INS]) / len(hyp_word) if hyp_word else 0.0
    return {
        "word_alignment_op": op,
        "char_counts": counts,
        "unsupported_score_raw": raw_score,
    }


def _merge_overlapping(windows: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _repeat_ngram_rate(text: str, size: int) -> float:
    words = text.split()
    if len(words) < size:
        return 0.0
    seen: set[tuple[str, ...]] = set()
    repeated_positions: set[int] = set()
    for start in range(len(words) - size + 1):
        ngram = tuple(word.casefold() for word in words[start : start + size])
        if ngram in seen:
            repeated_positions.update(range(start, start + size))
        else:
            seen.add(ngram)
    return len(repeated_positions) / len(words)
