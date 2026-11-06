---
read_when: You publish or cite release v1.0.3 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.3 release notes

Leaderboard release. The benchmark version stays v1.0: the ground truth, the pages, the
prompts, the scoring code, and every existing score are those of v1.0.0, so scores
compare directly across v1.0.0 to v1.0.3.

## Changes since v1.0.2

- **Frontier reference section.** The leaderboard has a new section for general-purpose
  frontier models. It is not ranked with the main table. Each row is a single run on
  one date through the vendor's command-line tool, at the highest effort setting, with
  the benchmark prompt and the page image only (no tools). Only page images were sent;
  model training on the data was off in both accounts. Vendor models change, so the
  rows are snapshots.

  | Engine | Run | `cer_norm` median | Entity recall median |
  |---|---|---|---|
  | Claude Fable 5.1 (effort max, Claude Code CLI) | 2026-10-31 | 0.055 | 0.944 |
  | GPT-6-Astra (reasoning effort max, Codex CLI) | 2026-11-06 | 0.070 | 0.933 |

- **9B row removed.** "13fragments 9B (internal, Run 11)" was an internal model-track
  run. That model will not be released, so the row is no longer on the leaderboard.
  Releases v1.0.0 to v1.0.2 keep it.
- **Leaderboard page.** The Hugging Face leaderboard page shows the frontier section.
- **Protocol.** §10 logs the sealed GPT-6-Astra gold run and its opening, each before any
  of its output was opened or scored.
