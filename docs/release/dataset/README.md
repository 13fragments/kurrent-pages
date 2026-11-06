---
pretty_name: Kurrent Pages Benchmark v1.0 page images
license: other
license_name: per-image-source-licences-with-evaluation-only-access-terms
license_link: https://github.com/13fragments/kurrent-pages/blob/main/docs/release/dataset/TERMS.md
language:
  - de
  - la
task_categories:
  - image-to-text
size_categories:
  - n<1K
viewer: false
extra_gated_heading: "Evaluation-only access"
extra_gated_prompt: >-
  These are the held-out test pages of the Kurrent Pages Benchmark v1.0. You may use them
  only to evaluate an engine. Do not train, fine-tune, or select a model on them;
  do not redistribute them; do not publish transcriptions, engine outputs, or
  per-page scores of these pages. Full terms: https://github.com/13fragments/kurrent-pages/blob/main/docs/release/dataset/TERMS.md
extra_gated_fields:
  Name: text
  Affiliation: text
  Engine or project to evaluate: text
  I accept the evaluation-only access terms: checkbox
extra_gated_button_content: "Accept terms and request access"
---

# Kurrent Pages Benchmark v1.0 page images

The 53 scored page images of the Kurrent Pages Benchmark v1.0 held-out set: German
historical handwriting and print from 1565 to 1948 (Kurrent, Sütterlin,
degraded Fraktur, early-modern hands, Latin cursive, registers, marginalia).
Use them to run an engine end to end, page image in, text out, and submit the
outputs for scoring.

- Benchmark repository, protocol, harness, and leaderboard:
  `https://github.com/13fragments/kurrent-pages`
- How to submit: `SUBMITTING.md` in that repository.
- Ground truth and entity annotations are **not** published. Scoring happens
  offline against the private ground truth; only aggregates are published.

## Contents

| Path | Contents |
|---|---|
| `images/<page ID>.jpg` | processed single pages at native resolution: spreads split to the scored side, facing-page slivers cropped, no other preprocessing |
| `metadata.csv` | page ID, primary stratum, all strata, period, licence, source collection |
| `SHA256SUMS` | SHA-256 of every image; the same hashes as `gold/v1_pages.sha256` in the benchmark repository |
| `TERMS.md` | access terms |

Check the images before a run:

```sh
shasum -a 256 -c SHA256SUMS
```

Pages per primary stratum: suetterlin 13, ugly_kurrent 12,
twentieth_century_kurrent 6, degraded_fraktur 5, nineteenth_c_civilian 5,
mixed_print_handwriting 3, table_registry 3, latin_cursive_1940s 2,
marginalia 2, tidy_kurrent 2. The two unscored annex pages of the protocol are
not in this dataset.

## Licences and attribution

Each image keeps the licence of its source record (`metadata.csv`): CC0 (29
pages), Public Domain Mark (22 pages), CC BY 4.0 (2 pages). The access terms add
conditions for access through this repository; they do not relicense any image.

CC BY 4.0 attribution: Badische Landesbibliothek Karlsruhe, K 3228,1,
`https://nbn-resolving.de/urn:nbn:de:bsz:31-20456`, licensed under CC BY 4.0.
The images in this dataset are cropped single pages of that record.

Source collections and the selection record of every page are in
`gold/selection.yml` and `gold/candidates.yml` of the benchmark repository.

## Citation

Cite the benchmark release: Kurrent Pages Benchmark v1.0. Zenodo, 2026.
https://doi.org/10.5281/zenodo.24015417
