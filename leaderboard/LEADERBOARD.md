# Leaderboard: Kurrent Pages Benchmark v1.0

Held-out set of 53 scored pages, ground truth v1.0, scored with harness v1.0.0-rc1 (rows added in v1.0.4: v1.0.4; in v1.0.5 and v1.0.6: v1.0.5). Aggregates only: no page scores and no outputs are published. `cer_norm` is the normalized character error rate (protocol §4, §5); lower is better. Entity recall is the share of gold persons, places, and dates found in the output (§5.5). Seg-fail is the share of pages with `cer_norm` above 0.75 or an empty output (§5.4). Licence: CC BY 4.0.

## Overall and hard strata

| Engine | Category | n | `cer_norm` median | `cer_norm` mean | Entity recall median | Seg-fail | Hard strata (33) `cer_norm` median | Hard strata entity recall median | Fabrication proxy, pages > 0.10 (unadjudicated) |
|---|---|---|---|---|---|---|---|---|---|
| Kurrent Transcriber 1B (13fragments/kurrent-transcriber-1b, v1) | open VLM, fine-tuned on Kurrent; published by the benchmark maintainer | 53 | **0.071** | 0.113 | 0.833 | 0% | 0.091 | 0.775 | 2 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), with the image step of Kurrent Transcriber 1B | open VLM, fine-tuned on Kurrent; run by the maintainer at the author's request | 53 | **0.075** | 0.135 | 0.833 | 0% | 0.085 | 0.750 | 2 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), uncropped scans, maintainer settings | open VLM, fine-tuned on Kurrent | 53 | **0.090** | 0.134 | 0.833 | 0% | 0.098 | 0.750 | 2 |
| Transkribus German Genius (Super Model, model ID 265149) | commercial reference, run 2026-09-24 | 53 | **0.131** | 0.186 | 0.850 | 2% | 0.128 | 0.825 | 2 |
| Transkribus Text Titan II (model ID 579509) | commercial reference, run 2026-09-24 | 53 | **0.169** | 0.214 | 0.857 | 2% | 0.150 | 0.804 | 1 |
| CHURRO 3B (stanford-oval/churro-3B) | open VLM, zero-shot | 53 | **0.258** | 0.412 | 0.588 | 4% | 0.266 | 0.508 | 4 |
| Kraken 7.0, kraken-german-xix-v1 model (dh-unibe/kraken-german-xix-v1, revision 945658d6) | open CRNN pipeline; run by the maintainer | 53 | **0.292** | 0.294 | 0.400 | 2% | 0.309 | 0.267 | 2 |
| LightOnOCR-3-1B (lightonai/LightOnOCR-3-1B, revision 23d54408), model card settings | open VLM, zero-shot; run by the maintainer | 53 | **0.359** | 0.380 | 0.500 | 6% | 0.363 | 0.333 | 5 |
| LightOnOCR-3-4B (lightonai/LightOnOCR-3-4B, revision b71010f0), model card settings | open VLM, zero-shot; run by the maintainer | 53 | **0.375** | 0.355 | 0.562 | 4% | 0.397 | 0.567 | 0 |
| olmOCR-2-7B-1025 (BF16) | open VLM, zero-shot | 53 | **0.440** | 0.385 | 0.533 | 2% | 0.440 | 0.485 | 0 |
| Qwen3.5-4B | open VLM, zero-shot | 53 | **0.461** | 0.428 | 0.400 | 11% | 0.461 | 0.342 | 0 |
| Qwen3.5-4B, script-hint prompt | open VLM, zero-shot | 53 | **0.465** | 0.612 | 0.471 | 9% | 0.467 | 0.450 | 3 |
| Qwen3-VL-4B-Instruct, script-hint prompt | open VLM, zero-shot | 53 | **0.540** | 0.587 | 0.250 | 13% | 0.572 | 0.250 | 2 |
| Qwen3-VL-4B-Instruct | open VLM, zero-shot | 53 | **0.581** | 0.601 | 0.250 | 13% | 0.585 | 0.232 | 3 |
| Kraken 7.0, rec_bohemica model (Zenodo 11673242) | open CRNN pipeline | 53 | **0.714** | 0.671 | 0.000 | 30% | 0.696 | 0.000 | 1 |
| Tesseract 5.5.2, deu_latf (tessdata_best) | open CRNN pipeline | 53 | **0.840** | 0.786 | 0.000 | 87% | 0.871 | 0.000 | 0 |
| Calamari 2.3.1, fraktur_historical | open CRNN pipeline | 53 | **0.907** | 0.836 | 0.000 | 89% | 0.914 | 0.000 | 0 |

