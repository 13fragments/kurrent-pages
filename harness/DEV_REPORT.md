# Harness v0 — Dev Validation Report (silver dev set)

**Date:** 2026-07-07 · **Harness:** `harness-v0` worktree · **Tests:** 66/66 passing

## The dev set

`data/dev_silver/` — 24 real manuscript/print pages across 8 strata (suetterlin,
tidy/ugly/20c kurrent, degraded Fraktur, mixed print+handwriting, 19th-c civilian,
table registry). Ground truth is **silver**: model-generated (Fable) transcripts +
entity annotations, provenance-tagged `"SILVER - ... harness dev only, NEVER gold"`
in every `.meta.json`. Per VISION.md, silver is quarantined from evaluation: this set
exists solely to exercise the harness. **Nothing here touches private gold**, and no
numbers from this report gate anything.

## Method

For each perturbation profile, synthetic hypotheses were generated from GT (seed=42)
with harness-v0's perturbation profiles and scored against GT. Bonus: real tesseract 5
(deu, tessdata_fast) run on the page images via `harness run`. (This section is a
historical record of the harness-v0 shakedown; that perturbation tooling is not part of
this repo. The current-harness sweep is appended below.)

## Per-profile medians (24 pages)

| profile    | cer_norm | cer_dipl | wer_norm | fab_rate | ro_cost | entity recall (mean) | seg_fail |
|------------|---------:|---------:|---------:|---------:|--------:|---------------------:|---------:|
| light      | 0.0112   | 0.0111   | 0.0687   | 0.0000   | 0.0000  | 0.990                | 0/24     |
| heavy      | 0.2056   | 0.2050   | 0.5907   | 0.0000   | 0.0000  | 0.708                | 0/24     |
| fabricator | 0.1580   | 0.1563   | 0.1906   | 0.1259   | 0.0000  | 0.989                | 0/24     |
| reorder    | 0.5681   | 0.5681   | 0.7414   | 0.0000   | 0.5681  | 0.999                | 1/24     |
| empty      | 1.0000   | 1.0000   | 1.0000   | 0.0000   | 0.0000  | 0.250*               | 24/24    |

\* empty entity recall is 0.0 on every page with entities; the 0.25 mean comes
entirely from 6 pages with `n_entities == 0`, where recall is defined as 1.0.

## Sanity checks — all PASS

| check | expectation | observed | verdict |
|---|---|---|---|
| light CER | median cer_norm < 0.06 | 0.0112 | PASS |
| heavy CER | median in (0.08, 0.5) | 0.2056 | PASS |
| fabricator CER | > light | 0.158 > 0.0112 | PASS |
| fab_rate | fabricator clearly highest, median > 0.03; light ~0 | fab 0.1259 vs 0.0 everywhere else | PASS |
| ro_cost | reorder highest, median > 0.02; light ~0 | reorder 0.5681 vs 0.0 everywhere else | PASS |
| empty seg_fail | all pages seg_fail=true | 24/24 | PASS |
| entity recall | light mean > 0.8; empty = 0 except n_entities==0 → 1.0 | light 0.990 (min 0.875); empty exactly {0.0 where n>0, 1.0 where n==0} | PASS |

Metric separation is clean: fab_rate fires only for the fabricator, ro_cost only for
reorder, seg_fail only for empty (plus one reorder page, see limitations).

## Bonus: real tesseract run

tesseract 5.x, `deu` (tessdata_fast) — `deu.traineddata` was absent from the
homebrew install and had to be downloaded first.

| slice | n | median cer_norm | median entity recall |
|---|--:|---:|---:|
| **overall** | 24 | **0.841** | 0.0 (mean 0.31*) |
| degraded_fraktur | 3 | **0.128** | 0.556 |
| nineteenth_c_civilian | 1 | 0.797 | 0.0 |
| table_registry | 1 | 0.802 | 0.083 |
| twentieth_century_kurrent | 4 | 0.819 | 0.0 |
| ugly_kurrent | 7 | 0.870 | 1.0* (all n_entities==0) |
| tidy_kurrent | 2 | 0.879 | 0.0 |
| mixed_print_handwriting | 2 | 0.894 | 0.0 |
| suetterlin | 4 | 0.954 | 0.0 |

