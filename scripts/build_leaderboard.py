#!/usr/bin/env python3
"""Build leaderboard/leaderboard.json and LEADERBOARD.md from public aggregates.

  uv run python scripts/build_leaderboard.py --aggregates <dir of <run>__<engine>/aggregates.json>

Rows come from leaderboard/rows.yml. Rows with `section: frontier` go to `frontier_rows`
and a separate "Frontier reference" section. Rows with `section: self_reported` go to
`self_reported_rows` and a separate "Self-reported (benchmark maintainer)" section. Neither
section is ranked with `rows`. The inputs are the aggregates-only reports
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
FRONTIER_NOTE = (
    "General-purpose frontier models, each a single run on one date through the "
    "vendor's command-line tool with the benchmark prompt and the page image only (no tools). Only page "
    "images were sent; model training on the data was off in both accounts. Vendor models change, so "
    "these rows are snapshots. They are not ranked with the main table."
)
SELF_REPORTED_NOTE = (
    "13fragments maintains this benchmark and also built the models in this section. 13fragments "
    "scored them with the same scorer and protocol as every other row. Because of this conflict of "
    "interest, these rows are self-reported and are not ranked with the main table."
)


def build(aggregates_dir: Path, spec: dict) -> dict:
    rows, frontier, self_reported = [], [], []
    groups = {None: rows, "frontier": frontier, "self_reported": self_reported}
    for row in spec["rows"]:
        if row.get("section") not in groups:
            raise SystemExit(f"{row['aggregates']}: unknown section {row['section']!r}")
        public = json.loads((aggregates_dir / row["aggregates"] / "aggregates.json").read_text())
        engine_key = row["aggregates"].split("__", 1)[1]
        engine = public["engines"][engine_key]
        if any(engine["gaps"][key] for key in ("missing_pages", "skipped_no_gt", "unbound_image_pages")):
            raise SystemExit(f"{row['aggregates']}: incomplete run; not a leaderboard row")
        groups[row.get("section")].append(
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
                **({"loop_policy_pages": engine["loop_policy_pages"]} if "loop_policy_pages" in engine else {}),
            }
        )
    for group in groups.values():
        group.sort(key=lambda r: r["overall"]["cer_norm_median"])
    return {
        "benchmark": spec["version"],
        "harness_tag": spec["harness_tag"],
        "metric_note": "cer_norm: normalized character error rate (protocol §4, §5); lower is better.",
        "rows": rows,
        "frontier_note": FRONTIER_NOTE,
        "frontier_rows": frontier,
        "self_reported_note": SELF_REPORTED_NOTE,
        "self_reported_rows": self_reported,
    }


def overall_table(rows: list[dict]) -> list[str]:
    lines = [
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
    return lines


def stratum_table(rows: list[dict], key: str, header: str) -> list[str]:
    lines = [f"| Engine | {header} |", "|---|" + "---|" * len(STRATA)]
    for row in rows:
        cells = " | ".join(_fmt(row["per_stratum"][s].get(key)) for s in STRATA)
        lines.append(f"| {row['engine']} | {cells} |")
    return lines


def render(board: dict) -> str:
    rows, frontier = board["rows"], board["frontier_rows"]
    self_reported = board.get("self_reported_rows", [])
    strata_n = {s: rows[0]["per_stratum"][s]["n"] for s in STRATA}
    header = " | ".join(
        f"{s} ({strata_n[s]}{', indicative' if strata_n[s] < INDICATIVE_BELOW else ''})"
        for s in STRATA
    )
    lines = [
        f"# Leaderboard: {board['benchmark']}",
        "",
        "Held-out set of 53 scored pages, ground truth v1.0, scored with harness "
        f"{board['harness_tag']}. Aggregates only: no page scores and no outputs are "
        "published. `cer_norm` is the normalized character error rate (protocol §4, §5); "
        "lower is better. Entity recall is the share of gold persons, places, and dates "
        "found in the output (§5.5). Seg-fail is the share of pages with `cer_norm` above "
        "0.75 or an empty output (§5.4). Licence: CC BY 4.0.",
        "",
        "## Overall and hard strata",
        "",
        *overall_table(rows),
    ]
    for title, key in (
        ("`cer_norm` median per stratum", "cer_norm_median"),
        ("Entity recall median per stratum", "entity_recall_median"),
    ):
        lines += ["", f"## {title}", "", "Pages per stratum in brackets.", "", *stratum_table(rows, key, header)]
    if frontier:
        lines += ["", "## Frontier reference", "", board["frontier_note"], "", *overall_table(frontier),
                  "", "`cer_norm` median per stratum:", "", *stratum_table(frontier, "cer_norm_median", header)]
    if self_reported:
        lines += ["", "## Self-reported (benchmark maintainer)", "", board["self_reported_note"], "",
                  *overall_table(self_reported), "", "`cer_norm` median per stratum:", "",
                  *stratum_table(self_reported, "cer_norm_median", header)]
    lines += [
        "",
        "## Notes",
        "",
        "- **Hard strata** are the §8 set of 33 pages: ugly_kurrent, suetterlin, table_registry,",
        "  marginalia, and mixed_print_handwriting.",
        "- **Small strata.** A stratum with fewer than 5 pages is indicative only. Read every",
        "  median with its page count.",
        "- **Fabrication.** The proxy column counts pages whose automatic long-insertion rate",
        "  (v0.1) is above 0.10. It is a review diagnostic, not a fabrication verdict. T3, the",
        "  adjudicated check for invented text (two AI model reviewers, §10, 2026-11-06), ran only",
        "  for Kurrent Transcriber 1B and LightOnOCR-HGH in their run of 2026-11-17: each had 0 of",
        "  53 pages with invented text, which meets the T3 pass rule of §10 (2026-11-06). No other",
        "  row has a T3 result; the image-step row of LightOnOCR-HGH has none either. In",
        "  `leaderboard.json`, `t3_status` is \"unresolved\" for every row:",
        "  that harness field does not apply the §10 rule.",
        "- **Reproducibility.** VLM rows are single runs in one serving state, with greedy decoding",
        "  except the LightOnOCR-3 rows (one sample at temperature 0.2 with a fixed seed). On the",
        "  maintainer's hardware, a serving-state change moved medians by about 0.02. Rows from",
        "  one run compare exactly; rows from different runs carry that noise.",
        "- **Repeat runs (v1.0.7).** Four rows ran three more times on 2026-11-26 (§10). The three",
        "  LightOnOCR rows gave the same median in all four runs. CHURRO 3B gave 0.236 to 0.263,",
        "  with 13 of 53 replies at the token limit in each repeat. Every pairwise order held, and no",
        "  published score changed. Read a row within about 0.03 of CHURRO 3B as not ordered against it.",
        "- **Image position.** The author of LightOnOCR-HGH observed that a shift of the image by",
        "  half a patch (7 pixels) can change what models of this kind read, for example whether a",
        "  faint first line is read. The maintainer has not measured this on the benchmark pages.",
        "  Read small differences between closely related models with care.",
        "- **Loop guard.** VLM outputs that stopped at the token limit are scored without their",
        "  trailing repetition loop (§10, 2026-10-16). Kurrent Transcriber 1B also removes repeated",
        "  runs (`run_removal_v1`, §10, 2026-11-13). `loop_policy_pages` in `leaderboard.json`",
        "  counts the pages that this step changed.",
        "- **Fine-tuned rows (added in v1.0.4).** Kurrent Transcriber 1B and LightOnOCR-HGH ran in",
        "  one sealed run on 2026-11-17 (§10). Both used greedy decoding, at most 4,096 tokens, the",
        "  page image only, a windowed repetition penalty of 1.1 over 20 tokens (the vLLM plugin",
        "  ships with the Kurrent Transcriber 1B repository), and the LightOnOCR output map",
        "  (`lighton-marks`). Kurrent Transcriber 1B also used its image step (`furniture_fp_v16`)",
        "  and run removal, as its model card documents. For LightOnOCR-HGH, these are the",
        "  maintainer's settings. The maintainer of this benchmark publishes Kurrent Transcriber 1B.",
        "- **LightOnOCR-HGH, two rows (second row added in v1.0.6).** The first LightOnOCR-HGH row",
        "  read the unchanged scans. At the model author's request, the second used the image step",
        "  of Kurrent Transcriber 1B (`furniture_fp_v16`) on 2026-11-19 (§10). This step paints scan",
        "  furniture outside the leaf and keeps the image size. It does not crop to the paper edge",
        "  or split a double-page spread. Neither row has the input preparation of the model card.",
        "- **LightOnOCR-HGH, result.** Median 0.075 with the image step, 0.090 without. Under the",
        "  rule registered before the run, the two are level within the serving drift, so the result",
        "  does not show that the image step helps. Kurrent Transcriber 1B ran in the same session",
        "  as a drift control and scored 0.071, as recorded; the difference of 0.004 is also level.",
        "  The image-step row had one loop-guard cut.",
        "- **Maintainer runs (added in v1.0.5).** The maintainer ran LightOnOCR-3-1B,",
        "  LightOnOCR-3-4B, and kraken-german-xix-v1 on 2026-11-19 (§10), each once, at a pinned",
        "  revision with the settings of its model card. LightOnOCR-3: page image only, temperature",
        "  0.2, top_p 0.9, a fixed seed, at most 4,096 tokens, and no output map; the 4B row also",
        "  uses the card client's thumbnail step (at most 2,048 pixels per side). The two",
        "  LightOnOCR-3 rows differ by less than the serving drift; read them as level.",
        "  kraken-german-xix-v1: the card's command, kraken 7.0 baseline segmentation and",
        "  recognition. Model owners can ask for a run with other settings (`SUBMITTING.md`).",
        "- **Maintainer runs, batch 3 (added in v1.0.7).** The maintainer ran six open models on",
        "  2026-11-25 and 2026-11-26 (§10), each once, at a pinned revision. Gemma 4 31B and",
        "  Qwen3.5-27B: the zero-shot settings of the Qwen3.5-4B row (greedy, repetition penalty 1.1,",
        "  at most 4,096 tokens, thinking off; both vendors recommend sampling). Gemma 4 used an",
        "  image budget of 1,120 vision tokens. GLM-OCR: its SDK 0.1.5 with defaults, without",
        "  speculative decoding.",
        "- **Batch 3, document-OCR models.** dots.ocr: the authors' parser with its defaults",
        "  (temperature 0.1, no seed, at most 16,384 tokens). Its picture regions come out as base64",
        "  image data, which counts against the engine and explains its mean. DeepSeek-OCR and",
        "  DeepSeek-OCR-2: the card prompt \"Free OCR.\"; on many pages both repeat one short sequence",
        "  until the token limit.",
        "- **Batch 3, not run.** Unlimited-OCR (setup failed after two server starts), Chandra OCR 2 (its",
        "  licence excludes users with a competing product), and Unlimited-OCR-2 (needs its own",
        "  serving build). The drift control, LightOnOCR-HGH with the image step, reproduced its",
        "  median of 0.075 in every session where it ran.",
        "- **Harness.** The rows added in v1.0.4 were scored with harness v1.0.4. It adds opt-in",
        "  engine keys: an image step, run removal, and an output map (§10, 2026-11-13 and",
        "  2026-11-15). The rows added in v1.0.5 were scored with harness v1.0.5. It adds opt-in",
        "  sampling keys, an image step, and a line-model engine type (§10, 2026-11-19). The row",
        "  added in v1.0.6 was scored with the same harness.",
        "- **Harness v1.0.7.** The rows added in v1.0.7 were scored with harness v1.0.7. It adds an",
        "  engine type for the authors' page pipelines, a key that sends the prompt before the image,",
        "  and an output map (§10, 2026-11-25).",
        "- **Illegible marks.** `cer_norm` scores `[unleserlich]` as ordinary text. Where the ground",
        "  truth has text, the mark costs its 13 characters. So an engine that marks a spot instead",
        "  of guessing pays this cost. LightOnOCR-HGH writes ▨, which its output map turns into",
        "  `[unleserlich]`. A later protocol version may score the mark differently.",
        "- **Unchanged rows.** For engines without the new keys, the OCR metrics and the public",
        "  aggregates use unchanged code. The earlier rows keep their scores.",
        "- **Self-reported row.** Kurrent Transcriber 1B is in its own section, outside the",
        "  rank order, because the maintainer of this benchmark built it (§10, 2026-11-25). Its",
        "  scores did not change. From v1.0.7, a maintainer model runs on the held-out pages at most",
        "  once per public release, after it is chosen on development sets (§10, 2026-11-26).",
        "- **Annex pages** are reported only and are not a fabrication signal (§10, 2026-10-18).",
        "- **Commercial references.** Transkribus rows ran on 2026-09-24 through the Transkribus",
        "  service.",
        "- **Frontier reference.** Claude Fable 5.1 and GPT-6-Astra ran at their highest",
        "  effort setting through the Claude Code CLI and the Codex CLI on the maintainer's",
        "  subscriptions. The rows record the run date; a later model version can score",
        "  differently.",
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
    print(
        f"leaderboard: {len(board['rows'])} rows, {len(board['frontier_rows'])} frontier rows, "
        f"{len(board['self_reported_rows'])} self-reported rows; page-ID check clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
