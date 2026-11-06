#!/usr/bin/env python3
"""Build leaderboard/leaderboard.json and LEADERBOARD.md from public aggregates.

  uv run python scripts/build_leaderboard.py --aggregates <dir of <run>__<engine>/aggregates.json>

Rows come from leaderboard/rows.yml. The inputs are the aggregates-only reports
(`harness report --aggregates-only`), so the outputs hold no page ID, page
score, or page text. The script checks that again before it writes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.gold import load_selection  # noqa: E402
from harness.report_markdown import _fmt  # noqa: E402

OUT = ROOT / "leaderboard"
STRATA = (
    "suetterlin",
    "ugly_kurrent",
    "tidy_kurrent",
    "twentieth_century_kurrent",
    "nineteenth_c_civilian",
    "degraded_fraktur",
    "mixed_print_handwriting",
    "table_registry",
    "marginalia",
    "latin_cursive_1940s",
)
INDICATIVE_BELOW = 5


def build(aggregates_dir: Path, spec: dict) -> dict:
    rows = []
    for row in spec["rows"]:
        public = json.loads((aggregates_dir / row["aggregates"] / "aggregates.json").read_text())
        engine_key = row["aggregates"].split("__", 1)[1]
        engine = public["engines"][engine_key]
        if any(engine["gaps"][key] for key in ("missing_pages", "skipped_no_gt", "unbound_image_pages")):
            raise SystemExit(f"{row['aggregates']}: incomplete run; not a leaderboard row")
        rows.append(
            {
                "engine": row["engine"],
                "category": row["category"],
                "access": row["access"],
                "run_id": public["run_id"],
                "harness_commit": public["harness_commit"],
                "overall": engine["overall"],
                "hard_strata": engine["hard_strata"],
                "per_stratum": engine["per_stratum"],
                "fabrication_proxy_unadjudicated": engine["fabrication_proxy_unadjudicated"],
                "t3_status": engine["t3_status"],
                "failed_pages": engine["gaps"]["error_pages"],
                "loop_guard_pages": engine["gaps"]["loop_guard_pages"],
            }
        )
    rows.sort(key=lambda r: r["overall"]["cer_norm_median"])
    return {
        "benchmark": spec["version"],
        "harness_tag": spec["harness_tag"],
        "metric_note": "cer_norm: normalized character error rate (protocol §4, §5); lower is better.",
        "rows": rows,
    }


def render(board: dict) -> str:
    rows = board["rows"]
    strata_n = {s: rows[0]["per_stratum"][s]["n"] for s in STRATA}
    lines = [
        f"# Leaderboard: {board['benchmark']}",
        "",
        "Held-out set of 53 scored pages, ground truth v1.0, scored with harness "
        f"`{board['harness_tag']}`. Aggregates only: no page scores and no outputs are "
        "published. `cer_norm` is the normalized character error rate (protocol §4, §5); "
        "lower is better. Entity recall is the share of gold persons, places, and dates "
        "found in the output (§5.5). Seg-fail is the share of pages with `cer_norm` above "
        "0.75 or an empty output (§5.4). Licence: CC BY 4.0.",
        "",
        "## Overall and hard strata",
        "",
        "| Engine | Category | n | `cer_norm` median | `cer_norm` mean | Entity recall median | Seg-fail | Hard strata (33) `cer_norm` median | Hard strata entity recall median | Fabrication proxy, pages > 0.10 (unadjudicated) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        o, h = row["overall"], row["hard_strata"]
        proxy = row["fabrication_proxy_unadjudicated"]
        lines.append(
            f"| {row['engine']} | {row['category']} | {o['n']} | **{_fmt(o['cer_norm_median'])}** "
            f"| {_fmt(o['cer_norm_mean'])} | {_fmt(o['entity_recall_median'])} "
            f"| {_fmt(o['seg_fail_rate'], pct=True)} | {_fmt(h.get('cer_norm_median'))} "
            f"| {_fmt(h.get('entity_recall_median'))} | {proxy['pages_above_0.10'] if proxy else '—'} |"
        )
    header = " | ".join(
        f"{s} ({strata_n[s]}{', indicative' if strata_n[s] < INDICATIVE_BELOW else ''})"
        for s in STRATA
    )
    for title, key in (
        ("`cer_norm` median per stratum", "cer_norm_median"),
        ("Entity recall median per stratum", "entity_recall_median"),
    ):
        lines += ["", f"## {title}", "", "Pages per stratum in brackets.", "", f"| Engine | {header} |",
                  "|---|" + "---|" * len(STRATA)]
        for row in rows:
            cells = " | ".join(_fmt(row["per_stratum"][s].get(key)) for s in STRATA)
            lines.append(f"| {row['engine']} | {cells} |")
    lines += [
        "",
        "## Notes",
        "",
        "- **Hard strata** are the §8 set of 33 pages: ugly_kurrent, suetterlin, table_registry,",
        "  marginalia, and mixed_print_handwriting.",
        "- **Small strata.** A stratum with fewer than 5 pages is indicative only. Read every",
        "  median with its page count.",
        "- **Fabrication** is not adjudicated for any engine (T3 open). The proxy column counts",
        "  pages whose automatic long-insertion rate (v0.1) is above 0.10. It is a review",
        "  diagnostic, not a fabrication verdict.",
        "- **Reproducibility.** VLM rows are single greedy runs in one serving state. On the",
        "  maintainer's hardware, a serving-state change moved medians by about 0.02. Rows from",
        "  one run compare exactly; rows from different runs carry that noise.",
        "- **Loop guard.** VLM outputs that stopped at the token limit are scored without their",
        "  trailing repetition loop (§10, 2026-10-16).",
        "- **Annex pages** are reported only and are not a fabrication signal (§10, 2026-10-18).",
        "- **Commercial references.** Transkribus rows ran on 2026-09-24 through the Transkribus",
        "  service.",
        "- **Internal row.** \"13fragments 9B (internal, Run 11)\" is a model-track run",
        "  (Qwen3.5-9B with a LoRA adapter, Run 11 step 800). It is a reference, not a",
        "  released model.",
        "- **Submissions:** see [`SUBMITTING.md`](../SUBMITTING.md). One scored submission per",
        "  engine per 30 days.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregates", type=Path, required=True)
    parser.add_argument("--rows", type=Path, default=OUT / "rows.yml")
    args = parser.parse_args()
    spec = yaml.safe_load(args.rows.read_text(encoding="utf-8"))
    board = build(args.aggregates, spec)
    payload = json.dumps(board, indent=2, ensure_ascii=False) + "\n"
    markdown = render(board)
    pages = load_selection(ROOT / "gold/selection.yml")
    for page in pages:
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(page.id)}(?![A-Za-z0-9])")
        if pattern.search(payload) or pattern.search(markdown):
            raise SystemExit(f"page ID {page.id} would be published; nothing written")
    (OUT / "leaderboard.json").write_text(payload, encoding="utf-8")
    (OUT / "LEADERBOARD.md").write_text(markdown, encoding="utf-8")
    print(f"leaderboard: {len(board['rows'])} rows; page-ID check clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
