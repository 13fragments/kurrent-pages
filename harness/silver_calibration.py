"""Verified silver inputs and cross-engine review-volume diagnostics.

Archived run metadata predates the repository split. Bind a new diagnostic
record to the silver manifest and original output bytes; never rewrite history
or promote silver results to a benchmark verdict.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics

from harness import normalization
from harness.entities import extract_entity_risk_candidates
from harness.gold import sha256_file
from harness.trust import score_trust_diagnostics


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def _verify(path: Path, expected: object) -> None:
    if not isinstance(expected, str) or sha256_file(path) != expected:
        raise ValueError(f"{path}: SHA-256 does not match the silver manifest")


def load_silver_units(
    manifest_path: Path,
    gt_dir: Path,
    images_dir: Path,
    run_dirs: list[Path],
) -> list[dict]:
    """Load complete archived engine runs against an explicit silver manifest.

    All payloads must be dev-prefixed, hashed silver entries. The original
    freeze metadata is retained as evidence, not trusted as a silver binding.
    """
    manifest = _json(manifest_path)
    pages = manifest.get("pages")
    if (
        not isinstance(pages, dict)
        or not pages
        or manifest.get("page_count") != len(pages)
        or "silver" not in str(manifest.get("purpose", "")).lower()
        or not manifest.get("quarantine")
    ):
        raise ValueError("expected a nonempty, quarantined silver development manifest")
    references = {}
    for page, info in sorted(pages.items()):
        if not page.startswith("dev_") or Path(page).name != page:
            raise ValueError("only dev-prefixed silver page IDs are accepted")
        image = images_dir / f"{page}.jpg"
        reference = gt_dir / f"{page}.txt"
        metadata = gt_dir / f"{page}.meta.json"
        for path, key in (
            (image, "image_sha256"),
            (reference, "gt_sha256"),
            (metadata, "meta_sha256"),
        ):
            _verify(path, info.get(key))
        meta = _json(metadata)
        if meta.get("id") != page or meta.get("stratum") != info.get("stratum"):
            raise ValueError(f"{page}: silver metadata identity mismatch")
        references[page] = reference.read_bytes().decode("utf-8")
    units = []
    seen = set()
    manifest_hash = sha256_file(manifest_path)
    for run_dir in run_dirs:
        run_meta_path = run_dir / "run.json"
        run_meta = _json(run_meta_path)
        engine_dirs = sorted((run_dir / "outputs").glob("*"))
        if not engine_dirs:
            raise ValueError(f"{run_dir}: no archived engine outputs")
        for engine_dir in engine_dirs:
            if not engine_dir.is_dir():
                continue
            engine = engine_dir.name
            if engine not in run_meta.get("engines", {}):
                raise ValueError(f"{run_dir}: engine absent from run metadata")
            records = sorted(engine_dir.glob("*.json"))
            if {path.stem for path in records} != set(pages):
                raise ValueError(
                    f"{engine_dir}: archived page coverage differs from silver manifest"
                )
            for record_path in records:
                record = _json(record_path)
                page = record_path.stem
                info = pages[page]
                if (engine, page) in seen:
                    raise ValueError(f"duplicate engine/page input: {engine}/{page}")
                if (
                    record.get("engine") != engine
                    or record.get("page") != page
                    or record.get("image") != f"{page}.jpg"
                    or record.get("image_sha256") != info["image_sha256"]
                ):
                    raise ValueError(
                        f"{record_path}: output identity/image binding mismatch"
                    )
                if not isinstance(record.get("text"), str) or record.get("error"):
                    raise ValueError(
                        f"{record_path}: requires a successful archived text output"
                    )
                seen.add((engine, page))
                units.append(
                    {
                        "engine": engine,
                        "page": page,
                        "stratum": info["stratum"],
                        "image_path": str((images_dir / f"{page}.jpg").resolve()),
                        "image_sha256": info["image_sha256"],
                        "reference": references[page],
                        "hypothesis": record["text"],
                        "source_run": str(run_dir.resolve()),
                        "source_run_sha256": sha256_file(run_meta_path),
                        "source_record_sha256": sha256_file(record_path),
                        "silver_manifest_sha256": manifest_hash,
                        "reference_sha256": info["gt_sha256"],
                        "source_model_id": record.get("model_id"),
                        "source_config_sha256": record.get("config_sha256"),
                    }
                )
    if not units:
        raise ValueError("no silver run inputs supplied")
    return units


def score_silver_unit(unit: dict) -> dict:
    """Current trust diagnostics only; no expensive unrelated CER calculations."""
    reference, hypothesis = normalization.scoring_texts(
        unit["reference"], unit["hypothesis"]
    )
    reference, hypothesis = normalization.normalize(reference), normalization.normalize(
        hypothesis
    )
    scores = score_trust_diagnostics(reference, hypothesis)
    scores.update(extract_entity_risk_candidates(hypothesis))
    scores["image_sha256"] = unit["image_sha256"]
    return {
        **unit,
        "reference_normalized": reference,
        "hypothesis_normalized": hypothesis,
        "score": scores,
    }


def summarize_silver_units(scored: list[dict]) -> dict:
    """Aggregate review burden; real-output recall awaits exhaustive human review."""
    by_engine = defaultdict(list)
    for unit in scored:
        by_engine[unit["engine"]].append(unit)
    engines = {}
    for engine, units in sorted(by_engine.items()):
        scores = [unit["score"] for unit in units]
        spans = [len(score["review_candidate_spans_auto"]) for score in scores]
        entities = [len(score["entity_risk_candidates"]) for score in scores]
        rates = [score["review_candidate_rate_auto"] for score in scores]
        chars = sum(score["hyp_chars"] for score in scores)
        engines[engine] = {
            "pages": len(units),
            "hypothesis_chars": chars,
            "span_candidates": sum(spans),
            "entity_candidates": sum(entities),
            "pages_with_span_candidates": sum(count > 0 for count in spans),
            "span_candidates_max_per_page": max(spans),
            "entity_candidates_max_per_page": max(entities),
            "candidate_rate_median": statistics.median(rates),
            "candidate_rate_mean": statistics.mean(rates),
            "candidate_rate_micro": sum(
                s["review_candidate_chars_auto"] for s in scores
            )
            / chars
            if chars
            else 0,
            "candidate_rate_max": max(rates),
            "real_output_recall": None,
            "adjudication_status": "awaiting_human_reviews",
        }
    evidence = [
        {
            key: unit[key]
            for key in (
                "engine",
                "page",
                "source_run_sha256",
                "source_record_sha256",
                "silver_manifest_sha256",
                "image_sha256",
                "reference_sha256",
                "source_model_id",
                "source_config_sha256",
            )
        }
        for unit in scored
    ]
    first = scored[0]["score"]
    return {
        "schema_version": "silver-calibration-v01",
        "purpose": (
            "Quarantined silver diagnostics; no model-quality claim or T3 verdict"
        ),
        "trust_diagnostic_version": first["trust_diagnostic_version"],
        "review_candidate_version": first["review_candidate_version"],
        "review_candidate_parameters": first["review_candidate_parameters"],
        "entity_candidate_version": first["entity_candidate_version"],
        "engines": engines,
        "source_evidence": evidence,
        "source_evidence_sha256": hashlib.sha256(
            json.dumps(evidence, sort_keys=True).encode()
        ).hexdigest(),
        "t3_status": "unresolved",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", type=Path, default=Path("harness/dev_manifest.json")
    )
    parser.add_argument("--gt", type=Path, default=Path("data/dev_silver/gt"))
    parser.add_argument("--images", type=Path, default=Path("data/dev_silver/pages"))
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; use a new path")
    if args.workers < 1:
        parser.error("workers must be positive")
    units = load_silver_units(args.manifest, args.gt, args.images, args.run_dir)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        scored = []
        for unit in pool.map(score_silver_unit, units):
            scored.append(unit)
            print(f"scored {len(scored)}/{len(units)}", flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(summarize_silver_units(scored), output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(f"report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
