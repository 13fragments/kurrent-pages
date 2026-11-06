#!/usr/bin/env python3
"""Turn a submitted prediction bundle into a harness run dir (protocol §11, O4).

  uv run python scripts/import_submission.py --bundle <dir> --runs-root evals/submissions
  uv run python -m harness report --run-dir <printed run dir> --aggregates-only --out <dir>

The bundle format is in SUBMITTING.md. Every output is bound to the frozen image
by the hash the participant reports; a scored page without a text file is a
failed page and scores as empty output (§1). The script prints counts only.
Exit 2 rejects the bundle and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness import PROTOCOL_VERSION  # noqa: E402
from harness.gold import load_selection, sha256_file  # noqa: E402
from harness.runner import _git_commit  # noqa: E402

ENGINE_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
REQUIRED = ("engine", "engine_version", "benchmark_version", "description", "image_sha256")


class BundleError(ValueError):
    pass


def _regular(path: Path, bundle: Path) -> Path:
    # A zip can carry symlinks: a page file linked to a private GT file would score
    # as a perfect page and copy GT text into the run dir.
    if path.is_symlink() or not path.resolve().is_relative_to(bundle.resolve()):
        raise BundleError(f"{path.name}: symlink or path outside the bundle")
    return path


def read_bundle(bundle: Path, pages, manifest: dict[str, str]) -> tuple[dict, dict[str, str]]:
    _regular(bundle / "pages", bundle)
    meta = json.loads(_regular(bundle / "run.json", bundle).read_text(encoding="utf-8"))
    missing = [key for key in REQUIRED if key not in meta]
    if missing:
        raise BundleError(f"run.json lacks {missing}")
    if not ENGINE_NAME.match(str(meta["engine"])):
        raise BundleError("engine name must match [a-z0-9][a-z0-9_-]*")
    scored = {page.id: page for page in pages if page.scored}
    texts: dict[str, str] = {}
    for path in sorted((bundle / "pages").glob("*")):
        if path.suffix != ".txt" or path.stem not in scored:
            raise BundleError(f"{path.name}: not a scored page of this selection")
        if not _regular(path, bundle).is_file():
            raise BundleError(f"{path.name}: not a regular file")
        try:
            texts[path.stem] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise BundleError(f"{path.name}: not UTF-8") from exc
    hashes = meta["image_sha256"]
    for page_id, page in scored.items():
        reported = str(hashes.get(page_id, "")).casefold()
        if reported != manifest.get(page.image_name):
            raise BundleError(f"{page_id}: image hash missing or not the frozen image")
    unknown = sorted(set(meta.get("length_stopped", [])) - set(scored))
    if unknown:
        raise BundleError(f"length_stopped names {len(unknown)} unknown pages")
    return meta, texts


def write_run(runs_root: Path, meta: dict, texts: dict[str, str], pages, args) -> Path:
    stamp = datetime.now(timezone.utc)
    engine = meta["engine"]
    run_dir = runs_root / f"{stamp:%Y%m%d-%H%M%S}_submission_{engine}"
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = runs_root / f"{stamp:%Y%m%d-%H%M%S}_submission_{engine}_{suffix}"
    out_dir = run_dir / "outputs" / engine
    out_dir.mkdir(parents=True)
    length_stopped = set(meta.get("length_stopped", []))
    for page in pages:
        if not page.scored:
            continue
        record = {
            "page": page.id,
            "engine": engine,
            "image": page.image_name,
            "image_sha256": str(meta["image_sha256"][page.id]).casefold(),
            "timestamp": stamp.isoformat(timespec="seconds"),
            # The loop guard (§10, 2026-10-16) applies to outputs that used all of
            # their completion tokens: max_tokens is 1 and a length stop used 1.
            "meta": {"usage": {"completion_tokens": int(page.id in length_stopped)}},
        }
        if page.id in texts:
            record["text"] = texts[page.id]
        else:
            record.update(text="", error="no output in the submitted bundle")
        (out_dir / f"{page.id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    run_meta = {
        "run_id": run_dir.name,
        "protocol_version": PROTOCOL_VERSION,
        "created": stamp.isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "engines": {
            engine: {
                "type": "submission",
                "version": meta["engine_version"],
                "description": meta["description"],
                "config": {"max_tokens": 1},
            }
        },
        "submission": {
            key: meta.get(key) for key in ("engine_version", "benchmark_version", "submitter")
        },
        "selection_path": str(args.selection.resolve()),
        "selection_sha256": sha256_file(args.selection),
        "freeze_sha_path": str(args.sha.resolve()),
        "freeze_sha256": sha256_file(args.sha),
    }
    (run_dir / "run.json").write_text(json.dumps(run_meta, indent=2) + "\n", encoding="utf-8")
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--runs-root", type=Path, default=ROOT / "evals/submissions")
    parser.add_argument("--selection", type=Path, default=ROOT / "gold/selection.yml")
    parser.add_argument("--sha", type=Path, default=ROOT / "gold/v1_pages.sha256")
    args = parser.parse_args()
    pages = load_selection(args.selection)
    manifest = {
        name.strip(): digest.casefold()
        for digest, name in (
            line.split(None, 1)
            for line in args.sha.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    try:
        meta, texts = read_bundle(args.bundle, pages, manifest)
    except (BundleError, OSError, json.JSONDecodeError) as exc:
        print(f"rejected: {exc}", file=sys.stderr)
        return 2
    run_dir = write_run(args.runs_root, meta, texts, pages, args)
    scored = sum(page.scored for page in pages)
    print(
        f"imported {meta['engine']} {meta['engine_version']}: {len(texts)}/{scored} scored "
        f"pages with text, {len(meta.get('length_stopped', []))} length-stopped"
    )
    print(f"run dir: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
