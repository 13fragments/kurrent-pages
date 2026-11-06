"""Markdown rendering for benchmark aggregates."""

from __future__ import annotations

from harness import PROTOCOL_VERSION, SCORING_SCHEMA_VERSION


def render_report(run_meta: dict, engines: dict[str, dict]) -> str:
    lines = [
        f"# Benchmark report — {run_meta.get('run_id', 'unnamed run')}",
        "",
        f"Protocol {PROTOCOL_VERSION} · scoring schema {SCORING_SCHEMA_VERSION} · "
        f"generated {run_meta.get('created', '?')}.",
        "",
        "The automatic trust fields are review diagnostics, not fabrication labels. "
        "Only complete image-grounded adjudication can populate the `*_adj` fields; "
        "T3 remains unresolved until its thresholds are ratified.",
        "",
    ]
    if any(_report_incomplete(data) for data in engines.values()):
        lines += [
            "**INCOMPLETE REPORT — run gaps remain; do not treat these results as final.**",
            "",
        ]
    lines += [
        "## Accuracy summary",
        "",
        "| engine | n | cer_dipl med | cer_norm med | wer_norm med | nls_norm med | ro_cost med | ent. recall med | seg-fail |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, data in engines.items():
        overall = data["aggregate"]["overall"]
        lines.append(
            f"| {name} | {overall['n']} | {_fmt(overall['cer_dipl_median'])} "
            f"| {_fmt(overall['cer_norm_median'])} | {_fmt(overall['wer_norm_median'])} "
            f"| {_fmt(overall['nls_norm_median'])} | {_fmt(overall['ro_cost_median'])} "
            f"| {_fmt(overall['entity_recall_median'])} "
            f"| {_fmt(overall['seg_fail_rate'], pct=True)} |"
        )
    lines.extend(_automatic_summary(engines))
    lines.extend(_adjudication_summary(engines))
    lines.extend(_kill_summary(engines))
    for name, data in engines.items():
        lines.extend(_engine_detail(name, data))
    lines.append("")
    return "\n".join(lines)


def _automatic_summary(engines: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Automatic trust diagnostics (not fabrication verdicts)",
        "",
        "Each rate cell is median / mean / micro; tail cells are maximum page rate.",
        "",
        "| engine | hyp-char error | omission | excess length | long insertion v0.1 | review candidate | repeat-4gram mean / max |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, data in engines.items():
        overall = data["aggregate"]["overall"]
        lines.append(
            f"| {name} | {_triple(overall, 'hyp_char_error')} "
            f"| {_triple(overall, 'omission_rate')} "
            f"| {_triple(overall, 'excess_length_rate')} "
            f"| {_triple(overall, 'long_ins_rate_v01')} "
            f"| {_triple(overall, 'review_candidate_rate_auto')} "
            f"| {_fmt(overall['repeat_4gram_rate_mean'])} / "
            f"{_fmt(overall['repeat_4gram_rate_max'])} |"
        )
    return lines


def _adjudication_summary(engines: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Image-grounded adjudication and draft T3",
        "",
        "| engine | T3 status | adjudicated | fabrication median / mean / micro | affected pages (rate; upper 95%) | max page | degenerate micro | entity precision / decision coverage | fabricated / non-entity candidates | uncertain spans / entities | disagreements |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, data in engines.items():
        aggregate = data["aggregate"]
        overall = aggregate["overall"]
        trust = aggregate["trust_check"]
        affected = (
            f"{overall['fab_page_count']} ({_fmt(overall['fab_page_rate_adj'], pct=True)}; "
            f"{_fmt(overall['fab_page_rate_adj_upper95'], pct=True)})"
            if overall["adjudicated_pages"]
            else "—"
        )
        lines.append(
            f"| {name} | **{trust['status']}** | {overall['adjudicated_pages']}/{trust['expected_pages']} "
            f"| {_fmt(overall['fab_rate_adj_median'])} / "
            f"{_fmt(overall['fab_rate_adj_mean'])} / {_fmt(overall['fab_rate_adj_micro'])} "
            f"| {affected} | {_fmt(overall['fab_rate_adj_max'])} "
            f"| {_fmt(overall['degenerate_rate_adj_micro'])} "
            f"| {_fmt(overall['entity_precision_adj_micro'])} / "
            f"{_fmt(overall['entity_decision_coverage_adj'])} "
            f"| {overall['fabricated_entity_count']} / "
            f"{overall['entity_not_entity_adj_total']} "
            f"| {overall['adjudication_label_counts'].get('gt_or_image_uncertain', 0)} / "
            f"{overall['entity_uncertain_adj_total']} "
            f"| {overall['adjudication_disagreements']} |"
        )
    lines += _reliability_summary(engines)
    lines += [
        "",
        "No PASS/FAIL is emitted: the blinded pilot and protocol amendment have not occurred.",
    ]
    return lines


def _reliability_summary(engines: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "Review reliability (exact raw agreement includes boundary/kind agreement; "
        "label κ is pooled from label confusion and marginals, never averaged by page):",
        "",
        "| engine | decisions | items | exact raw | label raw | label Cohen’s κ | reviewer 1 classes | reviewer 2 classes | confusion |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    fields = (
        ("automatic spans", "candidate_review_agreement"),
        ("reviewer-added spans", "manual_span_review_agreement"),
        ("automatic entities", "entity_review_agreement"),
        ("reviewer-added entities", "manual_entity_review_agreement"),
    )
    for name, data in engines.items():
        overall = data["aggregate"]["overall"]
        for label, field in fields:
            agreement = overall[field]
            classes = agreement["class_counts"]
            lines.append(
                f"| {name} | {label} | {agreement['items']} "
                f"| {_fmt(agreement['raw_agreement'])} "
                f"| {_fmt(agreement['label_raw_agreement'])} "
                f"| {_fmt(agreement['cohen_kappa'])} "
                f"| `{classes['reviewer_1']}` | `{classes['reviewer_2']}` "
                f"| `{agreement['confusion']}` |"
            )
    return lines


def _kill_summary(engines: dict[str, dict]) -> list[str]:
    lines = [
        "",
        "## Gate 0 kill criterion (§8, hard-strata set)",
        "",
        "Applies to open CRNN end-to-end configs only; VLM rows shown for reference.",
        "",
        "| engine | n | median cer_norm | median ent. recall | seg-fail rate | would trigger kill |",
        "|---|---|---|---|---|---|",
    ]
    for name, data in engines.items():
        hard = data["aggregate"]["hard_strata"]
        check = data["aggregate"]["kill_check"]
        if check["kill"]:
            verdict = "KILL"
        elif not check.get("eligible"):
            verdict = "not eligible"
        elif not check["complete"]:
            verdict = f"incomplete ({check['scored_pages']}/{check['expected_pages']})"
        else:
            verdict = "no"
        lines.append(
            f"| {name} | {hard['n']} | {_fmt(hard['cer_norm_median'])} "
            f"| {_fmt(hard['entity_recall_median'])} "
            f"| {_fmt(hard['seg_fail_rate'], pct=True)} | **{verdict}** |"
        )
    return lines


def _engine_detail(name: str, data: dict) -> list[str]:
    aggregate = data["aggregate"]
    lines = [
        "",
        f"## {name}",
        "",
        "| stratum (primary) | n | cer med / mean | omission mean / micro | review-candidate mean / micro / max | adjudicated | fab median / mean / micro / incidence / max | fab pages >1% / >5% / >10% | entity precision / decision coverage | fabricated / non-entity candidates | uncertain spans / entities |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for stratum, stats in aggregate["per_stratum"].items():
        lines.append(
            f"| {stratum} | {stats['n']} "
            f"| {_fmt(stats['cer_norm_median'])} / {_fmt(stats['cer_norm_mean'])} "
            f"| {_fmt(stats['omission_rate_mean'])} / {_fmt(stats['omission_rate_micro'])} "
            f"| {_fmt(stats['review_candidate_rate_auto_mean'])} / "
            f"{_fmt(stats['review_candidate_rate_auto_micro'])} / "
            f"{_fmt(stats['review_candidate_rate_auto_max'])} "
            f"| {stats['adjudicated_pages']}/{stats['n']} "
            f"| {_fmt(stats['fab_rate_adj_median'])} / {_fmt(stats['fab_rate_adj_mean'])} / "
            f"{_fmt(stats['fab_rate_adj_micro'])} / "
            f"{_fmt(stats['fab_page_rate_adj'], pct=True)} / {_fmt(stats['fab_rate_adj_max'])} "
            f"| {_severity_counts(stats['fab_rate_adj_above'])} "
            f"| {_fmt(stats['entity_precision_adj_micro'])} / "
            f"{_fmt(stats['entity_decision_coverage_adj'])} "
            f"| {stats['fabricated_entity_count']} / "
            f"{stats['entity_not_entity_adj_total']} "
            f"| {stats['adjudication_label_counts'].get('gt_or_image_uncertain', 0)} / "
            f"{stats['entity_uncertain_adj_total']} |"
        )
    lines.extend(_all_tag_table(aggregate))
    lines.extend(_risk_notes(data))
    return lines


def _all_tag_table(aggregate: dict) -> list[str]:
    lines = [
        "",
        "All-tag cuts (pages counted under every tag they carry):",
        "",
        "| tag | n | cer_norm med | ent. recall | seg-fail |",
        "|---|---|---|---|---|",
    ]
    for tag, stats in aggregate["per_tag"].items():
        lines.append(
            f"| {tag} | {stats['n']} | {_fmt(stats['cer_norm_median'])} "
            f"| {_fmt(stats['entity_recall_median'])} "
            f"| {_fmt(stats['seg_fail_rate'], pct=True)} |"
        )
    return lines


def _risk_notes(data: dict) -> list[str]:
    aggregate = data["aggregate"]
    overall = aggregate["overall"]
    annex = aggregate["annex"]
    cluster = aggregate["hand_cluster_sensitivity"]
    lines = [
        "",
        f"Adjudicated severity counts (`>1%`, `>5%`, `>10%`): fabrication "
        f"{overall['fab_rate_adj_above']}; combined trust failures "
        f"{overall['trust_failure_rate_adj_above']}.",
        "",
        f"Hand-cluster sensitivity: {cluster['affected_clusters']}/{cluster['clusters']} affected; "
        f"one-sided upper 95% {_fmt(cluster['affected_rate_upper95'], pct=True)}.",
        "",
        f"Final span labels: `{overall['adjudication_label_counts']}`; "
        f"final entity labels: `{overall['entity_label_counts']}`.",
        "",
        f"Ordered reviewer pair consistent: {overall['reviewer_pair_consistent']}. "
        "Reviewer identities remain private.",
    ]
    if annex["pages"]:
        lines += [
            "",
            f"Annex pages (reported only; both contain real text, so this is not a "
            f"fabrication signal; §10, 2026-10-18): {annex['abstention_ok']}/{annex['pages']} "
            f"without text output; characters output: {annex['hallucinated_chars']}.",
        ]
    gaps = _run_gaps(data)
    if gaps:
        lines += ["", "**Run gaps:** " + "; ".join(gaps)]
    for title, examples in (
        ("Adjudicated fabrication examples", _adjudicated_examples(data["pages"])),
        ("All uncertain span cases", _uncertain_span_examples(data["pages"])),
        ("All uncertain entity cases", _uncertain_entity_examples(data["pages"])),
        (
            "Automatic review candidates (not labels)",
            _candidate_examples(data["pages"]),
        ),
        ("Legacy v0.1 long-insertion examples", _legacy_examples(data["pages"])),
    ):
        if examples:
            lines += ["", f"{title}:", ""]
            lines += [f"- `{page}`: “{text}”" for page, text in examples]
    return lines


def _run_gaps(data: dict) -> list[str]:
    gaps = []
    for key, description in (
        ("error_pages", "failed pages scored as empty output"),
        ("annex_failed_pages", "annex pages without output (reported only, §10 2026-10-18)"),
        ("missing_pages", "pages with no output"),
        ("skipped_no_gt", "pages skipped because transcription GT is missing"),
        ("unannotated_pages", "pages missing entity annotations"),
        ("unbound_image_pages", "outputs without a valid image hash"),
        ("invalid_adjudications", "invalid adjudications"),
        ("loop_guard_pages", "token-limited outputs scored without their trailing loop (§10, 2026-10-16)"),
    ):
        if data.get(key):
            gaps.append(f"{description}: {data[key]}")
    return gaps


def _report_incomplete(data: dict) -> bool:
    return any(
        data.get(key)
        for key in (
            "missing_pages",
            "skipped_no_gt",
            "unannotated_pages",
            "unbound_image_pages",
            "invalid_adjudications",
        )
    )


def _adjudicated_examples(
    pages: dict[str, dict], limit: int = 5
) -> list[tuple[str, str]]:
    examples = [
        (
            page,
            span["text"],
            scores.get("fab_rate_adj", 0.0),
            span["start"],
            span["end"],
        )
        for page, scores in pages.items()
        for span in scores.get("adjudicated_spans", [])
        if span["label"] == "fluent_fabrication"
    ]
    examples.sort(key=lambda item: (-item[2], -len(item[1]), item[0], item[3]))
    top_by_page = []
    seen_pages = set()
    for example in examples:
        if example[0] in seen_pages:
            continue
        top_by_page.append(example)
        seen_pages.add(example[0])
        if len(top_by_page) == limit:
            break
    selected = {
        (page, start, end): (page, text)
        for page, text, rate, start, end in examples
        if rate > 0.10
    }
    for page, text, _, start, end in top_by_page:
        selected[(page, start, end)] = (page, text)
    return list(selected.values())


def _uncertain_span_examples(pages: dict[str, dict]) -> list[tuple[str, str]]:
    return [
        (page, span["text"])
        for page, scores in pages.items()
        for span in scores.get("adjudicated_spans", [])
        if span["label"] == "gt_or_image_uncertain"
    ]


def _uncertain_entity_examples(pages: dict[str, dict]) -> list[tuple[str, str]]:
    return [
        (page, entity["text"])
        for page, scores in pages.items()
        for entity in scores.get("adjudicated_entities", [])
        if entity["label"] == "uncertain"
    ]


def _candidate_examples(
    pages: dict[str, dict], limit: int = 5
) -> list[tuple[str, str]]:
    return _longest(
        (page, span["text"])
        for page, scores in pages.items()
        for span in scores.get("review_candidate_spans_auto", [])
    )[:limit]


def _legacy_examples(pages: dict[str, dict], limit: int = 5) -> list[tuple[str, str]]:
    return _longest(
        (page, span)
        for page, scores in pages.items()
        for span in scores.get("long_ins_spans_v01", [])
    )[:limit]


def _longest(items) -> list[tuple[str, str]]:
    return sorted(items, key=lambda item: len(item[1]), reverse=True)


def _triple(stats: dict, metric: str) -> str:
    return " / ".join(
        _fmt(stats.get(f"{metric}_{suffix}")) for suffix in ("median", "mean", "micro")
    )


def _severity_counts(counts: dict[str, int]) -> str:
    return " / ".join(str(counts[key]) for key in (">0.01", ">0.05", ">0.10"))


def _fmt(value, pct: bool = False) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return f"{value:.0%}" if pct else f"{value:.3f}"
