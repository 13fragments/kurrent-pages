---
title: Kurrent Pages Leaderboard
emoji: 📜
colorFrom: yellow
colorTo: red
sdk: static
pinned: false
license: cc-by-4.0
short_description: HTR leaderboard for German Kurrent and Sütterlin pages
tags:
  - leaderboard
  - benchmark
  - htr
  - ocr
  - handwritten-text-recognition
  - historical-documents
  - kurrent
---

# Kurrent Pages Leaderboard

The leaderboard of the Kurrent Pages Benchmark v1.0: 53 held-out pages of German
handwriting and print from 1565 to 1948.

The ground truth is not published, so no model can have it in its training
data. The pages come from 20 volumes in 10 strata. With about 1,700 lines, the
set is as large as the READ 2016 test set, which publishes its transcriptions
and comes from one series of minutes.

The page loads `leaderboard/leaderboard.json` from
<https://github.com/13fragments/kurrent-pages> at view time. To change the rows,
change that file. This Space needs no rebuild.

- Benchmark website: <https://kurrentpages.org/>
- Benchmark, protocol, and harness: <https://github.com/13fragments/kurrent-pages>
- Page images (gated, evaluation only): <https://huggingface.co/datasets/13fragments/kurrent-pages-v1>
- Citation: <https://doi.org/10.5281/zenodo.24015417>

Leaderboard data: CC BY 4.0.
