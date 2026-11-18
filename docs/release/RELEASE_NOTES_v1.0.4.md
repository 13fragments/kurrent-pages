---
read_when: You publish or cite release v1.0.4 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.4 release notes

Leaderboard and harness release. The benchmark version stays v1.0: the ground truth, the pages, the
prompts of existing engines, and the OCR metric definitions are those of v1.0.0, and no existing
score changed. OCR scores compare directly across v1.0.0 to v1.0.4. T3 scoring changed (see Harness).

## Changes since v1.0.3

- **Two new rows.** Both come from one sealed gold run on 2026-11-17 (protocol §10).

  | Engine | `cer_norm` median | Hard strata median | Entity recall median |
  |---|---|---|---|
  | Kurrent Transcriber 1B (`13fragments/kurrent-transcriber-1b`, v1) | 0.071 | 0.091 | 0.833 |
  | LightOnOCR-HGH (`b-straub/LightOnOCR-3-1B-Historic-German-Handwriting`, revision `47931fbe`) | 0.090 | 0.098 | 0.833 |

  Both rows use greedy decoding, at most 4,096 tokens, the page image only, a windowed repetition
  penalty of 1.1 over 20 tokens, and the LightOnOCR output map. Kurrent Transcriber 1B also uses its
  image step and run removal, as its model card documents. For LightOnOCR-HGH, these are the
  maintainer's settings; its author's settings can differ.
- **Disclosure.** 13fragments maintains this benchmark and publishes Kurrent Transcriber 1B. The
  row says so in its category.
- **Invented text.** The T3 check (two AI model reviewers) ran for both new rows: 0 of 53 pages with
  invented text each, which meets the T3 pass rule of §10 (2026-11-06). No other row has a T3 result.
- **Harness.** New opt-in engine keys, each logged in §10 before its first gold run: an image step
  (`preprocess`), run removal (`loop_policy`), an output map (`output_map`), a system message
  (`system_prompt`), and server-side sampling (`server_sampling`). For engines without these keys,
  the OCR metrics and the public aggregates use unchanged code, so the earlier rows were not
  rescored. T3 scoring now exempts a bracketed abstention mark (`t3-v2-abstention-mark`).
- **Same ground truth.** The new rows were scored against GT v1.0: every ground-truth file, the
  entity lists, and the page selection have the hashes recorded at the v1.0 freeze.
- **Protocol.** §3.2 item 9: scan furniture (colour charts, rulers, digitization footers) is not
  transcribed. The owner checked the ground truth against it: 0 pages changed. §1 allows one fixed
  image step per engine entry. §10 logs the gold runs and protocol decisions since v1.0.3, including
  the T3 method with two AI model reviewers.
- **T3 documents.** `docs/T3_MODEL_REVIEW.md`, the reviewer instructions, and the two review scripts
  are now public.
- **Not added.** CHURRO 3B with its own settings has no row: its server did not start in that run.
  Models that are not released get no row.
