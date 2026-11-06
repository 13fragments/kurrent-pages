"""Sequence alignment primitives for the pre-registered metrics.

Pure stdlib. Levenshtein distance/ops power CER/WER/NLS and the fabrication
metric (protocol §5.1/§5.3); the Hungarian solver powers the order-insensitive
CER inside `ro_cost` (protocol §5.2).
"""

from __future__ import annotations

from typing import Sequence

# Alignment op codes: (op, ref_index, hyp_index); index is -1 for the absent side.
EQUAL, SUB, DEL, INS = "equal", "sub", "del", "ins"


def levenshtein(ref: Sequence, hyp: Sequence) -> int:
    """Edit distance between two sequences (str -> char level, list -> token level)."""
    if len(ref) < len(hyp):  # keep the DP row on the shorter sequence
        ref, hyp = hyp, ref
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + (r != h),  # substitution / match
                )
            )
        previous = current
    return previous[-1]


def align_ops(ref: Sequence, hyp: Sequence) -> list[tuple[str, int, int]]:
    """Full alignment backtrace, one op per aligned position.

    Among equal-cost optimal paths, the backtrace prefers insertions, then
    deletions, then diagonal moves. This selects the path family in which
    inserted material stays in maximal contiguous runs instead of being
    fragmented by scavenged single-character matches — the property the
    fabrication metric (§5.3 insertion runs) depends on. Cost is unaffected;
    all choices reconstruct a minimum-edit alignment.
    """
    rows, cols = len(ref) + 1, len(hyp) + 1
    dist = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        dist[i][0] = i
    for j in range(cols):
        dist[0][j] = j
    for i in range(1, rows):
        row, above = dist[i], dist[i - 1]
        r = ref[i - 1]
        for j in range(1, cols):
            row[j] = min(above[j] + 1, row[j - 1] + 1, above[j - 1] + (r != hyp[j - 1]))
    ops: list[tuple[str, int, int]] = []
    i, j = len(ref), len(hyp)
    while i > 0 or j > 0:
        if j > 0 and dist[i][j] == dist[i][j - 1] + 1:
            ops.append((INS, -1, j - 1))
            j -= 1
        elif i > 0 and dist[i][j] == dist[i - 1][j] + 1:
            ops.append((DEL, i - 1, -1))
            i -= 1
        else:
            ops.append((EQUAL if ref[i - 1] == hyp[j - 1] else SUB, i - 1, j - 1))
            i, j = i - 1, j - 1
    ops.reverse()
    return ops


def char_align_ops(ref: str, hyp: str) -> list[tuple[str, int, int]]:
    """align_ops for long strings via Hirschberg divide & conquer: O(n*m) time
    but linear memory, so full pages (thousands of chars) align without the
    quadratic backtrace matrix. Same op format/indices as align_ops."""
    return linear_align_ops(ref, hyp)


def linear_align_ops(ref: Sequence, hyp: Sequence) -> list[tuple[str, int, int]]:
    """Minimum-edit backtrace using linear memory for arbitrary sequences."""
    ops: list[tuple[str, int, int]] = []
    _hirschberg(ref, hyp, 0, 0, ops)
    return ops


# Below this cell count the quadratic backtrace matrix is cheap enough.
_DIRECT_DP_CELLS = 250_000


def _hirschberg(
    ref: Sequence, hyp: Sequence, ref_off: int, hyp_off: int, ops: list
) -> None:
    if len(ref) * len(hyp) <= _DIRECT_DP_CELLS or len(ref) <= 1:
        for op, i, j in align_ops(ref, hyp):
            ops.append(
                (op, i + ref_off if i >= 0 else -1, j + hyp_off if j >= 0 else -1)
            )
        return
    mid = len(ref) // 2
    left = _nw_last_row(ref[:mid], hyp)
    right = _nw_last_row(ref[mid:][::-1], hyp[::-1])
    split, best = 0, None
    for j in range(len(hyp) + 1):
        cost = left[j] + right[len(hyp) - j]
        if best is None or cost < best:
            best, split = cost, j
    _hirschberg(ref[:mid], hyp[:split], ref_off, hyp_off, ops)
    _hirschberg(ref[mid:], hyp[split:], ref_off + mid, hyp_off + split, ops)


def _nw_last_row(ref: Sequence, hyp: Sequence) -> list[int]:
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h))
            )
        previous = current
    return previous


def cer(ref: str, hyp: str) -> float:
    """Character error rate; empty reference scores 0.0 on empty hyp, else 1.0."""
    if not ref:
        return 0.0 if not hyp else 1.0
    return levenshtein(ref, hyp) / len(ref)


def wer(ref_tokens: Sequence[str], hyp_tokens: Sequence[str]) -> float:
    if not ref_tokens:
        return 0.0 if not hyp_tokens else 1.0
    return levenshtein(ref_tokens, hyp_tokens) / len(ref_tokens)


def nls(ref: str, hyp: str) -> float:
    """Normalized Levenshtein similarity, 1 - d/max(|ref|,|hyp|) (CHURRO comparability)."""
    longest = max(len(ref), len(hyp))
    if longest == 0:
        return 1.0
    return 1.0 - levenshtein(ref, hyp) / longest


def hungarian(cost: list[list[float]]) -> tuple[float, list[int]]:
    """Minimal-cost assignment on a square matrix (Kuhn–Munkres with potentials, O(n^3)).

    Returns (total_cost, assignment) where assignment[row] = column.
    """
    n = len(cost)
    if n == 0:
        return 0.0, []
    if any(len(row) != n for row in cost):
        raise ValueError("hungarian() needs a square matrix")
    INF = float("inf")
    u = [0.0] * (n + 1)  # row potentials, 1-indexed
    v = [0.0] * (n + 1)  # column potentials
    match = [0] * (n + 1)  # match[col] = row assigned to col; 0 = free
    for row in range(1, n + 1):
        match[0] = row
        j0 = 0
        minv = [INF] * (n + 1)
        way = [0] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = match[j0], INF, 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            for j in range(n + 1):
                if used[j]:
                    u[match[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if match[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            match[j0] = match[j1]
            j0 = j1
    assignment = [0] * n
    total = 0.0
    for j in range(1, n + 1):
        assignment[match[j] - 1] = j - 1
        total += cost[match[j] - 1][j - 1]
    return total, assignment


def assignment_cost_with_unmatched(
    pair_costs: list[list[float]],
    ref_unmatched: list[float],
    hyp_unmatched: list[float],
) -> float:
    """Optimal cost of assigning ref items to hyp items where leaving an item
    unmatched has a per-item cost (protocol §5.2: unmatched lines counted whole).

    Builds the classic (R+H)x(R+H) square: real costs top-left, per-ref dummy
    diagonal top-right, per-hyp dummy diagonal bottom-left, zeros bottom-right.
    """
    r, h = len(ref_unmatched), len(hyp_unmatched)
    if r == 0:
        return sum(hyp_unmatched)
    if h == 0:
        return sum(ref_unmatched)
    n = r + h
    big = sum(ref_unmatched) + sum(hyp_unmatched) + 1.0
    cost = [[0.0] * n for _ in range(n)]
    for i in range(r):
        for j in range(h):
            cost[i][j] = pair_costs[i][j]
        for j in range(r):
            cost[i][h + j] = ref_unmatched[i] if i == j else big
    for i in range(h):
        for j in range(h):
            cost[r + i][j] = hyp_unmatched[i] if i == j else big
    total, _ = hungarian(cost)
    return total
