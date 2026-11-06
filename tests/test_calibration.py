import json

from harness.calibration import (
    CalibrationConfig,
    build_fixture_cases,
    main,
    run_calibration,
)
from harness.scoring import score_page


def test_fixture_generation_is_seeded_and_covers_requested_dimensions():
    config = CalibrationConfig(
        seed=41,
        span_sizes=(3, 5),
        positions=("start", "middle", "end"),
        pages=("dev_letter", "dev_register"),
    )
    first = build_fixture_cases(config=config)
    second = build_fixture_cases(config=config)
    assert first == second
    injected = [case for case in first if case["category"] == "injected_span"]
    assert {case["span_size"] for case in injected} == {3, 5}
    assert {case["position"] for case in injected} == {"start", "middle", "end"}
    assert {case["mode"] for case in injected} == {
        "appended",
        "equal",
        "shorter",
        "longer",
    }
    assert len({case["id"] for case in first}) == len(first)


def test_calibration_report_keeps_automatic_diagnostics_separate_from_labels():
    config = CalibrationConfig(
        seed=9,
        span_sizes=(3, 5),
        positions=("middle",),
        pages=("dev_letter",),
    )
    report = run_calibration(config=config)
    assert report["diagnostic_only"] is True
    assert report["human_labels"] == {
        "included": False,
        "performed": False,
        "source": None,
    }
    assert report["t3"]["status"] == "unresolved"
    assert report["t3"]["pass"] is None
    assert report["injected_span_recall"]["coverage_rule"].startswith("union")
    assert report["injected_span_recall"]["overlap_alone_is_not_recall"] is True
    assert report["high_risk_entity_recall"]["recall"] == 1.0
    assert report["review_volume"]["candidate_spans"] >= 0
    assert report["report_sha256"]


def test_candidate_offsets_are_normalized_and_controls_report_failures():
    config = CalibrationConfig(
        seed=12,
        span_sizes=(5,),
        positions=("middle",),
        pages=("dev_letter",),
    )
    cases = build_fixture_cases(config=config)
    for case in cases:
        if "injected_span" not in case:
            continue
        injected = case["injected_span"]
        normalized = " ".join(case["hyp"].split())
        assert case["offset_space"] == "normalized_hypothesis"
        assert normalized[injected["start"] : injected["end"]] == injected["text"]
    report = run_calibration(cases)
    controls = report["benign_zero_candidate_controls"]
    assert controls["passed"] is True
    assert report["failure_count"] >= 0
    assert all("details" in failure for failure in report["failures"])


def test_v02_recalls_realistic_five_word_replacement_missed_by_v01_defaults():
    config = CalibrationConfig(
        seed=20260906,
        span_sizes=(5,),
        positions=("start",),
        pages=("dev_invoice",),
    )
    case = next(
        case
        for case in build_fixture_cases(config=config)
        if case["id"] == "inject_dev_invoice_equal_5_start"
    )
    scores = score_page(case["gold"], case["hyp"])
    injected = case["injected_span"]
    assert any(
        span["text"] == injected["text"]
        and span["start"] == injected["start"]
        and span["end"] == injected["end"]
        for span in scores["review_candidate_spans_auto"]
    )


def test_calibration_cli_emits_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "harness.calibration.run_calibration",
        lambda **kwargs: {"seed": kwargs["seed"], "diagnostic_only": True},
    )
    assert main(["--seed", "77", "--indent", "0"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "diagnostic_only": True,
        "seed": 77,
    }
