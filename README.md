# Kurrent Pages Benchmark

Held-out benchmark for end-to-end transcription of mixed German historical
documents: Kurrent, Sütterlin, degraded Fraktur, early-modern hands, registers,
and marginalia from 1565 to 1948. An engine gets a raw page image and returns the
page text. The repository holds the preregistered protocol, the public page
manifest, the evaluation harness, the engine adapters, and the leaderboard. It
holds no ground truth: the 53 scored pages are scored offline against a private,
double-keyed transcription.

**Release: Kurrent Pages Benchmark v1.0** = ground truth v1.0 + harness tag `v1.0.0` +
`BENCHMARK_PROTOCOL.md` with §10 up to the tag date.

| Document | Contents |
|---|---|
| [`leaderboard/LEADERBOARD.md`](leaderboard/LEADERBOARD.md) | per-engine and per-stratum aggregates |
| [`SUBMITTING.md`](SUBMITTING.md) | how to get the page images and submit outputs |
| [`BENCHMARK_PROTOCOL.md`](BENCHMARK_PROTOCOL.md) | the frozen protocol and its dated amendment log (§10) |
| [`docs/release/RELEASE_NOTES_v1.0.md`](docs/release/RELEASE_NOTES_v1.0.md) | ground-truth provenance, harness tag, known limits |
| [`CHANGELOG.md`](CHANGELOG.md) | harness changes |

`VISION.md` is retained as a frozen context snapshot because the preregistered
protocol cites its sections; the evolving model plan lives in a private model
repository.

## Repositories

- [`13fragments/kurrent-pages`](https://github.com/13fragments/kurrent-pages): this
  protocol and harness; public.
- The model repository (private): training corpus, synthesis, and model work;
  never receives held-out evaluation assets.
- The private evaluation repository: images, transcriptions, annotations, and
  transcriber operations.
- The archive repository (private): original mixed repository history.

See [docs/REPOSITORY_BOUNDARIES.md](docs/REPOSITORY_BOUNDARIES.md) before moving
data between repositories.

## Quick start

```sh
uv sync
uv run pytest
uv run python scripts/check_boundary.py
uv run python -m harness list-pages
```

The private evaluation checkout defaults to the sibling directory
`../benchmark-eval-private`. Override it with `BENCHMARK_EVAL_ROOT`:

```sh
BENCHMARK_EVAL_ROOT=/secure/benchmark-eval-private uv run python -m harness check
```

Gold images, transcriptions, and entity annotations are read from that private
root. Baseline weights stay gitignored under `data/raw/models/`; silver fixtures
may live under `data/dev_silver/`.

Score a stored run and write the public aggregates (no page IDs, page scores, or
text):

```sh
uv run python -m harness report --run-dir evals/own_gold/runs/<id> --aggregates-only --out <dir>
```

## Licence

Copyright 2026 the Kurrent Pages Benchmark authors.

| Path | Licence |
|---|---|
| `harness/`, `scripts/`, `tests/`, `configs/`, `deploy/`, `pyproject.toml`, `uv.lock` | Apache License 2.0 ([`LICENSE`](LICENSE)) |
| `BENCHMARK_PROTOCOL.md`, `VISION.md`, `README.md`, `CHANGELOG.md`, `SUBMITTING.md`, `docs/`, `gold/` (page manifest, source links, hashes), `leaderboard/` | Creative Commons Attribution 4.0 International ([`LICENSE-docs`](LICENSE-docs)) |

The benchmark page images are not in this repository. Each image keeps the
licence of its source record (CC0, Public Domain Mark, or CC BY 4.0), which
`gold/selection.yml` records per page. The gold transcriptions and entity
annotations are not published (protocol §7, §11).

## Citation

Kurrent Pages Benchmark v1.0, `<zenodo-doi>`.
