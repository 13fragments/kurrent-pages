"""Aggregates-only report: the public form of a scored run (release v1.0, B7).

It publishes per-engine, per-stratum aggregates and nothing finer: no page ID,
no page score, no output or GT text, and no path from the run metadata. A group
of fewer than MIN_GROUP pages is suppressed, because its median would be one
page's score; `*_max` fields are left out for the same reason. `leaks()` checks
the rendered text before anything is written.
"""

from __future__ import annotations

import json
import re

from harness import PROTOCOL_VERSION, SCORING_SCHEMA_VERSION
from harness.gold import GoldPage
from harness.report_markdown import _fmt

MIN_GROUP = 2
INDICATIVE_BELOW = 5
FAB_PROXY_CUT = 0.10
_PUBLIC_STATS = (
    "cer_norm_median",
    "cer_norm_mean",
    "cer_dipl_median",
    "wer_norm_median",
    "nls_norm_median",
    "ro_cost_median",
    "entity_recall_median",
    "entity_pages",
    "seg_fail_rate",
)
_GAP_KEYS = (
    "missing_pages",
    "skipped_no_gt",
    "unannotated_pages",
    "unbound_image_pages",
    "invalid_adjudications",
    "error_pages",
    "annex_failed_pages",
    "loop_guard_pages",
)
_INCOMPLETE_KEYS = _GAP_KEYS[:5]


def public_aggregates(run_meta: dict, scores: dict[str, dict], harness_commit: str) -> dict:
    return {
        "run_id": run_meta.get("run_id"),
        "created": run_meta.get("created"),
        "protocol_version": PROTOCOL_VERSION,
        "scoring_schema_version": SCORING_SCHEMA_VERSION,
        "harness_commit": harness_commit,
        "min_group": MIN_GROUP,
        "engines": {name: _engine(data) for name, data in scores.items()},
    }


def _engine(data: dict) -> dict:
    aggregate = data["aggregate"]
    kill = aggregate["kill_check"]
    proxy = [
        score["long_ins_rate_v01"]
        for score in data["pages"].values()
        if score.get("long_ins_rate_v01") is not None
    ]
    overall = aggregate["overall"]
    annex = aggregate["annex"]
    return {
        "overall": _group(overall),
        "hard_strata": _group(aggregate["hard_strata"]),
        "per_stratum": {
            name: _group(stats) for name, stats in aggregate["per_stratum"].items()
        },
        "kill_check": {
            key: kill[key] for key in ("eligible", "complete", "conditions_met", "kill")
        },
        "t3_status": aggregate["trust_check"]["status"],
        "fabrication_proxy_unadjudicated": None
        if len(proxy) < MIN_GROUP
        else {
            "metric": "long_ins_rate_v01",
            "median": overall["long_ins_rate_v01_median"],
            "mean": overall["long_ins_rate_v01_mean"],
            "micro": overall["long_ins_rate_v01_micro"],
            f"pages_above_{FAB_PROXY_CUT:.2f}": sum(v > FAB_PROXY_CUT for v in proxy),
        },
        "annex": {
            "pages": annex["pages"],
            "abstention_ok": annex["abstention_ok"],
            "hallucinated_chars_total": sum(annex["hallucinated_chars"].values()),
        },
        "gaps": {key: len(data.get(key) or []) for key in _GAP_KEYS},
    }


def _group(stats: dict) -> dict:
    if stats["n"] < MIN_GROUP:
        return {"n": stats["n"], "suppressed": True}
    return {"n": stats["n"], **{key: stats.get(key) for key in _PUBLIC_STATS}}


def incomplete(public: dict) -> bool:
    return any(
        engine["gaps"][key] for engine in public["engines"].values() for key in _INCOMPLETE_KEYS
    )


