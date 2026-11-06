#!/usr/bin/env python3
"""Fail when private evaluation material enters the benchmark checkout."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_LOCAL = (
    Path("data/gold"),
    Path("data/benchmark_gold"),
    Path("gold/entities"),
    Path("docs/outreach"),
)
FORBIDDEN_TRACKED_SUFFIXES = (".eml", ".docx", ".pdf")
PRIVATE_PAGE_NAME = re.compile(
    r"^(?:G\d{2}[a-z]?|A\d{2}_annex)\.(?:jpe?g|png|tiff?|txt|ya?ml)$",
    re.IGNORECASE,
)


def violations() -> list[str]:
    problems = [str(path) for path in FORBIDDEN_LOCAL if (ROOT / path).exists()]
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode().split("\0")
    problems.extend(path for path in tracked if path.endswith(FORBIDDEN_TRACKED_SUFFIXES))
    problems.extend(path for path in tracked if PRIVATE_PAGE_NAME.match(Path(path).name))
    return sorted(set(filter(None, problems)))


def main() -> int:
    problems = violations()
    if problems:
        print("benchmark boundary violation:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    print("benchmark boundary: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
