# Submitting results to the Kurrent Pages Benchmark v1.0

You run your engine on the 53 scored page images and send the outputs
privately. The maintainer scores them offline against the private ground truth
and publishes aggregates only. Your outputs and per-page scores are never
published (protocol §7, §11).

## Rules

- **One scored submission per engine per 30 days.** An engine is one model
  family from one submitter. Each submission names its engine version. The cap
  stops hill-climbing on the held-out set.
- **End-to-end only.** Raw page image in, page text out (protocol §1). Do not
  crop, deskew, or otherwise preprocess the images outside your engine.
- **No human in the loop.** No manual correction, selection between runs, or
  prompt tuning on the benchmark pages.
- **No training on the pages.** The dataset terms forbid training, fine-tuning,
  or model selection on the images, and publishing transcriptions of them.
- **A failed page counts against the engine.** A scored page without a text file
  scores as empty output (protocol §1).

## Get the images

Request access to the gated dataset `13fragments/kurrent-pages-v1` on
Hugging Face and accept its evaluation-only terms. Check every image against
[`gold/v1_pages.sha256`](gold/v1_pages.sha256) before you run:

```sh
cd <dataset dir>/images && shasum -a 256 -c <repo>/gold/v1_pages.sha256 --ignore-missing
```

The two annex pages (`A01`, `A02`) are not in the dataset. They are reported
only, and the bundle does not include them.

## Bundle format

One directory, sent as one `.zip` file:

```
<engine>_<version>/
  run.json
  pages/
    G01.txt
    G02.txt
    ...
```

- `pages/<page ID>.txt`: the engine's transcription of that page, UTF-8, as the
  engine produced it. Use the page IDs of `gold/selection.yml`. Line breaks are
  part of the text. Write `[unleserlich]` where the engine abstains (protocol
  §3.4).
- `run.json`:

```json
{
  "engine": "acme_htr",
  "engine_version": "2.1",
  "benchmark_version": "Kurrent Pages Benchmark v1.0",
  "description": "Model, weights or API version, prompt, decoding settings, hardware.",
  "submitter": "Name or organization (kept private)",
  "image_sha256": {"G01": "<sha256 of the image file your engine read>", "...": "..."},
  "length_stopped": ["<page IDs whose output stopped at the output token limit>"]
}
```

`engine` uses lowercase letters, digits, `_`, and `-`. `image_sha256` lists all
53 scored pages; each value must equal the hash in `gold/v1_pages.sha256`.
`length_stopped` lists the pages where generation stopped at a length limit: the
scorer removes a trailing repetition loop from those outputs only (protocol §10,
2026-10-16). Leave it empty if none.

## Send it

Send the `.zip` file to `kurrent-pages@13fragments.com`. Say whether the engine row may
name the submitter, and whether the engine is open (weights or code public) or
commercial.

## What gets published

The maintainer imports the bundle with `scripts/import_submission.py`, scores it
with the release harness (tag `v1.0.0`), and adds one row to
[`leaderboard/`](leaderboard/): per stratum, the page count, median and mean
`cer_norm`, median entity recall, and the segmentation-failure rate, plus the
same overall and on the §8 hard strata. You receive the same aggregates. No page
ID with a score, no per-page score, and no output text is published or returned.

Scores compare only within v1.0 (protocol §11).