def render_public_report(public: dict) -> str:
    engines = public["engines"]
    lines = [
        f"# Benchmark aggregates — {public['run_id']}",
        "",
        f"Protocol {public['protocol_version']} · scoring schema "
        f"{public['scoring_schema_version']} · harness `{public['harness_commit'][:12]}`.",
        "",
        "Aggregates only: no page IDs, page scores, or page text. Groups of fewer than "
        f"{MIN_GROUP} pages are suppressed; strata of fewer than {INDICATIVE_BELOW} pages are "
        "indicative.",
        "",
    ]
    if incomplete(public):
        lines += ["**INCOMPLETE REPORT — run gaps remain; do not publish.**", ""]
    lines += [
        "## Overall",
        "",
        "| engine | n | cer_norm median | cer_norm mean | cer_dipl median | wer_norm median | nls_norm median | entity recall median | seg-fail |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, engine in engines.items():
        lines.append(f"| {name} | " + _row(engine["overall"], (
            "cer_norm_median", "cer_norm_mean", "cer_dipl_median", "wer_norm_median",
            "nls_norm_median", "entity_recall_median")))
    lines += [
        "",
        "## Hard strata (§8)",
        "",
        "| engine | n | cer_norm median | entity recall median | seg-fail | would trigger kill |",
        "|---|---|---|---|---|---|",
    ]
    for name, engine in engines.items():
        kill = engine["kill_check"]
        verdict = "KILL" if kill["kill"] else "no" if kill["eligible"] else "not eligible"
        lines.append(
            f"| {name} | "
            + _row(engine["hard_strata"], ("cer_norm_median", "entity_recall_median"))
            + f" {verdict} |"
        )
    lines += [
        "",
        "## Per stratum (primary)",
        "",
        "| engine | stratum | n | cer_norm median | cer_norm mean | entity recall median | seg-fail |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, engine in engines.items():
        for stratum, group in engine["per_stratum"].items():
            label = stratum if group["n"] >= INDICATIVE_BELOW else f"{stratum} (indicative)"
            lines.append(f"| {name} | {label} | " + _row(group, (
                "cer_norm_median", "cer_norm_mean", "entity_recall_median")))
    lines += [
        "",
        "## Automatic fabrication proxy (unadjudicated, not a fabrication verdict)",
        "",
        f"| engine | long insertion v0.1 median / mean / micro | pages above {FAB_PROXY_CUT:.2f} | T3 |",
        "|---|---|---|---|",
    ]
    for name, engine in engines.items():
        proxy = engine["fabrication_proxy_unadjudicated"]
        cells = (
            "— | —"
            if proxy is None
            else f"{_fmt(proxy['median'])} / {_fmt(proxy['mean'])} / {_fmt(proxy['micro'])} "
            f"| {proxy[f'pages_above_{FAB_PROXY_CUT:.2f}']}"
        )
        lines.append(f"| {name} | {cells} | {engine['t3_status']} |")
    lines += [
        "",
        "## Annex pages (reported only; not a fabrication signal, §10 2026-10-18)",
        "",
        "| engine | pages | without text output | characters output (total) |",
        "|---|---|---|---|",
    ]
    for name, engine in engines.items():
        annex = engine["annex"]
        lines.append(
            f"| {name} | {annex['pages']} | {annex['abstention_ok']} "
            f"| {annex['hallucinated_chars_total']} |"
        )
    lines += [
        "",
        "## Run gaps (page counts)",
        "",
        "| engine | " + " | ".join(key.replace("_", " ") for key in _GAP_KEYS) + " |",
        "|---|" + "---|" * len(_GAP_KEYS),
    ]
    for name, engine in engines.items():
        lines.append(
            f"| {name} | " + " | ".join(str(engine["gaps"][key]) for key in _GAP_KEYS) + " |"
        )
    lines.append("")
    return "\n".join(lines)


def _row(group: dict, medians: tuple[str, ...]) -> str:
    if group.get("suppressed"):
        return f"{group['n']} | " + " | ".join("suppressed" for _ in (*medians, "seg")) + " |"
    cells = [_fmt(group[key]) for key in medians] + [_fmt(group["seg_fail_rate"], pct=True)]
    return f"{group['n']} | " + " | ".join(cells) + " |"


def leaks(texts: list[str], pages: list[GoldPage], run_meta: dict) -> list[str]:
    """Page IDs and run-metadata paths found in any of the rendered texts."""
    found = []
    for page in pages:
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(page.id)}(?![A-Za-z0-9])")
        if any(pattern.search(text) for text in texts):
            found.append(f"page ID {page.id}")
    for key, value in run_meta.items():
        if key.endswith(("_dir", "_path")) and value and any(str(value) in t for t in texts):
            found.append(f"run metadata path {key}")
    return found


def dump_json(public: dict) -> str:
    return json.dumps(public, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
