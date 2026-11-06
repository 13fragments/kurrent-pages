---
read_when: You cite the Kurrent Pages Benchmark v1.0, compare scores across versions, or prepare the next benchmark version.
---

# Kurrent Pages Benchmark v1.0 release notes

The Kurrent Pages Benchmark v1.0 is the first citable version of the benchmark. It is ground
truth (GT) v1.0, harness tag `v1.0.0`, and `BENCHMARK_PROTOCOL.md` with §10 up
to the tag date. Scores compare only within v1.0 (protocol §11).

## What is in the release

- **Protocol:** `BENCHMARK_PROTOCOL.md`, preregistered on 2026-07-05 before any GT
  or engine run, with every later change dated in §10.
- **Harness:** `harness/` and `scripts/` at tag `v1.0.0`. The scoring code is the
  code of `v1.0.0-rc1`, which rescored every leaderboard row.
- **Page manifest:** `gold/selection.yml`, `gold/candidates.yml`, and
  `gold/v1_pages.sha256` (55 images: 53 scored pages and 2 annex pages).
- **Leaderboard:** `leaderboard/` (JSON and Markdown), aggregates only.
- **Page images:** the 53 scored pages as a gated dataset on Hugging Face
  (`13fragments/kurrent-pages-v1`), evaluation-only terms.
- **Submissions:** `SUBMITTING.md`.

The GT, the entity annotations, every engine output on the benchmark pages, and
every per-page score stay private (protocol §7, §11).

## Ground-truth provenance (aggregate)

| Pages | Keying route |
|---|---|
| 36 | Kurrent and Sütterlin: two independent external keys (on 2 of these pages the second key came from a third keyer); the author adjudicated every disagreement against the scan. The primary key is v1.0 on all 36. |
| 2 | Kurrent trial pages: the primary keyer's key. |
| 7 | Degraded Fraktur (5) and Latin cursive (2): one external key, adjudicated by the author against the scan. |
| 8 | Early-modern hands: a specialist's key, adjudicated on 2026-09-14. |
| **53** | GT v1.0 text frozen on 2026-10-16. |

The author annotated persons, places, and dates on every scored page; the entity
lists were frozen on 2026-10-18 (53/53). Every external keyer worked under a
confidentiality and no-tools agreement (no OCR, HTR, AI, or cloud upload).

## Pages

53 scored pages from 20 source volumes in public collections; every scored page is CC0,
Public Domain Mark, or CC BY 4.0. Pages per primary stratum: suetterlin 13,
ugly_kurrent 12, twentieth_century_kurrent 6, degraded_fraktur 5,
nineteenth_c_civilian 5, mixed_print_handwriting 3, table_registry 3,
latin_cursive_1940s 2, marginalia 2, tidy_kurrent 2. The §8 hard-strata set
has 33 pages. `clean_fraktur` is empty in v1 (§9 note 1). The 2 annex pages are
reported only and are not in the image dataset.

## Changes since the freeze (§10 summary)

- **Conventions (2026-07 to 2026-10):** clarifications of the diplomatic
  transcription rules from the keyers' questions; no rule reversals.
- **GT production:** independent double-keying for the Kurrent and Sütterlin
  pages (2026-07-09); external key for Fraktur and Latin cursive (2026-07-28).
- **Engines (2026-09-24, 2026-10-31):** VLM repetition penalty 1.1; olmOCR-2 and
  Qwen3.5-4B added; frontier engines GPT-6-Astra and Claude Fable 5.1 added for
  reference readings.
- **Scoring (2026-10-16, 2026-10-18):** the loop guard scores token-limited VLM
  outputs without their trailing loop; the annex pages are reported only.
- **Gold use (2026-10-21):** guards against adaptive overfitting: model decisions
  on dev pages only, at most one sealed gold run per training-data round, and an
  external test set with every gold claim.
- **Release (2026-11-06):** roles in place of keyer names; gated images,
  private submissions, no fabrication examples from benchmark pages, and the
  early-modern pages count in v1.0.
- **Gate 2 (2026-11-06):** one sealed gold run per self-training round of the
  model track; the Round 0 gold run (two 1B engines and the Run 11 control) was
  pre-registered, run, and opened. Its rows are not on the v1.0 leaderboard. Two optional VLM engine keys, `image_only` and `vllm_xargs`,
  change only the requests of the engines that set them; scoring is unchanged.

## Rescore at the release harness

Every leaderboard row was rescored from its stored outputs at `v1.0.0-rc1`.
No published median changed (see `docs/release/RESCORE_V1.md`). The scoring code
of `v1.0.0` is that of `v1.0.0-rc1`; after rc1 only the engine request code in
`harness/engines/` changed (the two optional keys above).

## Known limits

- **Small strata.** Five strata have 2 or 3 pages. Their medians are indicative.
- **Serving-state noise.** VLM rows are single greedy runs. A serving-state change
  on the same hardware moved medians by about 0.02.
- **Fabrication (T3) is not adjudicated** for any engine. The leaderboard shows an
  automatic proxy only.
- **Entity lists have one annotator** (the author).
- **The author competes.** The author also trains a model that is scored here
  (VISION §6). The preregistered protocol, the sealed gold runs, and the gold-use
  guards are the controls.
- **Public sources.** Every page comes from a public scan. Anyone can transcribe
  the sources, so the held-out property depends on nobody publishing a
  transcription. One page (G32) has a documented caveat (§7).
- **Commercial rows.** The Transkribus rows ran on 2026-09-24 through the
  service; a later service version may score differently.
- **No public rescoring.** Without public GT, nobody else can rescore an engine.
  The harness, the manifest, and the source scans keep the method auditable.
