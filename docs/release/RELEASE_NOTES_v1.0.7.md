---
read_when: You publish or cite release v1.0.7 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.7 release notes

Leaderboard, harness, and protocol release. The benchmark version stays v1.0: the ground truth, the
pages, the prompts of existing engines, and the OCR metric definitions are those of v1.0.6, and no
existing score changed. OCR scores compare directly across v1.0.0 to v1.0.7.

## Changes since v1.0.6

- **Six open models, run by the maintainer.** Batch 3 of the maintainer runs (protocol §10,
  2026-11-25) adds six rows. Each model ran once, at a pinned revision, on the 53 held-out pages.

  | Engine | `cer_norm` median | Hard strata median | Entity recall median |
  |---|---|---|---|
  | Gemma 4 31B, benchmark zero-shot settings | 0.290 | 0.328 | 0.667 |
  | Qwen3.5-27B, benchmark zero-shot settings | 0.346 | 0.403 | 0.650 |
  | GLM-OCR, SDK 0.1.5 defaults | 0.538 | 0.538 | 0.250 |
  | dots.ocr, the authors' parser defaults | 0.748 | 0.664 | 0.400 |
  | DeepSeek-OCR-2, "Free OCR." prompt | 0.802 | 0.779 | 0.000 |
  | DeepSeek-OCR, "Free OCR." prompt | 0.868 | 0.868 | 0.000 |

  No new row has a lower median than CHURRO 3B (0.258). The best, Gemma 4 31B, is level with
  kraken-german-xix-v1 (0.292) within the serving drift of about 0.02. DeepSeek-OCR and
  DeepSeek-OCR-2 often repeat one short sequence until the token limit. dots.ocr writes picture
  regions as base64 image data; that text counts against the engine and explains its mean.
- **Not run.** Unlimited-OCR failed setup after two server starts: its remote code imports a
  function that transformers 5 removed, and the serving stack needs transformers 5. Chandra OCR 2
  was not run because its licence excludes users that offer a competing product. Unlimited-OCR-2
  needs its own serving build, so it was not run.
- **Kurrent Transcriber 1B is self-reported.** 13fragments maintains this benchmark and built
  Kurrent Transcriber 1B, so its row moved from the ranked table to a new section, "Self-reported
  (benchmark maintainer)". Its score did not change. This section has been on the public `main`
  branch since 2026-11-25; v1.0.7 is its first release. From this release, a maintainer model runs on
  the held-out pages at most once per public release, after it is chosen on development sets.
- **Repeat runs.** Four rows ran three more times on 2026-11-26. The three LightOnOCR rows gave the
  same median in all four runs, and CHURRO 3B gave medians from 0.236 to 0.263. Every pairwise order
  of the four rows held in every run, and no published score was replaced.
- **Drift control.** LightOnOCR-HGH with the image step reproduced its median of 0.075 in every
  batch-3 session where it ran.
- **Harness.** The engine type `pipeline_http` sends each page to the authors' own page pipeline
  and returns its text unchanged. With the key `text_first`, the prompt goes before the image, and
  the output map `unlimited-remove-det` applies the Unlimited-OCR card's output step. Existing
  engines send unchanged requests.
- **Same ground truth.** The new rows were scored against GT v1.0: every ground-truth file, the
  entity lists, and the page selection have the hashes recorded at the v1.0 freeze.
- **Protocol.** §10 logs batch 3, the repeat runs, and this release.
- **Already public since 2026-11-25.** A practice set of seven public pages for local pipeline tests
  (`practice/`), a section in the README that says how this benchmark differs from other test sets,
  and the website kurrentpages.org, which now shows release 1.0.7.
