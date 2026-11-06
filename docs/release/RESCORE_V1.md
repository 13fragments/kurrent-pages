---
read_when: You cite a leaderboard number, change the scoring code, or move the release tag.
---

# Release rescore at `v1.0.0-rc1` (blocker B6)

**Result: no published median changed.** Every leaderboard run was rescored from
its stored outputs with the harness at local tag `v1.0.0-rc1` (`cb479c3`). 116
published aggregates of the 18 runs listed below were compared; none differs by more than 0.001 (seg-fail
rates: more than their whole-percent rounding). Every overall, hard-strata, and
per-stratum aggregate of the stored score files (harness `9a04af7` rescored at
`da5ec8c`) is reproduced exactly. One more stored run, an external reference
reading that is not on the leaderboard, was rescored the same way with no
difference; it is not listed.

## Method

1. Each stored run under `evals/own_gold/runs/` was copied per engine (outputs and
   `run.json`, with `engines` reduced to that engine) to
   `evals/release_v1/rescore_rc1/`. The stored runs and scores did not change.
   No engine ran again.
2. Each copy was scored from a clean worktree of `v1.0.0-rc1` with
   `harness report --aggregates-only` against GT v1.0 and the frozen entity lists.
   All 19 exited 0 with no missing, unbound, or unannotated page.
3. The public outputs (19 `report_public.md` and 19 `aggregates.json`) contain no
   page ID: the built-in check passed for each, and an independent grep for
   `G01`–`G52b`, `A01`, and `A02` over all 38 files found none.
4. Published values: the Gate 0 table and the 2026-10-18 CHURRO rescore in
   `docs/GT_V1.md` of the private evaluation repository; model-track D-2026-10-18-04 and
   D-2026-10-21-01 (with its 2026-10-25 evidence), and EXP-20261023-9b-2mp.
   Published values have three decimals, so a difference up to 0.0005 is
   rounding.

## Comparison

"Other published aggregates" are the mean, entity recall, seg-fail rate, the §8
hard-strata values, and the per-stratum medians where a record publishes them.

| Run | Engine | Published median | Rescore median | Difference | Other published aggregates compared | Largest other difference |
|---|---|---|---|---|---|---|
| `20260924-112302_sealed` | `calamari_fraktur` | 0.907 | 0.9066 | -0.0004 | 6 (incl. 2 seg-fail %) | 0.0002 |
| `20260924-112302_sealed` | `churro` | 0.258 | 0.2583 | +0.0003 | 6 (incl. 2 seg-fail %) | 0.0005 |
| `20260924-112302_sealed` | `kraken_kurrent` | 0.714 | 0.7141 | +0.0001 | 6 (incl. 2 seg-fail %) | 0.0005 |
| `20260924-112302_sealed` | `olmocr2_7b` | 0.440 | 0.4399 | -0.0001 | 6 (incl. 2 seg-fail %) | 0.0003 |
| `20260924-112302_sealed` | `qwen35_4b` | 0.461 | 0.4608 | -0.0002 | 6 (incl. 2 seg-fail %) | 0.0003 |
| `20260924-112302_sealed` | `qwen35_4b_hint` | 0.465 | 0.4646 | -0.0004 | 6 (incl. 2 seg-fail %) | 0.0004 |
| `20260924-112302_sealed` | `qwen3vl_4b` | 0.581 | 0.5811 | +0.0001 | 6 (incl. 2 seg-fail %) | 0.0002 |
| `20260924-112302_sealed` | `qwen3vl_4b_hint` | 0.540 | 0.5395 | -0.0005 | 6 (incl. 2 seg-fail %) | 0.0004 |
| `20260924-112302_sealed` | `tesseract_fraktur` | 0.840 | 0.8404 | +0.0004 | 6 (incl. 2 seg-fail %) | 0.0004 |
| `20260924-112302_sealed` | `transkribus_german_genius` | 0.131 | 0.1313 | +0.0003 | 6 (incl. 2 seg-fail %) | 0.0003 |
| `20260924-112302_sealed` | `transkribus_text_titan_ii` | 0.169 | 0.1690 | +0.0000 | 6 (incl. 2 seg-fail %) | 0.0004 |
| `20261018-154538_gate1_sealed` | `gate1_run2_s1000` | 0.283 | 0.2827 | -0.0003 | 4 | 0.0004 |
| `20261018-154538_gate1_sealed` | `gate1_run3_s1200` | 0.274 | 0.2740 | -0.0000 | 4 | 0.0004 |
| `20261018-154538_gate1_sealed` | `qwen35_4b` | 0.445 | 0.4450 | +0.0000 | 4 | 0.0007 |
| `20261020-164104_gate1_9b_sealed` | `gate1_run7_s800` | 0.189 | 0.1889 | -0.0001 | 6 | 0.0005 |
| `20261020-164104_gate1_9b_sealed` | `qwen35_9b` | 0.389 | 0.3886 | -0.0004 | 4 | 0.0004 |
| `20261025-065703_gate1_run11_sealed` | `gate1_run11_s800` | 0.158 | 0.1581 | +0.0001 | 6 | 0.0005 |
| `20261025-065703_gate1_run11_sealed` | `qwen35_9b` | 0.389 | 0.3886 | -0.0004 | 4 | 0.0004 |

## Differences above 0.001

None.

## Notes

- The two `qwen35_9b` rows (2026-10-20 and 2026-10-25 runs) are equal on every
  aggregate, as recorded on 2026-10-25.
- The Gate 0 `qwen35_4b` row (0.461) and the Gate 1 4B run's `qwen35_4b` row
  (0.445) are two serving states; the leaderboard uses the Gate 0 row.
- Loop-guard cuts are unchanged: CHURRO 7, Qwen3.5-4B 7, Qwen3-VL-4B 13, Run 11
  step 800 1.
