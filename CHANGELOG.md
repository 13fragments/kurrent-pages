# Changelog

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
