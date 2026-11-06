from harness.adjudication import adjudication_template, score_adjudication
from harness.gold import GoldPage
from harness.report import _binomial_upper_bound, _stats, aggregate
from harness.report_markdown import _adjudicated_examples, _run_gaps, render_report
from harness.scoring import score_page


def _adjudicate(hyp: str, fab_end: int = 0) -> dict:
    score = score_page(hyp, hyp)
    score["image_sha256"] = "a" * 64
    form = adjudication_template("eng", "G01", score)
    manual_spans = (
        [{"start": 0, "end": fab_end, "label": "fluent_fabrication"}] if fab_end else []
    )
    for index, review in enumerate(form["reviews"]):
        review["reviewer"] = f"reviewer-{index + 1}"
        review["full_page_reviewed"] = True
        review["added_spans"] = [dict(item) for item in manual_spans]
        for item in review["candidate_labels"]:
            item["label"] = "supported"
        for item in review["entity_labels"]:
            item["label"] = "supported"
    form["spans"] = manual_spans
    for item in form["entities"]:
        item["label"] = "supported"
    score.update(
        score_adjudication(
            form, engine="eng", page="G01", hyp_norm=hyp, page_score=score
        )
    )
    return score


def test_adjudicated_stats_expose_mean_micro_incidence_max_and_thresholds():
    stats = _stats([_adjudicate("abcdefghij", fab_end=2), _adjudicate("klmnopqrst")])
    assert stats["fab_rate_adj_mean"] == 0.1
    assert stats["fab_rate_adj_micro"] == 0.1
    assert stats["fab_page_rate_adj"] == 0.5
    assert stats["fab_rate_adj_max"] == 0.2
    assert stats["fab_rate_adj_above"] == {">0.01": 1, ">0.05": 1, ">0.10": 1}


def test_excess_length_reports_macro_and_micro_rates():
    score = score_page("abcde", "abcdefghij")
    stats = _stats([score])
    assert stats["excess_length_rate_median"] == 0.5
    assert stats["excess_length_rate_mean"] == 0.5
    assert stats["excess_length_rate_micro"] == 0.5


def test_zero_incidence_exact_upper_bound_matches_rule_of_three_scale():
    upper = _binomial_upper_bound(0, 53)
    assert upper is not None
    assert 0.054 < upper < 0.056


def test_t3_never_emits_pass_before_threshold_ratification():
    pages = [
        GoldPage(id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True),
        GoldPage(id="G02", image_name="G02.jpg", strata=("tidy_kurrent",), scored=True),
    ]
    scores = {"G01": _adjudicate("abcdefghij"), "G02": _adjudicate("klmnopqrst")}
    result = aggregate(scores, {}, pages)
    assert result["trust_check"] == {
        "status": "unresolved",
        "pass": None,
        "thresholds_ratified": False,
        "complete": True,
        "adjudicated_pages": 2,
        "expected_pages": 2,
        "annex_complete": True,
        "annex_clean": True,
        "reason": "T3 thresholds require a blinded pilot and protocol amendment",
    }


def test_report_names_legacy_metric_and_labels_candidates_as_non_verdicts():
    page = GoldPage(
        id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True
    )
    score = _adjudicate("abcdefghij", fab_end=2)
    aggregate_result = aggregate({"G01": score}, {}, [page])
    report = render_report(
        {"run_id": "test", "created": "now"},
        {
            "eng": {
                "aggregate": aggregate_result,
                "pages": {"G01": score},
                "error_pages": [],
                "annex_failed_pages": [],
                "missing_pages": [],
                "invalid_adjudications": [],
            }
        },
    )
    assert "long insertion v0.1" in report
    assert (
        "Automatic review candidates (not labels)" not in report
    )  # none on exact text
    assert (
        "automatic trust fields are review diagnostics, not fabrication labels"
        in report
    )
    assert "No PASS/FAIL is emitted" in report


def test_agreement_is_pooled_from_confusion_margins_not_page_kappas():
    first = _adjudicate("abcdefghij")
    second = _adjudicate("klmnopqrst")
    first["candidate_review_agreement"] = {
        "items": 1,
        "agreements": 1,
        "raw_agreement": 1.0,
        "cohen_kappa": None,
        "class_counts": {
            "reviewer_1": {"supported": 1},
            "reviewer_2": {"supported": 1},
        },
        "confusion": {"supported": {"supported": 1}},
    }
    second["candidate_review_agreement"] = {
        "items": 1,
        "agreements": 0,
        "raw_agreement": 0.0,
        "cohen_kappa": 0.0,
        "class_counts": {
            "reviewer_1": {"supported": 1},
            "reviewer_2": {"fluent_fabrication": 1},
        },
        "confusion": {"supported": {"fluent_fabrication": 1}},
    }
    pooled = _stats([first, second])["candidate_review_agreement"]
    assert pooled["items"] == 2
    assert pooled["raw_agreement"] == 0.5
    assert pooled["label_raw_agreement"] == 0.5
    assert pooled["cohen_kappa"] == 0.0
    assert pooled["confusion"] == {
        "supported": {"fluent_fabrication": 1, "supported": 1}
    }