## `cer_norm` median per stratum

Pages per stratum in brackets.

| Engine | suetterlin (13) | ugly_kurrent (12) | tidy_kurrent (2, indicative) | twentieth_century_kurrent (6) | nineteenth_c_civilian (5) | degraded_fraktur (5) | mixed_print_handwriting (3, indicative) | table_registry (3, indicative) | marginalia (2, indicative) | latin_cursive_1940s (2, indicative) |
|---|---|---|---|---|---|---|---|---|---|---|
| Kurrent Transcriber 1B (13fragments/kurrent-transcriber-1b, v1) | 0.027 | 0.168 | 0.071 | 0.171 | 0.071 | 0.006 | 0.210 | 0.128 | 0.185 | 0.064 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), with the image step of Kurrent Transcriber 1B | 0.045 | 0.203 | 0.067 | 0.214 | 0.068 | 0.013 | 0.274 | 0.075 | 0.210 | 0.135 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), uncropped scans, maintainer settings | 0.045 | 0.212 | 0.086 | 0.205 | 0.080 | 0.013 | 0.265 | 0.098 | 0.211 | 0.135 |
| Transkribus German Genius (Super Model, model ID 265149) | 0.080 | 0.168 | 0.087 | 0.275 | 0.133 | 0.013 | 0.247 | 0.128 | 0.174 | 0.079 |
| Transkribus Text Titan II (model ID 579509) | 0.077 | 0.211 | 0.145 | 0.199 | 0.147 | 0.016 | 0.372 | 0.150 | 0.269 | 0.184 |
| CHURRO 3B (stanford-oval/churro-3B) | 0.232 | 0.387 | 2.902 | 0.452 | 0.303 | 0.004 | 0.419 | 0.182 | 0.238 | 0.216 |
| Kraken 7.0, kraken-german-xix-v1 model (dh-unibe/kraken-german-xix-v1, revision 945658d6) | 0.198 | 0.338 | 0.113 | 0.362 | 0.169 | 0.065 | 0.449 | 0.188 | 0.454 | 0.387 |
| LightOnOCR-3-1B (lightonai/LightOnOCR-3-1B, revision 23d54408), model card settings | 0.286 | 0.523 | 0.428 | 0.486 | 0.402 | 0.008 | 0.563 | 0.247 | 0.601 | 0.199 |
| LightOnOCR-3-4B (lightonai/LightOnOCR-3-4B, revision b71010f0), model card settings | 0.225 | 0.451 | 0.471 | 0.419 | 0.411 | 0.011 | 0.611 | 0.222 | 0.537 | 0.137 |
| olmOCR-2-7B-1025 (BF16) | 0.291 | 0.507 | 0.653 | 0.516 | 0.509 | 0.007 | 0.482 | 0.254 | 0.541 | 0.124 |
| Qwen3.5-4B | 0.392 | 0.521 | 0.585 | 0.531 | 0.526 | 0.009 | 0.628 | 0.304 | 0.550 | 0.151 |
| Qwen3.5-4B, script-hint prompt | 0.388 | 0.545 | 0.561 | 0.563 | 0.535 | 0.009 | 0.516 | 0.299 | 0.560 | 0.151 |
| Qwen3-VL-4B-Instruct, script-hint prompt | 0.512 | 0.604 | 0.670 | 0.593 | 0.614 | 0.021 | 0.627 | 0.441 | 0.735 | 0.278 |
| Qwen3-VL-4B-Instruct | 0.472 | 0.631 | 0.775 | 0.603 | 0.706 | 0.021 | 0.627 | 0.458 | 0.738 | 0.253 |
| Kraken 7.0, rec_bohemica model (Zenodo 11673242) | 0.758 | 0.681 | 0.514 | 0.742 | 0.771 | 0.347 | 0.737 | 0.581 | 0.742 | 0.734 |
| Tesseract 5.5.2, deu_latf (tessdata_best) | 1.000 | 0.862 | 0.847 | 0.839 | 0.825 | 0.034 | 0.864 | 0.776 | 0.810 | 0.754 |
| Calamari 2.3.1, fraktur_historical | 0.886 | 0.913 | 0.911 | 0.938 | 0.919 | 0.360 | 0.942 | 0.914 | 0.853 | 0.744 |

