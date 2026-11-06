"""Benchmark harness CLI.

  python -m harness check                       # preflight: freeze, GT coverage, engines
  python -m harness list-pages                  # gold set overview
  python -m harness run --engines mock --label smoke
  python -m harness score --run-dir evals/own_gold/runs/<id>
  python -m harness report --run-dir evals/own_gold/runs/<id>
  python -m harness report --run-dir evals/own_gold/runs/<id> --aggregates-only --out <dir>

Default paths assume repo root as cwd; every one is overridable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from harness.adjudication import (
    adjudication_template,
    is_untouched_adjudication_template,
)
from harness.engines import load_engines
from harness.engines.base import EngineUnavailable
from harness.gold import (
    load_entities,
    load_gt,
    load_selection,
    sha256_file,
    stratum_total_mismatches,
    verify_freeze,
)
from harness.report import render_report
from harness.report_public import (
    dump_json,
    incomplete,
    leaks,
    public_aggregates,
    render_public_report,
)
from harness.runner import (
    _git_commit,
    create_run_dir,
    resume_conflicts,
    run_engines,
    run_meta_conflicts,
    score_run,
    write_run_meta,
)

PRIVATE_EVAL_ROOT = Path(os.environ.get("BENCHMARK_EVAL_ROOT", "../benchmark-eval-private"))

DEFAULTS = {
    "selection": Path("gold/selection.yml"),
    "sha": Path("gold/v1_pages.sha256"),
    "images": PRIVATE_EVAL_ROOT / "data/benchmark_gold/v1_pages",
    "gt": PRIVATE_EVAL_ROOT / "data/benchmark_gold/gt",
    "entities": PRIVATE_EVAL_ROOT / "data/benchmark_gold/entities",
    "engines_config": Path("configs/engines.yml"),
    "runs_root": Path("evals/own_gold/runs"),
}


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    pages = load_selection(args.selection)
    return args.func(args, pages)


def _cmd_list_pages(args, pages) -> int:
    for page in pages:
        gt = "GT" if load_gt(args.gt, page.id) is not None else "--"
        flag = "scored" if page.scored else "ANNEX "
        print(f"{page.id:5} {flag} {gt}  {page.primary_stratum:28} {page.image_name}")
    print(f"{len(pages)} pages ({sum(p.scored for p in pages)} scored)")
    return 0


def _cmd_check(args, pages) -> int:
    ok = True
    expected = [p.image_name for p in pages]
    problems = (
        verify_freeze(args.images, args.sha, expected)
        if args.sha.exists()
        else ["sha file missing"]
    )
    print(f"freeze check: {'OK' if not problems else 'FAIL'}")
    for problem in problems:
        ok = False
        print(f"  {problem}")
    with_gt = [p.id for p in pages if p.scored and load_gt(args.gt, p.id) is not None]
    scored_total = sum(p.scored for p in pages)
    print(f"GT coverage: {len(with_gt)}/{scored_total} scored pages")
    if len(with_gt) < scored_total:
        ok = False  # preflight fails until every scored page has GT (§2)
    with_entities = [
        p.id
        for p in pages
        if p.scored and load_entities(args.entities, p.id) is not None
    ]
    print(
        f"entity annotation coverage: {len(with_entities)}/{scored_total} scored pages"
    )
    if len(with_entities) < scored_total:
        ok = False  # entity annotations are gold targets too (§2.5)
    for warning in stratum_total_mismatches(args.selection):
        # Warning, not failure: known selection.yml bookkeeping double-counts;
        # §8 hard-set membership is unaffected (all involved strata are hard).
        # Resolving needs a protocol amendment (explicit primary field).
        print(f"warning: {warning}")
    engines = load_engines(args.engines_config)
    for name, engine in engines.items():
        try:
            engine.check()
            print(f"engine {name}: available")
        except EngineUnavailable as exc:
            print(f"engine {name}: UNAVAILABLE — {exc}")
    return 0 if ok else 1


def _cmd_run(args, pages) -> int:
    engines = load_engines(
        args.engines_config, args.engines.split(",") if args.engines else None
    )
    for name, engine in engines.items():
        try:
            engine.check()
        except EngineUnavailable as exc:
            print(f"error: engine {name} unavailable: {exc}", file=sys.stderr)
            return 2
    if not args.no_verify:
        # A missing sha file must block a run the same way a mismatch does
        # (§7 freeze integrity); --no-verify is the only escape hatch.
        problems = (
            verify_freeze(args.images, args.sha, [p.image_name for p in pages])
            if args.sha.exists()
            else [f"freeze hash file missing: {args.sha}"]
        )
        if problems:
            print(
                "error: freeze check failed (use --no-verify to override):",
                file=sys.stderr,
            )
            for problem in problems:
                print(f"  {problem}", file=sys.stderr)
            return 2
    # Protocol §2 hard ordering: all gold targets (transcription GT AND entity
    # annotations) are fixed before any engine output exists to be inspected.
    missing_gold = [
        p.id
        for p in pages
        if p.scored
        and (
            load_gt(args.gt, p.id) is None or load_entities(args.entities, p.id) is None
        )
    ]
    if missing_gold and not args.allow_incomplete_gt:
        print(
            f"error: {len(missing_gold)} scored pages lack GT and/or entity annotations "
            "(protocol §2 ordering). Use --allow-incomplete-gt only for smoke runs whose "
            "outputs the transcriber will not view.",
            file=sys.stderr,
        )
        return 2
    run_dir = args.run_dir or create_run_dir(args.runs_root, args.label)
    run_extra = _run_meta_extra(args)
    meta_conflicts = run_meta_conflicts(run_dir, run_extra)
    if meta_conflicts:
        print("error: run dir metadata mismatch; use a fresh run dir:", file=sys.stderr)
        for problem in meta_conflicts:
            print(f"  {problem}", file=sys.stderr)
        return 2
    conflicts = resume_conflicts(engines, pages, args.images, run_dir)
    if conflicts:
        # Refuse before touching run.json: metadata must never attribute
        # existing outputs to a different config.
        for name, reason in conflicts.items():
            print(f"error: engine {name}: {reason}", file=sys.stderr)
        return 2
    write_run_meta(run_dir, engines, run_extra)
    status = run_engines(engines, pages, args.images, run_dir)
    incomplete = False
    for name, per_page in status.items():
        # Recorded results — successes AND terminal failures — are complete
        # and scoreable (§1/§6); only pages with NO record keep the run
        # incomplete (missing image, engine unavailable/aborted, resume
        # conflict).
        noteworthy = [
            f"{gid}: {s}" for gid, s in per_page.items() if s not in ("ok", "exists")
        ]
        unrecorded = [
            s
            for s in per_page.values()
            if s not in ("ok", "exists", "failed-terminal")
            and not s.startswith("error")
        ]
        done = len(per_page) - len(unrecorded)
        print(
            f"{name}: {done}/{len(per_page)} pages recorded ({len(noteworthy)} noteworthy)"
        )
        for line in noteworthy[:10]:
            print(f"  {line}")
        if unrecorded:
            incomplete = True
    print(f"run dir: {run_dir}")
    if incomplete:
        # Pages without records must not look successful to automation;
        # resume with the same run dir once the cause is fixed.
        print("run incomplete: pages without records — see above", file=sys.stderr)
        return 1
    return 0


def _cmd_score(args, pages) -> int:
    try:
        _require_recorded_selection(args.run_dir, args.selection)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    results = score_run(
        args.run_dir,
        pages,
        args.gt,
        args.entities,
        freeze_sha_path=args.sha,
    )
    if not results:
        print("no engine outputs found in run dir", file=sys.stderr)
        return 1
    incomplete = False
    for name, result in results.items():
        overall = result["aggregate"]["overall"]
        line = (
            f"{name}: {overall['n']} pages scored, median cer_norm "
            f"{overall['cer_norm_median']}, skipped (no GT): {len(result['skipped_no_gt'])}"
        )
        trust = result["aggregate"]["trust_check"]
        line += (
            f", adjudicated: {trust['adjudicated_pages']}/{trust['expected_pages']}; "
            f"T3: {trust['status']}"
        )
        if result["error_pages"]:
            line += f", failed pages scored as empty output: {result['error_pages']}"
        if result["missing_pages"]:
            line += (
                f", MISSING outputs: {len(result['missing_pages'])} pages (partial run)"
            )
        if result["unannotated_pages"]:
            line += f", scored pages without entity annotation: {result['unannotated_pages']}"
        if result["unbound_image_pages"]:
            line += f", outputs without image hash: {result['unbound_image_pages']}"
        if result["annex_failed_pages"]:
            line += f", annex pages without output (reported only): {result['annex_failed_pages']}"
        if result["invalid_adjudications"]:
            line += f", INVALID adjudications: {result['invalid_adjudications']}"
        if result.get("loop_guard_pages"):
            line += f", loop guard cut: {result['loop_guard_pages']}"
        if (
            result["missing_pages"]
            or result["skipped_no_gt"]
            or result["unannotated_pages"]
            or result["unbound_image_pages"]
            or result["invalid_adjudications"]
        ):
            incomplete = True
        print(line)
    if incomplete:
        # Exit nonzero so automation cannot publish results from a partial run
        # (missing outputs or GT gaps); resume/complete first.
        print(
            "score incomplete: resume the run / complete GT before reporting",
            file=sys.stderr,
        )
        return 1
    return 0


def _cmd_report(args, pages) -> int:
    # Always rescore: cached scores/*.json can be stale after a resumed run
    # changed outputs, and a report must never publish a stale kill verdict.
    try:
        _require_recorded_selection(args.run_dir, args.selection)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    scores = score_run(
        args.run_dir,
        pages,
        args.gt,
        args.entities,
        freeze_sha_path=args.sha,
    )
    if not scores:
        print("nothing to report — no engine outputs in run dir", file=sys.stderr)
        return 1
    run_meta_path = args.run_dir / "run.json"
    run_meta = (
        json.loads(run_meta_path.read_text(encoding="utf-8"))
        if run_meta_path.exists()
        else {}
    )
    if args.aggregates_only:
        return _write_public_report(args, pages, run_meta, scores)
    markdown = render_report(run_meta, scores)
    report_path = args.run_dir / "report.md"
    report_path.write_text(markdown, encoding="utf-8")
    print(f"report: {report_path}")
    incomplete = False
    for name, data in scores.items():
        verdict = data["aggregate"]["kill_check"]
        print(f"{name}: kill-criterion conditions met: {verdict['kill']}")
        trust = data["aggregate"]["trust_check"]
        print(
            f"{name}: T3 {trust['status']} "
            f"({trust['adjudicated_pages']}/{trust['expected_pages']} pages adjudicated)"
        )
        if (
            data.get("missing_pages")
            or data.get("skipped_no_gt")
            or data.get("unannotated_pages")
            or data.get("unbound_image_pages")
            or data.get("invalid_adjudications")
        ):
            incomplete = True
    if incomplete:
        # The report file exists for inspection, but the exit code refuses to
        # bless a partial run (§8 verdicts need the complete set).
        print("report incomplete: run has missing outputs or GT gaps", file=sys.stderr)
        return 1
    return 0


def _write_public_report(args, pages, run_meta: dict, scores: dict) -> int:
    """Aggregates-only report (release v1.0): never touches the private report.md."""
    public = public_aggregates(run_meta, scores, _git_commit())
    markdown = render_public_report(public)
    payload = dump_json(public)
    found = leaks([markdown, payload], pages, run_meta)
    if found:
        print("error: public report would leak; nothing written:", file=sys.stderr)
        for item in found:
            print(f"  {item}", file=sys.stderr)
        return 2
    out_dir = args.out or args.run_dir / "public"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report_public.md").write_text(markdown, encoding="utf-8")
    (out_dir / "aggregates.json").write_text(payload, encoding="utf-8")
    print(f"public report: {out_dir / 'report_public.md'} (page-ID check: clean)")
    for name, engine in public["engines"].items():
        overall = engine["overall"]
        print(f"{name}: n {overall['n']}, median cer_norm {overall.get('cer_norm_median')}")
    if incomplete(public):
        print("report incomplete: run has missing outputs or GT gaps", file=sys.stderr)
        return 1
    return 0


def _cmd_adjudication_templates(args, pages) -> int:
    """Create coordinator import forms; never overwrite completed work."""
    try:
        _require_recorded_selection(args.run_dir, args.selection)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    scores = score_run(
        args.run_dir,
        pages,
        args.gt,
        args.entities,
        freeze_sha_path=args.sha,
    )
    if not scores:
        print("no engine outputs found in run dir", file=sys.stderr)
        return 1
    packet_gaps = []
    for engine, data in scores.items():
        expected = data["aggregate"]["trust_check"]["expected_pages"]
        available = len(data["pages"])
        print(
            f"{engine}: adjudication packet coverage {available}/{expected} scored pages"
        )
        for key, label in (
            ("missing_pages", "missing outputs"),
            ("skipped_no_gt", "missing transcription GT"),
            ("unannotated_pages", "missing entity annotations"),
            ("unbound_image_pages", "outputs without a valid image hash"),
        ):
            if data.get(key):
                packet_gaps.append(f"{engine}: {label}: {data[key]}")
        if available != expected and not any(
            gap.startswith(f"{engine}:") for gap in packet_gaps
        ):
            packet_gaps.append(
                f"{engine}: scored-page coverage is {available}/{expected}"
            )
    if packet_gaps:
        print(
            "error: adjudication packet is incomplete; no templates created",
            file=sys.stderr,
        )
        for gap in packet_gaps:
            print(f"  {gap}", file=sys.stderr)
        return 1
    created = 0
    skipped = 0
    pending = 0
    invalid_existing = []
    for engine, data in scores.items():
        for page, page_score in data["pages"].items():
            path = args.run_dir / "adjudications" / engine / f"{page}.yml"
            template = adjudication_template(engine, page, page_score)
            if path.exists():
                skipped += 1
                if is_untouched_adjudication_template(
                    path, engine=engine, page=page, page_score=page_score
                ):
                    pending += 1
                elif page_score.get("adjudication_status") == "invalid":
                    invalid_existing.append(str(path))
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                yaml.safe_dump(template, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            created += 1
    print(f"adjudication coordinator templates: {created} created, {skipped} preserved")
    if pending:
        print(f"untouched templates awaiting review: {pending}")
    print("templates expose engine IDs; prepare blinded reviewer packets separately")
    if invalid_existing:
        print(
            "error: existing adjudication forms are partially edited or stale:",
            file=sys.stderr,
        )
        for path in invalid_existing:
            print(f"  {path}", file=sys.stderr)
        return 1
    return 0


def _run_meta_extra(args) -> dict:
    return {
        "images_dir": str(args.images.resolve()),
        "selection_path": str(args.selection.resolve()),
        "selection_sha256": sha256_file(args.selection)
        if args.selection.exists()
        else None,
        "freeze_sha_path": str(args.sha.resolve()),
        "freeze_sha256": sha256_file(args.sha) if args.sha.exists() else None,
    }


def _require_recorded_selection(run_dir: Path, selection_path: Path) -> None:
    # A run always covers its whole loaded selection, and run.json records that
    # selection's sha256. Rejecting a hash mismatch here is the single guard that keeps
    # score/report honest: it catches both a wrong file (e.g. the default gold selection
    # against a silver run) and same-ID metadata drift (edited strata/primary) that would
    # otherwise silently mis-bucket per-stratum and Gate-0 aggregates.
    run_meta_path = run_dir / "run.json"
    if not run_meta_path.exists():
        return
    try:
        recorded = json.loads(run_meta_path.read_text(encoding="utf-8")).get(
            "selection_sha256"
        )
    except (json.JSONDecodeError, OSError):
        return
    if not recorded or selection_path is None or not selection_path.exists():
        return
    current = sha256_file(selection_path)
    if current != recorded:
        raise ValueError(
            f"--selection {selection_path} (sha256 {current[:12]}…) is not the selection "
            f"recorded for run {run_dir} (sha256 {recorded[:12]}…). Pass the selection used "
            "for this run; per-stratum and Gate-0 results depend on its exact metadata."
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    parser.add_argument("--selection", type=Path, default=DEFAULTS["selection"])
    parser.add_argument("--sha", type=Path, default=DEFAULTS["sha"])
    parser.add_argument("--images", type=Path, default=DEFAULTS["images"])
    parser.add_argument("--gt", type=Path, default=DEFAULTS["gt"])
    parser.add_argument("--entities", type=Path, default=DEFAULTS["entities"])
    parser.add_argument(
        "--engines-config", type=Path, default=DEFAULTS["engines_config"]
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-pages").set_defaults(func=_cmd_list_pages)
    sub.add_parser("check").set_defaults(func=_cmd_check)
    run_parser = sub.add_parser("run")
    run_parser.add_argument(
        "--engines", help="comma-separated engine names (default: all configured)"
    )
    run_parser.add_argument(
        "--label", default="", help="suffix for the run directory name"
    )
    run_parser.add_argument(
        "--run-dir", type=Path, help="resume into an existing run dir"
    )
    run_parser.add_argument("--runs-root", type=Path, default=DEFAULTS["runs_root"])
    run_parser.add_argument(
        "--no-verify", action="store_true", help="skip the freeze hash check"
    )
    run_parser.add_argument(
        "--allow-incomplete-gt",
        action="store_true",
        help="permit engine runs before GT is complete (smoke runs only; outputs must stay unviewed)",
    )
    run_parser.set_defaults(func=_cmd_run)
    for command, func in (
        ("score", _cmd_score),
        ("report", _cmd_report),
        ("adjudication-templates", _cmd_adjudication_templates),
    ):
        p = sub.add_parser(command)
        p.add_argument("--run-dir", type=Path, required=True)
        p.set_defaults(func=func)
        if command == "report":
            p.add_argument(
                "--aggregates-only",
                action="store_true",
                help="write the public aggregates (no page IDs, scores, or text) instead of report.md",
            )
            p.add_argument(
                "--out", type=Path, help="directory for the public report (default: RUN_DIR/public)"
            )
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
