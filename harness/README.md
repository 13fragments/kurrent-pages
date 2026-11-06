# Benchmark harness

Implements BENCHMARK_PROTOCOL.md v0.1-freeze end to end: raw page image →
engine → normalization layers → pre-registered metrics → report.

## Quickstart

```sh
uv sync                       # pyyaml (+ dev: pytest, pillow)
uv run pytest                 # metric + pipeline tests
uv run python -m harness check         # freeze hashes, GT coverage, engine availability
uv run python -m harness list-pages
uv run python -m harness run --engines tesseract_fraktur,qwen3vl_4b --label gate0
uv run python -m harness score  --run-dir evals/own_gold/runs/<id>
uv run python -m harness adjudication-templates --run-dir evals/own_gold/runs/<id>
uv run python -m harness report --run-dir evals/own_gold/runs/<id>
```

Engines are configured in `configs/engines.yml`; the two VLM prompts under
`configs/prompts/` are pre-registered (protocol §6) and must not be edited
after the first scored run.

## Expected data layout

```
$BENCHMARK_EVAL_ROOT/data/benchmark_gold/v1_pages/{GID}.jpg
                                frozen private images (hashes in gold/v1_pages.sha256)
$BENCHMARK_EVAL_ROOT/data/benchmark_gold/gt/{GID}.txt
                                private diplomatic GT, protocol §3.2
$BENCHMARK_EVAL_ROOT/data/benchmark_gold/entities/{GID}.yml
                                private entity annotations
data/raw/models/…               local baseline weights (gitignored)
```

`BENCHMARK_EVAL_ROOT` defaults to the sibling `../benchmark-eval-private` checkout.

Run results land in `evals/own_gold/runs/<timestamp>_<label>/` with
`run.json` (engine versions + configs), `outputs/`, `scores/`, `report.md`.
Runs are resumable: re-invoking `run` with `--run-dir` skips existing outputs.

## Fabrication review draft

The post-silver fabrication redesign is implemented as an executable draft; see
[`docs/FABRICATION_METRIC.md`](../docs/FABRICATION_METRIC.md). Automatic trust
fields and review candidates are diagnostics, never fabrication verdicts. T3
stays unresolved until a blinded pilot freezes the candidate parameters, form,
report fields, and thresholds through a protocol amendment.

`adjudication-templates` creates one normalized-hypothesis- and frozen-image-bound
coordinator form per scored engine/page only when output, transcription GT,
entity-annotation, and image-hash coverage are complete. It never overwrites an
existing form. Each completed form requires:

1. two distinct reviewers who each inspected the full page, labeled every automatic
   span/entity candidate, and recorded any missed span/entity;
2. a resolved consensus covering every automatic and reviewer-added claim;
3. a distinct third resolver whenever labels, presence, or boundaries disagree.

After review, rerun `score` and `report`. Reports pool reviewer confusion/marginal
counts across pages before calculating label Cohen's kappa, and report exact
boundary/kind-aware raw agreement separately. They show fabrication tails, decided
entity precision plus uncertainty coverage, excluded non-entity candidate counts,
all uncertain cases, and all severe examples.

Run outputs, coordinator forms, reviewer packets, private images, GT, and entity
annotations remain in ignored/private evaluation storage. Public score records
contain hypothesis-side offsets and diagnostics but no aligned gold words or missed
gold-entity strings or reviewer/resolver identities. Prepare randomized, engine-blind
reviewer packets separately; the coordinator templates intentionally retain engine
IDs for safe import.

For the quarantined silver calibration and 12-unit human pilot, follow
[the pilot workflow](../docs/FABRICATION_PILOT.md). The silver loader verifies
the development manifest and original output hashes without rewriting archived
run metadata. Its reports measure candidate volume; human reviews are required
to measure missed candidates and adjudicated fabrication.

## Protocol pointers

* Metrics (§5): `harness/scoring.py`, `harness/entities.py`, `harness/report.py`
* Fabrication draft: `harness/trust.py`, `harness/adjudication.py`,
  `docs/FABRICATION_METRIC.md`
* Normalization layers (§3.3/§4): `harness/normalization.py`
* Kill criterion (§8): `harness/report.py::kill_check`, surfaced in every report
* Engines receive exactly the frozen image; segmentation failures count against
  the engine (§1) — the calamari/kraken runners embed their own segmentation.