## Entity recall median per stratum

Pages per stratum in brackets.

| Engine | suetterlin (13) | ugly_kurrent (12) | tidy_kurrent (2, indicative) | twentieth_century_kurrent (6) | nineteenth_c_civilian (5) | degraded_fraktur (5) | mixed_print_handwriting (3, indicative) | table_registry (3, indicative) | marginalia (2, indicative) | latin_cursive_1940s (2, indicative) |
|---|---|---|---|---|---|---|---|---|---|---|
| Kurrent Transcriber 1B (13fragments/kurrent-transcriber-1b, v1) | 1.000 | 0.333 | 1.000 | 0.750 | 0.800 | 1.000 | 0.571 | 0.857 | 0.429 | 0.722 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), with the image step of Kurrent Transcriber 1B | 0.929 | 0.370 | 1.000 | 0.917 | 0.875 | 0.869 | 0.444 | 0.857 | 0.143 | 0.694 |
| LightOnOCR-HGH (b-straub/LightOnOCR-3-1B-Historic-German-Handwriting, revision 47931fbe), uncropped scans, maintainer settings | 0.929 | 0.293 | 1.000 | 0.917 | 0.733 | 0.869 | 0.571 | 0.857 | 0.143 | 0.694 |
| Transkribus German Genius (Super Model, model ID 265149) | 1.000 | 0.758 | 1.000 | 0.633 | 0.875 | 0.917 | 0.571 | 0.857 | 0.714 | 0.694 |
| Transkribus Text Titan II (model ID 579509) | 1.000 | 0.321 | 1.000 | 0.550 | 0.875 | 0.929 | 0.429 | 0.750 | 0.143 | 0.528 |
| CHURRO 3B (stanford-oval/churro-3B) | 0.667 | 0.094 | 0.750 | 0.450 | 0.067 | 1.000 | 0.400 | 0.688 | 0.429 | 0.514 |
| Kraken 7.0, kraken-german-xix-v1 model (dh-unibe/kraken-german-xix-v1, revision 945658d6) | 0.333 | 0.105 | 0.750 | 0.400 | 0.500 | 0.653 | 0.143 | 0.429 | 0.000 | 0.083 |
| LightOnOCR-3-1B (lightonai/LightOnOCR-3-1B, revision 23d54408), model card settings | 0.500 | 0.000 | 1.000 | 0.333 | 0.667 | 0.792 | 0.286 | 0.750 | 0.000 | 0.444 |
| LightOnOCR-3-4B (lightonai/LightOnOCR-3-4B, revision b71010f0), model card settings | 0.667 | 0.000 | 0.500 | 0.367 | 0.688 | 0.853 | 0.222 | 0.667 | 0.000 | 0.375 |
| olmOCR-2-7B-1025 (BF16) | 0.643 | 0.038 | 0.500 | 0.350 | 0.533 | 0.980 | 0.400 | 0.562 | 0.000 | 0.542 |
| Qwen3.5-4B | 0.529 | 0.000 | 0.250 | 0.450 | 0.000 | 0.857 | 0.000 | 0.667 | 0.000 | 0.514 |
| Qwen3.5-4B, script-hint prompt | 0.667 | 0.000 | 0.250 | 0.250 | 0.000 | 0.815 | 0.111 | 0.667 | 0.143 | 0.444 |
| Qwen3-VL-4B-Instruct, script-hint prompt | 0.250 | 0.000 | 0.500 | 0.000 | 0.467 | 0.768 | 0.286 | 0.562 | 0.000 | 0.319 |
| Qwen3-VL-4B-Instruct | 0.250 | 0.000 | 0.500 | 0.000 | 0.000 | 0.768 | 0.200 | 0.571 | 0.000 | 0.431 |
| Kraken 7.0, rec_bohemica model (Zenodo 11673242) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.069 |
| Tesseract 5.5.2, deu_latf (tessdata_best) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.857 | 0.000 | 0.000 | 0.000 | 0.042 |
| Calamari 2.3.1, fraktur_historical | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.208 | 0.000 | 0.000 | 0.000 | 0.000 |

