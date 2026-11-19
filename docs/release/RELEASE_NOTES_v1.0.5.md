---
read_when: You publish or cite release v1.0.5 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.5 release notes

Leaderboard and harness release. The benchmark version stays v1.0: the ground truth, the pages, the
prompts of existing engines, and the OCR metric definitions are those of v1.0.0, and no existing
score changed. OCR scores compare directly across v1.0.0 to v1.0.5.

## Changes since v1.0.4

- **Three new rows, run by the maintainer.** Each ran once on 2026-11-19 with the settings of its
  model card at a pinned revision (protocol §10).

  | Engine | `cer_norm` median | Hard strata median | Entity recall median |
  |---|---|---|---|
  | kraken-german-xix-v1 (`dh-unibe/kraken-german-xix-v1`, revision `945658d6`), kraken 7.0 | 0.292 | 0.309 | 0.400 |
  | LightOnOCR-3-1B (`lightonai/LightOnOCR-3-1B`, revision `23d54408`) | 0.359 | 0.363 | 0.500 |
  | LightOnOCR-3-4B (`lightonai/LightOnOCR-3-4B`, revision `b71010f0`) | 0.375 | 0.397 | 0.562 |

  LightOnOCR-3: page image only, temperature 0.2, top_p 0.9, a fixed seed, at most 4,096 tokens,
  no output map. The 4B model also gets the thumbnail step of its card's client (at most 2,048
  pixels per side). Each LightOnOCR-3 row is one sample. The two medians differ by less than the
  serving drift of about 0.02, so read them as level. kraken-german-xix-v1: the card's command, baseline segmentation and recognition in one call.
- **Maintainer runs.** Owners of open-weight models can ask the maintainer to run their model
  (`SUBMITTING.md`). The maintainer decides on each request, and the usual rules apply. The dataset
  card links the submission route.
- **Harness.** New opt-in keys for VLM engines: `top_p`, `seed`, `stop`, `skip_special_tokens`, and
  `server_max_tokens`. Every VLM reply now records its `finish_reason`. New image step
  `thumbnail_2048_png` and engine type `trocr_lines` (TrOCR line models behind kraken baseline
  segmentation). Engines without these keys send unchanged requests, so the earlier rows were not
  rescored.
- **Same ground truth.** The new rows were scored against GT v1.0: every ground-truth file, the
  entity lists, and the page selection have the hashes recorded at the v1.0 freeze.
- **Protocol.** §10 logs the maintainer runs of batch 1 and this release.
- **Not yet added.** Three TrOCR line models from the same batch (`dh-unibe/trocr-kurrent`,
  `dh-unibe/trocr-kurrent-XVI-XVII`, and `dh-unibe/trocr-german-kurrent-xvi-xix-from-kurrent-v2`)
  get their rows when their run is complete. DeepSeek-OCR made no gold request and moves to a later
  batch. No T3 check ran for the new rows.
