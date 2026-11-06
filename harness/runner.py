"""Run orchestration + results store (protocol §6: every engine run logged
with exact version, config, and runtime in evals/own_gold/runs/).

Run directory layout:
  {run_dir}/run.json                     run metadata + engine descriptions
  {run_dir}/outputs/{engine}/{GID}.json  one hypothesis per page per engine
  {run_dir}/scores/{engine}.json         per-page scores + aggregates
  {run_dir}/report.md                    human-readable comparison sheet

Resume semantics (protocol §6 single-attempt rule): every existing readable
record — success OR recorded failure — is final for this run. Infrastructure
death (EngineUnavailable, e.g. dead endpoint, HTTP 5xx) writes NO record, so
the affected pages get their first real attempt on resume; deterministic
EngineErrors are terminal and score as empty output (§1). Re-attempting a
recorded failure requires a fresh run dir. run.json is created once; resumes
merge engine descriptions and append a `resumed` timestamp without touching
the original created/git_commit record.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from harness import PROTOCOL_VERSION, SCORING_SCHEMA_VERSION, normalization
from harness.adjudication import (
    AdjudicationError,
    invalid_adjudication_fields,
    is_untouched_adjudication_template,
    load_adjudication,
)
from harness.adjudication_validation import canonical_identity
from harness.engines import Engine
from harness.engines.base import EngineError, EngineUnavailable
from harness.gold import GoldPage, load_entities, load_gt, sha256_file
from harness.loop_guard import cut_loop, token_limited
from harness.report import aggregate
from harness.scoring import score_annex, score_page


def create_run_dir(runs_root: Path, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_dir = runs_root / (f"{stamp}_{label}" if label else stamp)
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_run_meta(run_dir: Path, engines: dict[str, Engine], extra: dict) -> None:
    path = run_dir / "run.json"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if path.exists():
        conflicts = run_meta_conflicts(run_dir, extra)
        if conflicts:
            raise ValueError("; ".join(conflicts))
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["engines"].update(
            {name: engine.describe() for name, engine in engines.items()}
        )
        meta.setdefault("resumed", []).append(now)
    else:
        meta = {
            "run_id": run_dir.name,
            "protocol_version": PROTOCOL_VERSION,
            "created": now,
            "git_commit": _git_commit(),
            "python": sys.version.split()[0],
            "engines": {name: engine.describe() for name, engine in engines.items()},
            **extra,
        }
    _write_json(path, meta)


def run_meta_conflicts(run_dir: Path, extra: dict) -> list[str]:
    path = run_dir / "run.json"
    if not path.exists():
        return []
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return [f"existing run metadata is unreadable: {exc}"]
    expected = {"protocol_version": PROTOCOL_VERSION, **extra}
    conflicts = []
    for key, value in expected.items():
        if key not in meta:
            conflicts.append(f"existing run metadata is missing {key!r}")
        elif meta[key] != value:
            conflicts.append(
                f"{key} differs: existing {meta[key]!r}, current {value!r}"
            )
    return conflicts


def run_engines(
    engines: dict[str, Engine],
    pages: list[GoldPage],
    images_dir: Path,
    run_dir: Path,
    skip_existing: bool = True,
) -> dict[str, dict[str, str]]:
    """Transcribe every page with every engine. Recorded outputs (success or
    failure) are final for this run — no per-page retries (§6); an
    EngineUnavailable aborts that engine's remaining pages without writing
    records so a resume gives them their first attempt. Resume refuses to mix
    outputs across engine configs (config hash stored per page record).
    Returns status map."""
    status: dict[str, dict[str, str]] = {}
    conflicts = resume_conflicts(engines, pages, images_dir, run_dir)
    for name, engine in engines.items():
        if name in conflicts:
            # Refuse the whole engine BEFORE any page is written: a partial
            # resume with a changed config or image must not mix outputs.
            status[name] = {
                page.id: f"resume-conflict: {conflicts[name]}" for page in pages
            }
            continue
        engine_dir = run_dir / "outputs" / name
        engine_dir.mkdir(parents=True, exist_ok=True)
        status[name] = {}
        config_hash = _config_hash(engine)
        stop = threading.Event()

        def run_page(page: GoldPage) -> str:
            out_path = engine_dir / f"{page.id}.json"
            if skip_existing:
                recorded = _record_state(out_path)
                if recorded == "ok":
                    return "exists"
                if recorded == "failed":
                    # §6 single attempt: a recorded failure is this run's
                    # result (scored as empty output, §1). Fresh run dir to
                    # re-attempt.
                    return "failed-terminal"
            if stop.is_set():
                return "aborted: engine unavailable"
            image = images_dir / page.image_name
            if not image.exists():
                return "missing-image"
            record = {
                "page": page.id,
                "engine": name,
                "image": page.image_name,
                "image_sha256": sha256_file(image),
                "config_sha256": config_hash,
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            try:
                output = engine.transcribe(image)
            except EngineUnavailable as exc:
                # Engine (endpoint/binary) died: stop here, write nothing, so a
                # resume retries this page and all remaining ones.
                stop.set()
                return f"unavailable: {exc}"
            except EngineError as exc:
                record.update(text="", error=str(exc))
                _write_json(out_path, record)
                return f"error: {exc}"
            record.update(
                text=output.text,
                model_id=output.model_id,
                duration_s=round(output.duration_s, 3),
                meta=output.meta,
            )
            _write_json(out_path, record)
            return "ok"

        # Engines with a `concurrency` attribute (codex_cli) run pages in parallel;
        # every other engine keeps the sequential order.
        with ThreadPoolExecutor(max_workers=max(1, getattr(engine, "concurrency", 1))) as pool:
            for page, result in zip(pages, pool.map(run_page, pages)):
                status[name][page.id] = result
    return status


def resume_conflicts(
    engines: dict[str, Engine], pages: list[GoldPage], images_dir: Path, run_dir: Path
) -> dict[str, str]:
    """Engines with ANY existing readable record in run_dir (success or
    terminal failure — both are results) produced by a DIFFERENT config or a
    DIFFERENT image than supplied now. Call before writing run metadata;
    run_engines() refuses conflicted engines outright."""
    conflicts: dict[str, str] = {}
    image_hashes: dict[str, str] = {}
    for name, engine in engines.items():
        engine_dir = run_dir / "outputs" / name
        if not engine_dir.exists():
            continue
        config_hash = _config_hash(engine)
        for page in pages:
            out_path = engine_dir / f"{page.id}.json"
            if _record_state(out_path) == "absent":
                continue
            record = json.loads(out_path.read_text(encoding="utf-8"))
            if record.get("config_sha256") != config_hash:
                conflicts[name] = (
                    f"existing output for {page.id} was produced by a different engine "
                    "config; resume with the original config or use a fresh run dir"
                )
                break
            image = images_dir / page.image_name
            if image.exists():
                if page.image_name not in image_hashes:
                    image_hashes[page.image_name] = sha256_file(image)
                if record.get("image_sha256") != image_hashes[page.image_name]:
                    conflicts[name] = (
                        f"existing output for {page.id} was produced from a different "
                        "image than the current one; use a fresh run dir"
                    )
                    break
    return conflicts


def _record_state(out_path: Path) -> str:
    """'ok' | 'failed' | 'absent' — unreadable/corrupt records count as absent
    (an interrupted write is not an attempt)."""
    if not out_path.exists():
        return "absent"
    try:
        record = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return "absent"
    return "failed" if "error" in record else "ok"


def _has_successful_output(out_path: Path) -> bool:
    return _record_state(out_path) == "ok"


def _stored_config_hash(out_path: Path) -> str | None:
    try:
        return json.loads(out_path.read_text(encoding="utf-8")).get("config_sha256")
    except (json.JSONDecodeError, OSError):
        return None


def _config_hash(engine: Engine) -> str:
    canonical = json.dumps(engine.describe(), sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def score_run(
    run_dir: Path,
    pages: list[GoldPage],
    gt_dir: Path,
    entities_dir: Path,
    *,
    freeze_sha_path: Path | None = None,
) -> dict[str, dict]:
    """Score every engine output that has GT; write scores/{engine}.json."""
    outputs_root = run_dir / "outputs"
    run_meta_path = run_dir / "run.json"
    run_meta = (
        json.loads(run_meta_path.read_text(encoding="utf-8"))
        if run_meta_path.exists()
        else {}
    )
    engine_meta = run_meta.get("engines", {})
    frozen_image_hashes = _trusted_frozen_image_hashes(run_meta, freeze_sha_path)
    results: dict[str, dict] = {}
    engine_names = set(engine_meta)
    if outputs_root.is_dir():
        engine_names.update(
            path.name for path in outputs_root.iterdir() if path.is_dir()
        )
    if not engine_names:
        return results
    for engine_name in sorted(engine_names):
        engine_dir = outputs_root / engine_name
        page_scores: dict[str, dict] = {}
        annex_scores: dict[str, dict] = {}
        skipped: list[str] = []
        error_pages: list[str] = []
        annex_failed: list[str] = []
        missing_pages: list[str] = []
        unannotated: list[str] = []
        unbound_images: list[str] = []
        invalid_adjudications: list[str] = []
        guarded_pages: list[str] = []
        for page in pages:
            out_path = engine_dir / f"{page.id}.json"
            if not out_path.exists():
                # Aborted/partial run: surface the gap instead of silently
                # aggregating over the surviving subset. Annex pages are
                # reported only (§10, 2026-10-18), so their gap is an annex gap.
                (missing_pages if page.scored else annex_failed).append(page.id)
                continue
            record = json.loads(out_path.read_text(encoding="utf-8"))
            failed = "error" in record
            hyp = "" if failed else record.get("text", "")
            image_hash = record.get("image_sha256")
            image_bound = _is_sha256(
                image_hash
            ) and image_hash.casefold() == frozen_image_hashes.get(page.image_name)
            if not image_bound:
                unbound_images.append(page.id)
            if not page.scored:
                # A crashed engine must never count as annex-clean abstention.
                # Annex pages are reported only (§10, 2026-10-18): a failed
                # probe is listed, but it does not make the run incomplete.
                if failed:
                    annex_failed.append(page.id)
                elif image_bound:
                    annex_scores[page.id] = {
                        **score_annex(hyp),
                        "image_sha256": image_hash,
                    }
                continue
            if not image_bound:
                # No transcription or Gate-0 metric may count without proof
                # that this output came from the frozen page under test.
                continue
            if failed:
                # Scored pages DO count failures (protocol §1: pipeline
                # failures score against the engine — resume retries them).
                error_pages.append(page.id)
            gt = load_gt(gt_dir, page.id)
            if gt is None:
                skipped.append(page.id)
                continue
            entities = load_entities(entities_dir, page.id)
            if entities is None:
                # §2.5 annotates every scored page; a missing file must surface
                # as incompleteness (biased recall medians, suppressed §8 kill),
                # not silently shrink the entity-metric population.
                unannotated.append(page.id)
            guard = None
            if not failed and token_limited(record, engine_meta.get(engine_name, {})):
                guarded, rule = cut_loop(hyp)
                if rule is not None:
                    raw = score_page(gt, hyp, entities=entities)
                    guard = {
                        "rule": rule,
                        "raw_chars": len(hyp),
                        "scored_chars": len(guarded),
                        "unguarded": {key: raw[key] for key in GUARD_REPORTED if key in raw},
                    }
                    hyp = guarded
                    guarded_pages.append(page.id)
            page_score = score_page(gt, hyp, entities=entities)
            if guard is not None:
                page_score["loop_guard"] = guard
            page_score["image_sha256"] = image_hash
            adjudication_path = (
                run_dir / "adjudications" / engine_name / f"{page.id}.yml"
            )
            if adjudication_path.exists() and not is_untouched_adjudication_template(
                adjudication_path,
                engine=engine_name,
                page=page.id,
                page_score=page_score,
            ):
                _, hyp_scored = normalization.scoring_texts(gt, hyp)
                hyp_norm = normalization.normalize(hyp_scored)
                try:
                    page_score.update(
                        load_adjudication(
                            adjudication_path,
                            engine=engine_name,
                            page=page.id,
                            hyp_norm=hyp_norm,
                            page_score=page_score,
                        )
                    )
                except AdjudicationError as exc:
                    message = f"{page.id}: {exc}"
                    invalid_adjudications.append(message)
                    page_score.update(invalid_adjudication_fields(str(exc)))
            page_scores[page.id] = page_score
        _enforce_consistent_reviewer_pair(page_scores, invalid_adjudications)
        aggregate_result = aggregate(
            page_scores,
            annex_scores,
            pages,
            engine_meta=engine_meta.get(engine_name, {}),
        )
        _redact_private_adjudication_fields(page_scores)
        engine_result = {
            "scoring_schema_version": SCORING_SCHEMA_VERSION,
            "engine": engine_name,
            "pages": page_scores,
            "annex_pages": annex_scores,
            "skipped_no_gt": skipped,
            "error_pages": error_pages,
            "annex_failed_pages": annex_failed,
            "missing_pages": missing_pages,
            "unannotated_pages": unannotated,
            "unbound_image_pages": unbound_images,
            "invalid_adjudications": invalid_adjudications,
            "loop_guard_pages": guarded_pages,
            "aggregate": aggregate_result,
        }
        _write_json(run_dir / "scores" / f"{engine_name}.json", engine_result)
        results[engine_name] = engine_result
    return results


# Unguarded metrics kept on a guarded page (protocol §10, 2026-10-16).
GUARD_REPORTED = ("cer_norm", "cer_dipl", "wer_norm", "nls_norm", "fab_rate", "long_ins_rate_v01")


def _enforce_consistent_reviewer_pair(
    page_scores: dict[str, dict], invalid_adjudications: list[str]
) -> None:
    """Pooled Cohen kappa requires one fixed, ordered reviewer pair."""
    expected: tuple[str, str] | None = None
    for page_id in sorted(page_scores):
        score = page_scores[page_id]
        if score.get("adjudication_status") != "complete":
            continue
        reviewers = score["adjudication_reviewers"]
        pair = tuple(canonical_identity(value) for value in reviewers)
        if expected is None:
            expected = pair
            continue
        if pair == expected:
            continue
        message = "ordered reviewer pair differs from the run-wide pair"
        invalid_adjudications.append(f"{page_id}: {message}")
        score.update(invalid_adjudication_fields(message))


def _redact_private_adjudication_fields(page_scores: dict[str, dict]) -> None:
    """Reviewer and resolver identities belong only in private coordinator forms."""
    for score in page_scores.values():
        score.pop("adjudication_reviewers", None)
        score.pop("adjudication_resolver", None)


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.casefold())
    )


def _trusted_frozen_image_hashes(
    run_meta: dict, current_manifest: Path | None = None
) -> dict[str, str]:
    """Load only the exact freeze manifest whose digest the run recorded."""
    manifest_value: object = current_manifest or run_meta.get("freeze_sha_path")
    recorded_digest = run_meta.get("freeze_sha256")
    if not isinstance(manifest_value, (str, Path)) or not _is_sha256(recorded_digest):
        return {}
    manifest = Path(manifest_value)
    try:
        if sha256_file(manifest) != recorded_digest.casefold():
            return {}
        hashes: dict[str, str] = {}
        for raw_line in manifest.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            expected, name = line.split(None, 1)
            if not _is_sha256(expected):
                return {}
            hashes[name.strip()] = expected.casefold()
        return hashes
    except (OSError, ValueError):
        return {}


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
