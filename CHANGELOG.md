# Changelog

## v1.0.7

Leaderboard, harness, and protocol release; the benchmark version stays Kurrent Pages Benchmark
v1.0. No page, ground truth, prompt of an existing engine, or OCR metric definition changed, and no
existing score changed.

- Leaderboard: add six rows from batch 3 of the maintainer runs (2026-11-25 and 2026-11-26): Gemma
  4 31B (revision `842da379`), Qwen3.5-27B (`81a287ca`), GLM-OCR (`2e85a628`, SDK 0.1.5), dots.ocr
  (`c0111ce6`, the authors' parser), DeepSeek-OCR-2 (`aaa02f38`), and DeepSeek-OCR (`9f30c71f`).
  The notes give their settings and the engines that were not run.
- Leaderboard: list Kurrent Transcriber 1B in a new "Self-reported (benchmark maintainer)"
  section, outside the rank order, because 13fragments maintains the benchmark and built the
  model. Its score did not change. `leaderboard.json` adds `self_reported_note` and
  `self_reported_rows`, and `scripts/build_leaderboard.py` accepts `section: self_reported`. On
  public `main` since 2026-11-25.
- Gold use: a maintainer model now runs on the held-out pages at most once per public release,
  after it is chosen on development sets.
- Leaderboard notes: the result of three repeat runs of four rows, and the batch 3 settings.
- Harness: engine type `pipeline_http` with `scripts/pipeline_server.py` (the authors' page
  pipelines), opt-in key `text_first`, and output map `unlimited-remove-det`. Existing engines send
  unchanged requests, and their OCR metrics and public aggregates use unchanged code.
- Configs: the batch 3 engines.
- Website: version 1.0.7 on kurrentpages.org.
- Protocol: §10 entries for the self-reported section, batch 3, its amendments, the repeat runs,
  and this release.
- `docs/release/RESCORE_V1.md`: how the new rows were scored.
- Public since 2026-11-25, listed here for the record: the practice set (`practice/`), the
  "How this benchmark differs" section, and the kurrentpages.org website with its links from the
  dataset card and the leaderboard Space.

## v1.0.6

Leaderboard and protocol release; the benchmark version stays Kurrent Pages Benchmark v1.0.
No page, ground truth, prompt, harness code, or OCR metric definition changed, and no existing
score changed.

- Leaderboard: add a second LightOnOCR-HGH row (revision `47931fbe`), run by the maintainer on
  2026-11-19 at the model author's request, with the image step of Kurrent Transcriber 1B
  (`furniture_fp_v16`). The first LightOnOCR-HGH row keeps its score and now says that it read
  uncropped scans with the maintainer's settings.
- Leaderboard notes: the result of the new row under the rule registered before the run, a note
  on image shifts of half a patch, and how `cer_norm` scores `[unleserlich]`.
- Configs: engine `lighton_hgh_fp_v16`.
- Protocol: §10 entries for the run and this release.
- `docs/release/RESCORE_V1.md`: how the new row was scored.

## v1.0.5

Leaderboard, harness, and protocol log; the benchmark version stays Kurrent Pages Benchmark v1.0.
No page, ground truth, prompt of an existing engine, or OCR metric definition changed, and no
existing score changed.

- Leaderboard: add three rows that the maintainer ran on 2026-11-19 with the settings of each
  model card: LightOnOCR-3-1B (revision `23d54408`), LightOnOCR-3-4B (revision `b71010f0`), and
  kraken-german-xix-v1 (revision `945658d6`, kraken 7.0). The notes give their settings.
- Harness: opt-in `vlm_openai` keys `top_p`, `seed`, `stop`, `skip_special_tokens`, and
  `server_max_tokens`; every VLM reply records its `finish_reason`. Image step
  `thumbnail_2048_png`. Engine type `trocr_lines` (TrOCR line models behind kraken baseline
  segmentation) with `scripts/trocr_predict.py`. Engines without these keys send unchanged
  requests, and their OCR metrics and public aggregates use unchanged code.
- `SUBMITTING.md`: owners of open-weight models can ask the maintainer to run their model. The
  maintainer decides on each request, and the usual rules apply.
- Dataset card: links `SUBMITTING.md` and gives the submission address.
- Protocol: §10 entries for the maintainer runs of batch 1 and this release.
- `docs/release/RESCORE_V1.md`: how the new rows were scored.

## v1.0.4

Leaderboard, harness, and protocol log; the benchmark version stays Kurrent Pages Benchmark v1.0.
No page, ground truth, prompt of an existing engine, or OCR metric definition changed, and no
existing score changed. T3 scoring changed (`t3-v2-abstention-mark`, below).

- Leaderboard: add Kurrent Transcriber 1B (published by the benchmark maintainer) and
  LightOnOCR-HGH (revision `47931fbe`) from the sealed gold run of 2026-11-17. The notes give
  their decoding settings and their T3 result (0 of 53 pages with invented text each).
- Harness: opt-in engine keys `preprocess` (one fixed image step), `loop_policy`
  (`run_removal_v1`), `output_map` (`lighton-marks`, `churro-xml`), `system_prompt`, and
  `server_sampling`. For engines without these keys, the OCR metrics and the public aggregates use
  unchanged code.
- Harness: the T3 export applies an engine's output map and run removal, as scoring does. T3
  scoring `t3-v2-abstention-mark` does not count a bracketed abstention mark as invented text.
- Protocol: §3.2 item 9 (scan furniture is not transcribed; ground-truth check: 0 pages changed),
  the §1 image-step exception, and §10 entries since v1.0.3. Editorial: a Pod identifier, a keyer's
  pronoun, and a name placeholder were removed from earlier entries.
- Public T3 documents: `docs/T3_MODEL_REVIEW.md`, `configs/prompts/t3_model_review.txt`,
  `scripts/model_review.py`, and `scripts/model_review_resolve.py`.
- `docs/release/RESCORE_V1.md`: how the new rows were scored.

## v1.0.3

Leaderboard and documentation; the benchmark version stays Kurrent Pages Benchmark v1.0.
No page, ground truth, prompt, or scoring code changed, and no existing score changed.

- Leaderboard: add a "Frontier reference" section (`frontier_rows` in
  `leaderboard.json`), not ranked with the main table: Claude Fable 5.1 (run
  2026-10-31) and GPT-6-Astra (run 2026-11-06), each at its highest effort setting,
  page image and benchmark prompt only.
- Leaderboard: remove the "13fragments 9B (internal, Run 11)" row. That model will
  not be released (owner decision 2026-11-06). v1.0.0 to v1.0.2 keep the row.
- The Hugging Face leaderboard page shows the frontier section.
- Protocol §10: log the sealed GPT-6-Astra gold run and its opening.
- `docs/release/RESCORE_V1.md`: the frontier rows and how they were scored.

## v1.0.2

Documentation only; the benchmark version stays Kurrent Pages Benchmark v1.0.

- Fix `CITATION.cff`: one licence value (Apache-2.0). Zenodo's citation loader
  rejected the list of two, so v1.0.1 has no Zenodo record. The abstract names
  CC BY 4.0 for the protocol, documentation, and leaderboard.
- Includes every v1.0.1 change below.

## v1.0.1

Documentation only. No score, page, ground truth, prompt, or scoring code
changed; the benchmark version stays Kurrent Pages Benchmark v1.0.

- Leaderboard: the 9B row is now "13fragments 9B (internal, Run 11)". It is an
  internal model-track run, not a released model (owner decision 2026-11-06).
  Its scores are unchanged.
- Add `CITATION.cff` (13fragments as author, concept DOI 10.5281/zenodo.24015417).

## v1.0.0 (unreleased)

Kurrent Pages Benchmark v1.0: GT v1.0, this harness tag, and the protocol with §10 up to
the tag date. Release notes: `docs/release/RELEASE_NOTES_v1.0.md`.

- Add `harness report --aggregates-only`: writes `report_public.md` and
  `aggregates.json` with per-engine overall, hard-strata, and per-stratum
  aggregates. No page ID, page score, output text, or run path; groups of one
  page are suppressed; the command refuses to write when a page ID would appear.
- Add `scripts/import_submission.py`: turns a submitted prediction bundle into a
  run dir. Every output is bound to the frozen image hash; a missing scored page
  counts as a failed page; symlinks are rejected. Bundle format: `SUBMITTING.md`.
- Add `scripts/build_leaderboard.py` and `leaderboard/` (JSON and Markdown), built
  from the aggregates-only reports of the rescored runs.
- Add `scripts/stage_image_dataset.py`: stages the gated page-image dataset with
  its card and terms outside the repository and checks every image hash.
- Add `scripts/scan_release.py`: scans the working tree, the history, and the
  commit messages for addresses, hosts, private paths, and private terms.
- Add the optional `vlm_openai` keys `image_only` (send the page without the
  prompt text) and `vllm_xargs` (passed to vLLM as-is), and the Gate 2 Round 0
  engines (§10, 2026-11-06). Requests of existing engines are unchanged.
- Rename the evaluation-root variable to `BENCHMARK_EVAL_ROOT` (default
  `../benchmark-eval-private`).
- The public export leaves out the model-track dev scripts (`scripts/dev_*.py`,
  `scripts/page_dev_score.py`) and the reviewer-form worker (`hosting/pilot-review/`,
  `scripts/pilot_site.py`); entries below that name them describe the private
  repository.
- Add `LICENSE` (Apache-2.0, code) and `LICENSE-docs` (CC BY 4.0, protocol, docs,
  manifest, leaderboard).
- Protocol: keyer names replaced by roles; the §11 release sub-decisions closed
  (§10, 2026-11-06). No method change.
- Remove a private address and host names from the engine configs, the EVO
  deployment notes, and the reviewer-form worker.

## Before v1.0.0

- Add `scripts/page_dev_score.py`: scores one slice of a frozen page dev set manifest
  (model-track EXP-20261029-page-dev-set) against a served model, with the request settings of
  `dev_checkpoints.py`. Scored text is the output, then the output map, then the loop guard (A8);
  each record keeps (R, H) from `coverage_lengths`. Image and reference hashes are checked on every
  page; errors are never scored. `dev_checkpoints.conditions()` takes the manifest path (default
  unchanged).
- Add `harness.scoring.coverage_lengths()`: the normalized reference and
  hypothesis lengths of the pair that `cer_norm` scores, for the omission guard
  of the model-track page dev set (amendment A8). No metric changes.
  `scripts/dev_checkpoints.py` also stores `omission_rate` per page (A8 diagnostic).
- Add the loop guard (protocol §10, 2026-10-16): VLM outputs that stop at the
  token limit are scored without their trailing repetition loop. Raw outputs stay
  unchanged; guarded pages keep their unguarded metrics and are listed in scores and
  reports. `scripts/dev_loop_guard.py` reports its effect on the Gate 1 dev pages.
- Host the pilot reviewer form as a Cloudflare Worker behind Cloudflare
  Access (`hosting/pilot-review/`): the reviewer's e-mail selects the packet,
  the form autosaves to the worker and submits with one button, and
  `scripts/pilot_site.py` builds the assets and fetches results for import.
  `mail_packet.py --single-file` remains for offline delivery.
- Add reproducible silver calibration and blinded human-review pilot tooling.
  Broader fixtures identify missed short replacements. Revised draft candidate
  parameters improve recall; human review and T3 ratification remain pending.
- Rewrite the reviewer form for non-technical transcribers: German, one unit
  at a time with the scan beside three steps. Highlighted spans are cards with
  grey context asking "Steht das so im Bild? Ja / Nein / Weiß nicht" with
  reasons behind Nein; entity candidates are a tick-only checklist (unticked =
  `not_entity`); the full text comes last with one explicit question about the
  rest of it, which sets the full-page audit and opens text selection for
  missed spans and entities. Autosave, live per-unit status, numbered spots,
  program wrapper text explained. "Teils" answer for mixed spans (label stays
  uncertain; a `notes` entry and an optional `unit_note`, both ignored by the
  importer, carry the detail); entity candidates answered in one row instead
  of checkbox plus question. Import contract unchanged.

- Added the post-silver fabrication-metric implementation draft: trust diagnostics,
  high-recall review candidates, private frozen-image- and hypothesis-bound dual
  review, pooled reliability, entity-risk review, and tail-aware reporting. Public
  scores redact reviewer identities. T3 remains unresolved pending pilot.