Exactly the expected shape: near-total failure on handwriting (CER 0.80–0.95,
21/24 seg_fail), plausible-ish on Fraktur print (0.128 with a fast German model and
no Fraktur traineddata). fab_rate 0.0 — tesseract garbles, it does not fabricate.
Recorded for calibration only.

## Known limitations

- **Silver GT**: transcripts are model-generated with flagged uncertain readings;
  absolute CER values carry GT noise. Fine for harness validation, not for claims.
- **Small n**: 24 pages, some strata n=1–2; per-stratum numbers are anecdotes.
- **One reorder seg_fail**: `dev_brugger_0085` (shortest page) trips the
  segmentation-failure heuristic under reorder — heuristic is conservative on short
  pages. Not a sanity violation; worth a threshold look before gold use.
- **Scoring speed**: fabricator/reorder scoring ~45–90 s for 24 pages (alignment on
  long/reshuffled hypotheses). Acceptable at this scale; may need attention for
  full-size sets.
- **Entity recall n_entities==0 convention**: recall defaults to 1.0 on pages with
  no entities (6/24), which inflates means (see empty and ugly_kurrent rows).
  Report entity recall micro-averaged or excluding empty pages for real evals.
- **Tesseract config**: tessdata_fast + `deu` only (no Fraktur model); its Fraktur
  number is a lower bound.
- Single seed (42); perturbation medians not variance-checked across seeds.

---

## Silver sweep on the current (main) harness — 2026-07-09

Re-ran the silver set through main's harness (not the old worktree harness) via the
new `scripts/build_silver_selection.py` adapter. Purpose unchanged: plumbing only,
gates nothing, GT is model-generated.

- **Pipeline validated end-to-end**: `run → score → report` green on all 24 pages with
  `mock` (per-stratum + Gate-0 machinery exercised) and with a real engine.
- **tesseract_fraktur (deu_latf, tessdata_best)** over 24 pages: median `cer_norm`
  **0.874** overall; the per-stratum split is the benchmark thesis in miniature —

  | stratum | n | cer_norm med | seg-fail | ent. recall |
  |---|---|---|---|---|
  | degraded_fraktur | 3 | 0.058 | 0% | 0.672 |
  | table_registry | 1 | 0.787 | 100% | 0.000 |
  | twentieth_century_kurrent | 4 | 0.839 | 100% | 0.075 |
  | ugly_kurrent | 7 | 0.874 | 100% | 0.000 |
  | tidy_kurrent | 2 | 0.875 | 100% | 0.000 |
  | nineteenth_c_civilian | 1 | 0.874 | 100% | 0.000 |
  | mixed_print_handwriting | 2 | 0.896 | 100% | 0.000 |
  | suetterlin | 4 | 0.941 | 100% | 0.000 |

  Tesseract's Fraktur model reads printed Fraktur (~6% CER) and fails completely on
  every handwriting stratum (100% seg-fail). Expected, and the desired discrimination.

**CLI footgun found:** `score`/`report` re-load the selection from the *global*
`--selection` flag, which defaults to GOLD. If you don't repeat the silver flags on
`score`/`report` (not just `run`), they silently mis-report against the 55-page gold
selection. Follow-up: bind `score`/`report` to the run's recorded selection (run.json),
or hard-error when the run's page IDs don't match the selection.

Model fetch: `curl -fsSL -o data/raw/models/tessdata/deu_latf.traineddata \
  https://github.com/tesseract-ocr/tessdata_best/raw/main/deu_latf.traineddata`
(gitignored under data/raw/).

## Full local engine sweep on silver — 2026-07-09 (all four engine types)

All 24 silver pages, median `cer_norm` (silver GT is model-generated → gates nothing):

| engine | median cer_norm | best stratum | reads what |
|---|---|---|---|
| kraken_kurrent (CRNN) | **0.716** | tidy_kurrent 0.487, degraded_fraktur 0.358 | Kurrent model → least-bad on handwriting |
| tesseract_fraktur (CRNN) | 0.874 | degraded_fraktur **0.058** | Fraktur model → excellent on print, fails handwriting |
| calamari_fraktur (CRNN) | 0.919 | degraded_fraktur 0.465 | Fraktur model, weaker; worst overall |
| evo_qwen25vl (VLM stand-in) | 1.000 | — | 13/24 exceed 4096 ctx; 11 hallucinate — plumbing only |
| mock | 1.000 | — | baseline |

