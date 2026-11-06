from itertools import permutations
from random import Random

from harness.alignment import (
    INS,
    align_ops,
    assignment_cost_with_unmatched,
    cer,
    hungarian,
    levenshtein,
    linear_align_ops,
    nls,
    wer,
)


def test_levenshtein_known_cases():
    assert levenshtein("", "") == 0
    assert levenshtein("abc", "abc") == 0
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("flaw", "lawn") == 2
    assert levenshtein(["ein", "Haus"], ["ein", "Maus"]) == 1


def test_cer_wer_nls():
    assert cer("abcd", "abcd") == 0.0
    assert cer("abcd", "abed") == 0.25
    assert cer("", "") == 0.0
    assert cer("", "x") == 1.0
    assert wer("das alte Haus".split(), "das neue Haus".split()) == 1 / 3
    assert nls("abcd", "abcd") == 1.0
    assert nls("abcd", "") == 0.0


def test_align_ops_reconstructs_distance():
    ref, hyp = "Verſammlung", "Versammlung"
    ops = align_ops(ref, hyp)
    edits = sum(1 for op, _, _ in ops if op != "equal")
    assert edits == levenshtein(ref, hyp)


def test_align_ops_groups_insertions():
    ref = "a b c".split()
    hyp = "a x y z b c".split()
    ops = align_ops(ref, hyp)
    ins_run = [op for op in ops if op[0] == INS]
    assert len(ins_run) == 3


def test_char_align_ops_matches_direct_dp():
    from random import Random

    from harness.alignment import char_align_ops

    rng = Random(7)
    alphabet = "abcde "
    for _ in range(10):
        ref = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        hyp = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 120)))
        ops = char_align_ops(ref, hyp)
        edits = sum(1 for op, _, _ in ops if op != "equal")
        assert edits == levenshtein(ref, hyp)
        # ops must reconstruct hyp from ref
        rebuilt = "".join(
            hyp[j] if op in ("equal", "sub", INS) else "" for op, _, j in ops
        )
        assert rebuilt == hyp


def test_linear_alignment_handles_long_token_overgeneration():
    ref = [f"gold-{index}" for index in range(300)]
    hyp = [*ref, *[f"extra-{index}" for index in range(1_000)]]
    ops = linear_align_ops(ref, hyp)
    assert sum(op == INS for op, _, _ in ops) == 1_000
    assert len(ops) == len(hyp)


def _brute_force(cost):
    n = len(cost)
    return min(sum(cost[i][p[i]] for i in range(n)) for p in permutations(range(n)))


def test_hungarian_matches_brute_force():
    rng = Random(42)
    for _ in range(25):
        n = rng.randint(1, 5)
        cost = [[rng.uniform(0, 10) for _ in range(n)] for _ in range(n)]
        total, assignment = hungarian(cost)
        assert sorted(assignment) == list(range(n))
        assert abs(total - _brute_force(cost)) < 1e-9


def test_assignment_with_unmatched_prefers_cheap_matches():
    # Two ref lines, one hyp line identical to ref[0]: match it, pay ref[1] whole.
    pair = [[0.0], [8.0]]
    total = assignment_cost_with_unmatched(pair, [5.0, 6.0], [5.0])
    assert total == 6.0


def test_assignment_with_unmatched_empty_sides():
    assert assignment_cost_with_unmatched([], [], [3.0, 4.0]) == 7.0
    assert assignment_cost_with_unmatched([[]], [2.0], []) == 2.0
