#!/usr/bin/env python3
"""Prepare the documented silver pilot from verified archived engine outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

from harness.pilot import export_pilot
from harness.silver_calibration import load_silver_units


DEFAULT_PAGES = ("dev_freiberg_0016", "dev_kch060_615", "dev_giessen_0060")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--page", action="append", help="repeat to replace the documented sample"
    )
    parser.add_argument("--seed", type=int, default=20260906)
    parser.add_argument(
        "--manifest", type=Path, default=Path("harness/dev_manifest.json")
    )
    parser.add_argument("--gt", type=Path, default=Path("data/dev_silver/gt"))
    parser.add_argument("--images", type=Path, default=Path("data/dev_silver/pages"))
    args = parser.parse_args()
    units = load_silver_units(args.manifest, args.gt, args.images, args.run_dir)
    pages = set(args.page or DEFAULT_PAGES)
    missing = pages - {unit["page"] for unit in units}
    if missing:
        parser.error(f"selected pages absent from silver manifest: {sorted(missing)}")
    selected = [unit for unit in units if unit["page"] in pages]
    result = export_pilot(selected, args.out, seed=args.seed)
    print(f"pilot: {result['unit_count']} units per reviewer; human reviews pending")
    for path in result["review_files"]:
        print(f"review form: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