**Key validation:** each engine does best on the script its model was trained for
(tesseract-Fraktur wins on Fraktur 0.058; kraken-Kurrent wins on handwriting 0.72;
calamari-Fraktur poor on handwriting). The strata cleanly separate engine×script
competency — the harness discriminates as designed. No Gate-0 kill (all hard-strata
medians ≫ 0.25; expected, and silver gates nothing regardless).

**CLI footgun FIXED** (commit 15b9e37): score/report now bind to the run's recorded
page IDs and hard-error on a disjoint selection instead of silently reporting gold.

**Engine reproducibility — resolved by `scripts/setup_engines.sh`:** kraken now lives in
the uv `engines` dependency group, Calamari uses persistent `.venv-calamari/`, and
all open-CRNN model downloads are hash-pinned. Historical context: the prior setup
depended on an ad hoc `.venv` kraken install and a `/tmp` Calamari venv symlink.

## VLM clean re-run (EVO max_model_len 16384) — 2026-07-09

After the context bump, all 24 pages fit (0 context errors). evo_qwen25vl median
`cer_norm` **0.607** — nominally the best engine on silver. **This headline is
misleading; do not read it as VLM superiority:**

- **Median hides catastrophic hallucination.** Per-stratum medians: mixed_print_handwriting
  **5.83**, twentieth_century_kurrent **2.42** (CER > 1 ⇒ the model emits fluent German
  several times longer than the actual page). Spot-check (Freiberg mining page): output is
  confident nonsense ("...grobgeschnittenes Tier von 5 mm Blutweite...") — pure hallucination.
- **Silver GT is model-generated (Fable).** Scoring one LLM's output against another LLM's
  transcription rewards LLM-style fluency/agreement, not faithful reading. The 0.607 partly
  measures model-to-model style agreement, NOT accuracy. A faithful HUMAN gold transcription
  would expose the hallucination as error.
- **3B stand-in, not the pre-registered Qwen3-VL-4B.**

**Validation result: mixed.** The harness caught four catastrophic repetition/over-generation
pages through CER, seg-fail, and high page-level `fab_rate`, but it did **not** identify the
shorter Freiburg fluent replacement as fabrication (`cer_norm` 0.731, `seg_fail=false`,
`fab_rate=0.000`). Across all 24 pages, 19 had `fab_rate=0`, one had 0.013, and four had
0.674–0.918; the mean was 0.134 while the reported median was 0.000. The visual spot-check,
not the metric, caught the Freiburg failure. CER>1 is an overlong-output symptom, not a
fabrication definition. Root cause and proposed post-silver/pre-gold redesign:
[`docs/FABRICATION_METRIC.md`](../docs/FABRICATION_METRIC.md).

## Fabrication implementation draft — 2026-07-10

The construct-validity defect above now has an executable, regression-tested draft:

- the historical long-insertion metric is preserved as `long_ins_rate_v01`;
- hypothesis-side error, omission, excess-length, repetition, and high-recall review
  candidates are reported as diagnostics rather than fabrication verdicts;
- independent date/amount/identifier/name candidates cover short high-risk claims;
- headline `*_adj` fields require two complete reviews bound to both the normalized
  hypothesis and the run's frozen image, with a distinct resolver for label,
  presence, or boundary disagreements;
- reports expose median/mean/micro/tail incidence, pooled reviewer reliability,
  decided entity precision, uncertainty coverage, excluded non-entity candidates,
  severe examples, and hand-cluster sensitivity;
- score artifacts no longer serialize aligned private-gold words or missed private
  entity strings, reviewer identities, or resolver identities.

This closes the harness failure, not the protocol decision. Candidate parameters,
the form, and T3 thresholds remain draft until the blinded pilot and dated v0.2
amendment. Current reports therefore label T3 `unresolved` and emit no PASS/FAIL.
Silver remains plumbing/calibration evidence only and yields no model-quality claim.
