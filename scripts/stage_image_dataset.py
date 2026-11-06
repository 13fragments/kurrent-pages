#!/usr/bin/env python3
"""Stage the gated page-image dataset for upload (protocol §10, 2026-11-06, O3).

  uv run python scripts/stage_image_dataset.py --out <staging dir>

Copies the scored page images from the private evaluation checkout, checks every
copy against gold/v1_pages.sha256, and writes metadata.csv, SHA256SUMS, and the
dataset card and terms from docs/release/dataset/. Uploads nothing. The annex
pages stay out: the selection records no licence for them. Prints counts only.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.gold import load_selection, sha256_file  # noqa: E402

CARD_DIR = ROOT / "docs/release/dataset"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--images",
        type=Path,
        default=Path(os.environ.get("BENCHMARK_EVAL_ROOT", ROOT.parent / "benchmark-eval-private"))
        / "data/benchmark_gold/v1_pages",
    )
    args = parser.parse_args()
    if args.out.resolve().is_relative_to(ROOT):
        print("error: stage outside this repository", file=sys.stderr)
        return 2
    manifest = dict(
        reversed(line.split(None, 1))
        for line in (ROOT / "gold/v1_pages.sha256").read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    pages = [page for page in load_selection(ROOT / "gold/selection.yml") if page.scored]
    (args.out / "images").mkdir(parents=True, exist_ok=True)
    mismatched = 0
    for page in pages:
        target = args.out / "images" / page.image_name
        shutil.copyfile(args.images / page.image_name, target)
        mismatched += sha256_file(target) != manifest[page.image_name].casefold()
    with (args.out / "metadata.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["file_name", "page_id", "primary_stratum", "strata", "period", "license", "source_collection"]
        )
        for page in pages:
            writer.writerow([
                f"images/{page.image_name}", page.id, page.primary_stratum,
                ";".join(page.strata), page.period, page.license, page.source,
            ])
    (args.out / "SHA256SUMS").write_text(
        "".join(f"{manifest[page.image_name]}  images/{page.image_name}\n" for page in pages),
        encoding="utf-8",
    )
    for name in ("README.md", "TERMS.md"):
        shutil.copyfile(CARD_DIR / name, args.out / name)
    licences = Counter(page.license for page in pages)
    print(f"staged {len(pages)} scored page images in {args.out}")
    print(f"hash check against gold/v1_pages.sha256: {len(pages) - mismatched} match, {mismatched} differ")
    print(f"licences: {dict(sorted(licences.items()))}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