## Frontier reference

General-purpose frontier models, each a single run on one date through the vendor's command-line tool with the benchmark prompt and the page image only (no tools). Only page images were sent; model training on the data was off in both accounts. Vendor models change, so these rows are snapshots. They are not ranked with the main table.

| Engine | Category | n | `cer_norm` median | `cer_norm` mean | Entity recall median | Seg-fail | Hard strata (33) `cer_norm` median | Hard strata entity recall median | Fabrication proxy, pages > 0.10 (unadjudicated) |
|---|---|---|---|---|---|---|---|---|---|
| Claude Fable 5.1 (claude-fable-5-1, effort max, Claude Code CLI) | frontier VLM reference, run 2026-10-31 | 53 | **0.055** | 0.113 | 0.944 | 0% | 0.058 | 0.939 | 0 |
| GPT-6-Astra (gpt-6-astra, reasoning effort max, Codex CLI) | frontier VLM reference, run 2026-11-06 | 53 | **0.070** | 0.128 | 0.933 | 0% | 0.106 | 0.870 | 0 |

`cer_norm` median per stratum:

| Engine | suetterlin (13) | ugly_kurrent (12) | tidy_kurrent (2, indicative) | twentieth_century_kurrent (6) | nineteenth_c_civilian (5) | degraded_fraktur (5) | mixed_print_handwriting (3, indicative) | table_registry (3, indicative) | marginalia (2, indicative) | latin_cursive_1940s (2, indicative) |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Fable 5.1 (claude-fable-5-1, effort max, Claude Code CLI) | 0.011 | 0.139 | 0.081 | 0.132 | 0.088 | 0.003 | 0.228 | 0.083 | 0.180 | 0.027 |
| GPT-6-Astra (gpt-6-astra, reasoning effort max, Codex CLI) | 0.019 | 0.160 | 0.088 | 0.105 | 0.078 | 0.003 | 0.320 | 0.106 | 0.237 | 0.028 |

## Notes

- **Hard strata** are the §8 set of 33 pages: ugly_kurrent, suetterlin, table_registry,
  marginalia, and mixed_print_handwriting.
- **Small strata.** A stratum with fewer than 5 pages is indicative only. Read every
  median with its page count.
- **Fabrication.** The proxy column counts pages whose automatic long-insertion rate
  (v0.1) is above 0.10. It is a review diagnostic, not a fabrication verdict. T3, the
  adjudicated check for invented text (two AI model reviewers, §10, 2026-11-06), ran only
  for Kurrent Transcriber 1B and LightOnOCR-HGH in their run of 2026-11-17: each had 0 of
  53 pages with invented text, which meets the T3 pass rule of §10 (2026-11-06). No other
  row has a T3 result; the image-step row of LightOnOCR-HGH has none either. In
  `leaderboard.json`, `t3_status` is "unresolved" for every row:
  that harness field does not apply the §10 rule.
- **Reproducibility.** VLM rows are single runs in one serving state, with greedy decoding
  except the LightOnOCR-3 rows (one sample at temperature 0.2 with a fixed seed). On the
  maintainer's hardware, a serving-state change moved medians by about 0.02. Rows from
  one run compare exactly; rows from different runs carry that noise.
- **Image position.** The author of LightOnOCR-HGH observed that a shift of the image by
  half a patch (7 pixels) can change what models of this kind read, for example whether a
  faint first line is read. The maintainer has not measured this on the benchmark pages.
  Read small differences between closely related models with care.
