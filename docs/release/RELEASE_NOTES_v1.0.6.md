---
read_when: You publish or cite release v1.0.6 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.6 release notes

Leaderboard release. The benchmark version stays v1.0: the ground truth, the pages, the prompts,
the harness code, and the OCR metric definitions are those of v1.0.5, and no existing score changed.
OCR scores compare directly across v1.0.0 to v1.0.6.

## Changes since v1.0.5

- **A second LightOnOCR-HGH row.** The author of LightOnOCR-HGH pointed out that the first row read
  uncropped scans, while Kurrent Transcriber 1B used its image step. His model card says that the
  training pages were cropped to the paper edge. At his request, the maintainer ran the model again
  on 2026-11-19 with the image step of Kurrent Transcriber 1B (`furniture_fp_v16`), with the same
  weights and decoding (protocol §10).

  | Engine | `cer_norm` median | Hard strata median | Entity recall median |
  |---|---|---|---|
  | Kurrent Transcriber 1B (drift control of the same run, as recorded) | 0.071 | 0.091 | 0.833 |
  | LightOnOCR-HGH, with the image step of Kurrent Transcriber 1B | 0.075 | 0.085 | 0.833 |
  | LightOnOCR-HGH, uncropped scans (2026-11-17) | 0.090 | 0.098 | 0.833 |

  The image step paints scan furniture outside the leaf and keeps the image size. It does not crop
  to the paper edge, so neither row has the input preparation of the model card. Under the rule
  registered before the run, the two LightOnOCR-HGH rows are level within the serving drift of
  about 0.02, and the image-step row is level with Kurrent Transcriber 1B. The result does not show
  that the image step helps.
- **Leaderboard notes.** The first LightOnOCR-HGH row now says "uncropped scans, maintainer
  settings". New notes say that an image shift of half a patch can change what models of this kind
  read, and that `cer_norm` scores `[unleserlich]` as 13 characters where the ground truth has text.
- **Same ground truth.** The new row was scored against GT v1.0: every ground-truth file, the entity
  lists, and the page selection have the hashes recorded at the v1.0 freeze.
- **Protocol.** §10 logs the run and this release. The 30-day limit per engine was waived once for
  this run, because the model's author asked for it and its settings were fixed before the run.
- **Not yet added.** The three TrOCR line models of batch 1 get their rows when their run is
  complete. No T3 check ran for the new row; the T3 result stays with the first LightOnOCR-HGH row.
