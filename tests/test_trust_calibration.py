from pathlib import Path

import pytest
import yaml

from harness.scoring import score_page

FIXTURE = Path(__file__).parent / "fixtures" / "trust_metric_cases.yml"
CASES = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_frozen_trust_metric_cases(case: dict):
    scores = score_page(case["gold"], case["hyp"])
    if "candidate" in case:
        assert bool(scores["review_candidate_spans_auto"]) is case["candidate"]
    if "long_insertion" in case:
        assert (scores["long_ins_rate_v01"] > 0) is case["long_insertion"]
    if "omission_min" in case:
        assert scores["omission_rate"] >= case["omission_min"]
    if "repeat_min" in case:
        assert scores["repeat_4gram_rate"] >= case["repeat_min"]
    if "entity_texts" in case:
        candidates = {item["text"] for item in scores["entity_risk_candidates"]}
        assert candidates.issuperset(case["entity_texts"])


def test_fabrication_candidate_recall_target_on_frozen_fixture():
    fabricated = [case for case in CASES if case["kind"] == "fabrication"]
    recalled = 0
    for case in fabricated:
        scores = score_page(case["gold"], case["hyp"])
        start = case["hyp"].index(case["injected"])
        end = start + len(case["injected"])
        covered = set()
        for span in scores["review_candidate_spans_auto"]:
            covered.update(range(max(start, span["start"]), min(end, span["end"])))
        recalled += len(covered) / (end - start) >= 0.95
    assert recalled / len(fabricated) >= 0.95