- **Loop guard.** VLM outputs that stopped at the token limit are scored without their
  trailing repetition loop (§10, 2026-10-16). Kurrent Transcriber 1B also removes repeated
  runs (`run_removal_v1`, §10, 2026-11-13). `loop_policy_pages` in `leaderboard.json`
  counts the pages that this step changed.
- **Fine-tuned rows (added in v1.0.4).** Kurrent Transcriber 1B and LightOnOCR-HGH ran in
  one sealed run on 2026-11-17 (§10). Both used greedy decoding, at most 4,096 tokens, the
  page image only, a windowed repetition penalty of 1.1 over 20 tokens (the vLLM plugin
  ships with the Kurrent Transcriber 1B repository), and the LightOnOCR output map
  (`lighton-marks`). Kurrent Transcriber 1B also used its image step (`furniture_fp_v16`)
  and run removal, as its model card documents. For LightOnOCR-HGH, these are the
  maintainer's settings. The maintainer of this benchmark publishes Kurrent Transcriber 1B.
- **LightOnOCR-HGH, two rows (second row added in v1.0.6).** The first LightOnOCR-HGH row
  read the unchanged scans. At the model author's request, the second used the image step
  of Kurrent Transcriber 1B (`furniture_fp_v16`) on 2026-11-19 (§10). This step paints scan
  furniture outside the leaf and keeps the image size. It does not crop to the paper edge
  or split a double-page spread. Neither row has the input preparation of the model card.
- **LightOnOCR-HGH, result.** Median 0.075 with the image step, 0.090 without. Under the
  rule registered before the run, the two are level within the serving drift, so the result
  does not show that the image step helps. Kurrent Transcriber 1B ran in the same session
  as a drift control and scored 0.071, as recorded; the difference of 0.004 is also level.
  The image-step row had one loop-guard cut.
- **Maintainer runs (added in v1.0.5).** The maintainer ran LightOnOCR-3-1B,
  LightOnOCR-3-4B, and kraken-german-xix-v1 on 2026-11-19 (§10), each once, at a pinned
  revision with the settings of its model card. LightOnOCR-3: page image only, temperature
  0.2, top_p 0.9, a fixed seed, at most 4,096 tokens, and no output map; the 4B row also
  uses the card client's thumbnail step (at most 2,048 pixels per side). The two
  LightOnOCR-3 rows differ by less than the serving drift; read them as level.
  kraken-german-xix-v1: the card's command, kraken 7.0 baseline segmentation and
  recognition. Model owners can ask for a run with other settings (`SUBMITTING.md`).
- **Harness.** The rows added in v1.0.4 were scored with harness v1.0.4. It adds opt-in
  engine keys: an image step, run removal, and an output map (§10, 2026-11-13 and
  2026-11-15). The rows added in v1.0.5 were scored with harness v1.0.5. It adds opt-in
  sampling keys, an image step, and a line-model engine type (§10, 2026-11-19). The row
  added in v1.0.6 was scored with the same harness.
- **Illegible marks.** `cer_norm` scores `[unleserlich]` as ordinary text. Where the ground
  truth has text, the mark costs its 13 characters. So an engine that marks a spot instead
  of guessing pays this cost. LightOnOCR-HGH writes ▨, which its output map turns into
  `[unleserlich]`. A later protocol version may score the mark differently.
- **Unchanged rows.** For engines without the new keys, the OCR metrics and the public
  aggregates use unchanged code. The earlier rows keep their scores.
- **Annex pages** are reported only and are not a fabrication signal (§10, 2026-10-18).
- **Commercial references.** Transkribus rows ran on 2026-09-24 through the Transkribus
  service.
- **Frontier reference.** Claude Fable 5.1 and GPT-6-Astra ran at their highest
  effort setting through the Claude Code CLI and the Codex CLI on the maintainer's
  subscriptions. The rows record the run date; a later model version can score
  differently.
- **Submissions:** see [`SUBMITTING.md`](../SUBMITTING.md). One scored submission per
  engine per 30 days.
