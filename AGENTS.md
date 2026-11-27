# Repository guardrails

- Benchmark-only repository: protocol, harness, public manifests, baselines,
  and synthetic/model-generated silver fixtures.
- Never add held-out images, gold transcriptions, gold entity annotations,
  freelancer correspondence, invoices, or agreements.
- `gold/` means public benchmark metadata only. Private targets belong in
  the private evaluation repository (the sibling checkout named in `README.md`).
- Never import or copy code from the model repository that needs access to held-out
  targets.
- Run `uv run python scripts/check_boundary.py` and `uv run pytest` before push.

## Benchmark separation (owner rule, D-2026-11-25-01)

The Kurrent Pages Benchmark ranks other people's models. Outside test sets test
ours. "Our models" means models published by the benchmark maintainer. The
decision and its amendment A1 are in the model repository (`DECISIONS.md`).

- Do not score our own models or checkpoints on the benchmark gold. This covers
  selection, gates, ablations, diagnostics, repeat runs, and drift controls.
  Use a third-party engine, such as `lighton_hgh_fp_v16`, as the drift control.
- One exception: at most one gold run per public release of a model. Choose the
  model on dev sets first. Then run gold once and record it in §10 of
  `BENCHMARK_PROTOCOL.md` and in the model repository's experiment log.
- Our models are tested on outside public page sets: the ICFHR 2016 (READ2016)
  Ratsprotokolle test pages (Zenodo 1164045), the Bullinger unseen-writer test
  split (Zenodo 19728926), and the CHURRO-DS German handwriting test pages. The
  frozen inputs and the exclusion rule are in the model repository
  (`experiments/EXP-20261115-outside-benchmarks.md`).
- On the leaderboard, our models appear only in the unranked section
  "Self-reported (benchmark maintainer)". Never rank one of our models, and
  never present one as the leader, in the leaderboard, the dataset card, the
  website, or a paper.
- If a plan step would run one of our models on gold beyond the one release run,
  refuse it and tell the owner.

