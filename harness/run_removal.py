"""Run-only loop removal for engines that opt in (protocol §10, 2026-11-13; key `loop_policy: run_removal_v1`).

A copy of rule R2 of the model track's `scripts/loop_cut.py` (sha256 22ff27cb2b651afa57cb6058fd2a26e345f89bad8445307de4aac56bf57aaa29;
evidence EXP-20261107-loop-cut-stage-b): a run is a block of 20 to 400 code points that occurs at least 4 times in a
row, exact after Unicode NFC. The earliest run is removed with all its copies; the two sides are joined by one
newline if the removed span held a newline, else by one space, and by nothing if a side is empty; the result is
stripped. This repeats until no run is left.

Order for an engine with the key (`removed_text`): an output that reached the token limit gets the loop guard of
§10 2026-10-16 alone (`harness/loop_guard.py`), unchanged; any other output is NFC-normalized and loses its runs if
it holds one; an output without a run is scored as recorded. Engines without the key never reach this module.
numpy is imported only here, on that path.
"""

from __future__ import annotations

import unicodedata

POLICIES = ("run_removal_v1",)
R2_MIN_BLOCK = 20
R2_MAX_BLOCK = 400
R2_MIN_COPIES = 4


def removed_text(text: str) -> str | None:
    """The text without its runs (after NFC), or None when it holds no run."""
    return _r2(unicodedata.normalize("NFC", text))


def _r2(text: str) -> str | None:
    """Remove periodic runs; the earliest run first, its shortest period, then search again."""
    changed = False
    while True:
        run = _first_run(text)
        if run is None:
            return text if changed else None
        start, end = run
        before, after = text[:start].rstrip(" "), text[end:].lstrip(" ")
        joiner = "\n" if "\n" in text[start:end] else " "
        text = (before + joiner + after).strip() if before and after else (before + after).strip()
        changed = True


def _first_run(text: str) -> tuple[int, int] | None:
    import numpy as np

    codes = np.frombuffer(text.encode("utf-32-le"), dtype=np.uint32)
    n = len(codes)
    best = None
    for period in range(R2_MIN_BLOCK, min(R2_MAX_BLOCK, n // R2_MIN_COPIES) + 1):
        equal = codes[:-period] == codes[period:]
        need = (R2_MIN_COPIES - 1) * period  # equal positions of a run with R2_MIN_COPIES copies
        padded = np.concatenate(([False], equal, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        for start, stop in zip(edges[::2], edges[1::2]):
            if stop - start >= need:
                span = (int(start), int(stop) + period)
                if best is None or span[0] < best[0]:
                    best = span
                break
    return best
