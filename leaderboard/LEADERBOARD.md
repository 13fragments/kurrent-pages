# Leaderboard: Kurrent Pages Benchmark v1.0

Held-out set of 53 scored pages, ground truth v1.0, scored with harness `v1.0.0-rc1`. Aggregates only: no page scores and no outputs are published. `cer_norm` is the normalized character error rate (protocol §4, §5); lower is better. Entity recall is the share of gold persons, places, and dates found in the output (§5.5). Seg-fail is the share of pages with `cer_norm` above 0.75 or an empty output (§5.4). Licence: CC BY 4.0.

## Overall and hard strata

| Engine | Category | n | `cer_norm` median | `cer_norm` mean | Entity recall median | Seg-fail | Hard strata (33) `cer_norm` median | Hard strata entity recall median | Fabrication proxy, pages > 0.10 (unadjudicated) |
|---|---|---|---|---|---|---|---|---|---|
| Transkribus German Genius (Super Model, model ID 265149) | commercial reference, run 2026-09-24 | 53 | **0.131** | 0.186 | 0.850 | 2% | 0.128 | 0.825 | 2 |
| 13fragments 9B research preview (Qwen3.5-9B + LoRA, Run 11 step 800) | research preview, not released | 53 | **0.158** | 0.205 | 0.600 | 4% | 0.178 | 0.613 | 1 |
| Transkribus Text Titan II (model ID 579509) | commercial reference, run 2026-09-24 | 53 | **0.169** | 0.214 | 0.857 | 2% | 0.150 | 0.804 | 1 |
| CHURRO 3B (stanford-oval/churro-3B) | open VLM, zero-shot | 53 | **0.258** | 0.412 | 0.588 | 4% | 0.266 | 0.508 | 4 |
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
| Transkribus German Genius (Super Model, model ID 265149) | 0.080 | 0.168 | 0.087 | 0.275 | 0.133 | 0.013 | 0.247 | 0.128 | 0.174 | 0.079 |
| 13fragments 9B research preview (Qwen3.5-9B + LoRA, Run 11 step 800) | 0.105 | 0.281 | 0.146 | 0.241 | 0.119 | 0.004 | 0.300 | 0.155 | 0.246 | 0.132 |
| Transkribus Text Titan II (model ID 579509) | 0.077 | 0.211 | 0.145 | 0.199 | 0.147 | 0.016 | 0.372 | 0.150 | 0.269 | 0.184 |
| CHURRO 3B (stanford-oval/churro-3B) | 0.232 | 0.387 | 2.902 | 0.452 | 0.303 | 0.004 | 0.419 | 0.182 | 0.238 | 0.216 |
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
| Transkribus German Genius (Super Model, model ID 265149) | 1.000 | 0.758 | 1.000 | 0.633 | 0.875 | 0.917 | 0.571 | 0.857 | 0.714 | 0.694 |
| 13fragments 9B research preview (Qwen3.5-9B + LoRA, Run 11 step 800) | 0.600 | 0.529 | 1.000 | 0.283 | 0.500 | 1.000 | 0.600 | 0.667 | 0.286 | 0.403 |
| Transkribus Text Titan II (model ID 579509) | 1.000 | 0.321 | 1.000 | 0.550 | 0.875 | 0.929 | 0.429 | 0.750 | 0.143 | 0.528 |
| CHURRO 3B (stanford-oval/churro-3B) | 0.667 | 0.094 | 0.750 | 0.450 | 0.067 | 1.000 | 0.400 | 0.688 | 0.429 | 0.514 |
| olmOCR-2-7B-1025 (BF16) | 0.643 | 0.038 | 0.500 | 0.350 | 0.533 | 0.980 | 0.400 | 0.562 | 0.000 | 0.542 |
| Qwen3.5-4B | 0.529 | 0.000 | 0.250 | 0.450 | 0.000 | 0.857 | 0.000 | 0.667 | 0.000 | 0.514 |
| Qwen3.5-4B, script-hint prompt | 0.667 | 0.000 | 0.250 | 0.250 | 0.000 | 0.815 | 0.111 | 0.667 | 0.143 | 0.444 |
| Qwen3-VL-4B-Instruct, script-hint prompt | 0.250 | 0.000 | 0.500 | 0.000 | 0.467 | 0.768 | 0.286 | 0.562 | 0.000 | 0.319 |
| Qwen3-VL-4B-Instruct | 0.250 | 0.000 | 0.500 | 0.000 | 0.000 | 0.768 | 0.200 | 0.571 | 0.000 | 0.431 |
| Kraken 7.0, rec_bohemica model (Zenodo 11673242) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.069 |
| Tesseract 5.5.2, deu_latf (tessdata_best) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.857 | 0.000 | 0.000 | 0.000 | 0.042 |
| Calamari 2.3.1, fraktur_historical | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.208 | 0.000 | 0.000 | 0.000 | 0.000 |

## Notes

- **Hard strata** are the §8 set of 33 pages: ugly_kurrent, suetterlin, table_registry,
  marginalia, and mixed_print_handwriting.
- **Small strata.** A stratum with fewer than 5 pages is indicative only. Read every
  median with its page count.
- **Fabrication** is not adjudicated for any engine (T3 open). The proxy column counts
  pages whose automatic long-insertion rate (v0.1) is above 0.10. It is a review
  diagnostic, not a fabrication verdict.
- **Reproducibility.** VLM rows are single greedy runs in one serving state. On the
  maintainer's hardware, a serving-state change moved medians by about 0.02. Rows from
  one run compare exactly; rows from different runs carry that noise.
- **Loop guard.** VLM outputs that stopped at the token limit are scored without their
  trailing repetition loop (§10, 2026-10-16).
- **Annex pages** are reported only and are not a fabrication signal (§10, 2026-10-18).
- **Commercial references.** Transkribus rows ran on 2026-09-24 through the Transkribus
  service.
- **Research preview.** The 9B adapter is not released. A public release waits for
  the fabrication adjudication (T3).
- **Submissions:** see [`SUBMITTING.md`](../SUBMITTING.md). One scored submission per
  engine per 30 days.