def test_fabrication_examples_include_every_severe_page_after_top_five():
    pages = {
        f"G{index:02d}": {
            "fab_rate_adj": 0.2,
            "adjudicated_spans": [
                {
                    "start": 0,
                    "end": index,
                    "text": "x" * index,
                    "label": "fluent_fabrication",
                }
            ],
        }
        for index in range(1, 8)
    }
    assert {page for page, _ in _adjudicated_examples(pages)} == set(pages)


def test_report_surfaces_uncertainty_reliability_and_all_gap_classes():
    page = GoldPage(
        id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True
    )
    score = _adjudicate("abcdefghij")
    score["adjudicated_spans"] = [
        {"start": 0, "end": 3, "text": "abc", "label": "gt_or_image_uncertain"}
    ]
    score["adjudicated_entities"] = [
        {"start": 4, "end": 7, "text": "efg", "kind": "person", "label": "uncertain"}
    ]
    data = {
        "aggregate": aggregate({"G01": score}, {}, [page]),
        "pages": {"G01": score},
        "error_pages": [],
        "annex_failed_pages": [],
        "missing_pages": [],
        "skipped_no_gt": ["G02"],
        "unannotated_pages": ["G03"],
        "unbound_image_pages": ["G04"],
        "invalid_adjudications": [],
    }
    report = render_report({"run_id": "test", "created": "now"}, {"eng": data})
    assert "INCOMPLETE REPORT" in report
    assert "pages skipped because transcription GT is missing" in report
    assert "pages missing entity annotations" in report
    assert "outputs without a valid image hash" in report
    assert "Review reliability" in report
    assert "Cohen’s κ" in report
    assert "All uncertain span cases" in report and "abc" in report
    assert "All uncertain entity cases" in report and "efg" in report
    assert "entity precision" in report
    assert "decision coverage" in report
    assert "excess length" in report
    assert _run_gaps(data)


def test_recorded_engine_failure_is_not_labeled_an_incomplete_report():
    page = GoldPage(
        id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True
    )
    score = _adjudicate("")
    data = {
        "aggregate": aggregate({"G01": score}, {}, [page]),
        "pages": {"G01": score},
        "error_pages": ["G01"],
        "annex_failed_pages": [],
        "missing_pages": [],
        "skipped_no_gt": [],
        "unannotated_pages": [],
        "invalid_adjudications": [],
    }
    report = render_report({"run_id": "test", "created": "now"}, {"eng": data})
    assert "failed pages scored as empty output" in report
    assert "INCOMPLETE REPORT" not in report


def test_kappa_is_not_pooled_across_different_or_swapped_reviewer_pairs():
    first = _adjudicate("abcdefghij")
    second = _adjudicate("klmnopqrst")
    second["adjudication_reviewers"] = ["reviewer-2", "reviewer-1"]
    stats = _stats([first, second])
    assert stats["reviewer_pair_consistent"] is False
    assert stats["candidate_review_agreement"]["items"] == 0
    assert "adjudication_reviewer_pairs" not in stats


def test_t3_completeness_does_not_wait_for_annex_pages():  # D2 (tests/test_e2e.py)
    pages = [
        GoldPage(id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True),
        GoldPage(id="A01", image_name="A01_annex.jpg", strata=(), scored=False),
    ]
    result = aggregate({"G01": _adjudicate("abcdefghij")}, {}, pages)
    assert result["trust_check"]["complete"] is True
    assert result["trust_check"]["annex_complete"] is False


def test_report_labels_annex_results_as_reported_only():  # D3 (tests/test_e2e.py)
    pages = [
        GoldPage(id="G01", image_name="G01.jpg", strata=("tidy_kurrent",), scored=True),
        GoldPage(id="A01", image_name="A01_annex.jpg", strata=(), scored=False),
    ]
    score = _adjudicate("abcdefghij")
    annex = {"A01": {"abstention_ok": False, "hallucinated_chars": 120, "image_sha256": "a" * 64}}
    data = {
        "aggregate": aggregate({"G01": score}, annex, pages),
        "pages": {"G01": score},
        "annex_pages": annex,
        "error_pages": [],
        "annex_failed_pages": [],
        "missing_pages": [],
        "skipped_no_gt": [],
        "unannotated_pages": [],
        "invalid_adjudications": [],
    }
    report = render_report({"run_id": "test", "created": "now"}, {"eng": data})
    assert "not a fabrication signal" in report
    assert "abstention-clean" not in report
