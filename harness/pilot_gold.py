"""Blinded T3 review packets for a sealed gold run.

The loader accepts only outputs that the run's own scoring would accept: the
selection recorded in ``run.json``, the exact freeze manifest digest, a frozen
image hash on every output, and a stored page score bound to the hypothesis
that scoring saw (after the loop guard).  It reads private targets from the
eval-private paths and returns units for :func:`harness.pilot.export_pilot`.

Packets and the coordinator map hold gold text, scans, and page identity.
:func:`export_gold_packets` therefore writes only below a git-ignored path,
and its dry run returns counts only.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Sequence

from harness import normalization
from harness.gold import load_gt, load_selection, sha256_file
from harness.loop_guard import cut_loop, token_limited
from harness.pilot import export_pilot
from harness.pilot_data import prepare_units
from harness.pilot_types import PACKET_COUNT, PilotError
from harness.runner import _is_sha256, _trusted_frozen_image_hashes


def load_gold_units(
    run_dir: Path,
    engines: Sequence[str],
    *,
    selection: Path,
    sha: Path,
    images: Path,
    gt_dir: Path,
) -> list[dict]:
    """Load every scored page of each engine, bound like ``score_run`` binds it."""
    run_dir = Path(run_dir)
    run_meta = _json(run_dir / "run.json")
    recorded = run_meta.get("selection_sha256")
    if not _is_sha256(recorded) or sha256_file(selection) != recorded:
        raise PilotError("selection does not match the selection recorded for the run")
    frozen = _trusted_frozen_image_hashes(run_meta, sha)
    if not frozen:
        raise PilotError("freeze manifest does not match the digest recorded for the run")
    pages = [page for page in load_selection(selection) if page.scored]
    run_sha = sha256_file(run_dir / "run.json")
    units = []
    for engine in engines:
        engine_meta = run_meta.get("engines", {}).get(engine)
        if engine_meta is None:
            raise PilotError(f"engine is not part of the run: {engine}")
        scores = _json(run_dir / "scores" / f"{engine}.json").get("pages", {})
        for page in pages:
            record_path = run_dir / "outputs" / engine / f"{page.id}.json"
            if not record_path.is_file() or page.id not in scores:
                raise PilotError(f"{engine}: a scored page has no output or score")
            record = _json(record_path)
            image_sha = record.get("image_sha256")
            if not _is_sha256(image_sha) or image_sha.casefold() != frozen.get(page.image_name):
                raise PilotError(f"{engine}: an output is not bound to its frozen image")
            image_path = Path(images) / page.image_name
            if sha256_file(image_path) != frozen[page.image_name]:
                raise PilotError("a gold image differs from the freeze manifest")
            reference = load_gt(gt_dir, page.id)
            if reference is None:
                raise PilotError("a scored page has no gold transcription")
            hypothesis = "" if "error" in record else record.get("text", "")
            guarded = False
            if hypothesis and token_limited(record, engine_meta):
                hypothesis, rule = cut_loop(hypothesis)
                guarded = rule is not None
            score = scores[page.id]
            _, hyp_scored = normalization.scoring_texts(reference, hypothesis)
            hyp_sha = hashlib.sha256(
                normalization.normalize(hyp_scored).encode("utf-8")
            ).hexdigest()
            if score.get("hypothesis_sha256") != hyp_sha or score.get("image_sha256") != image_sha:
                raise PilotError(f"{engine}: a stored score is stale; rescore the run first")
            units.append(
                {
                    "engine": engine,
                    "page": page.id,
                    "stratum": page.primary or None,
                    "image_path": str(image_path.resolve()),
                    "image_sha256": frozen[page.image_name],
                    "reference": reference,
                    "reference_sha256": hashlib.sha256(reference.encode("utf-8")).hexdigest(),
                    "hypothesis": hypothesis,
                    "source_run": str(run_dir.resolve()),
                    "source_run_sha256": run_sha,
                    "source_record_sha256": sha256_file(record_path),
                    "source_model_id": record.get("model_id"),
                    "source_config_sha256": record.get("config_sha256"),
                    "score": score,
                    "loop_guarded": guarded,
                    "failed": "error" in record,
                }
            )
    return units


def gold_dry_run(units: list[dict]) -> dict:
    """Validate the units as packet export would and return counts only."""
    records = prepare_units(units)
    return {
        "unit_count": len(records),
        "engine_count": len({unit["engine"] for unit in units}),
        "packet_count": PACKET_COUNT,
        "hypothesis_chars": sum(len(r["hypothesis_normalized"]) for r in records),
        "span_candidates": sum(len(r["candidate_spans"]) for r in records),
        "entity_candidates": sum(len(r["entity_candidates"]) for r in records),
        "empty_hypotheses": sum(not r["hypothesis_normalized"] for r in records),
        "loop_guarded_units": sum(unit["loop_guarded"] for unit in units),
        "failed_outputs": sum(unit["failed"] for unit in units),
    }


def export_gold_packets(units: list[dict], out_dir: Path, *, seed: str) -> dict:
    """Write two blinded packets plus the coordinator map below an ignored path."""
    if not _git_ignored(Path(out_dir)):
        raise PilotError("gold packets must be written below a git-ignored path")
    result = export_pilot(units, out_dir, seed=seed, reference_source="gold")
    # Report what a coordinator needs to hand out packets, nothing that names
    # a page or engine.
    return {
        key: result[key]
        for key in ("status", "unit_count", "packet_count", "packet_ids", "map_path")
    }


def _git_ignored(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(path.resolve())],
            cwd=Path(__file__).resolve().parents[1],
            check=False,
            capture_output=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def _json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        # File names can be page IDs, so errors never name the file.
        raise PilotError(f"cannot read a run file: {exc.__class__.__name__}") from exc
    if not isinstance(value, dict):
        raise PilotError("a run file is not a JSON object")
    return value
