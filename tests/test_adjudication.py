import pytest

from harness.adjudication import (
    AdjudicationError,
    adjudication_template,
    score_adjudication,
)
from harness.adjudication_reliability import manual_agreement
from harness.scoring import score_page


def _form(
    score: dict,
    *,
    manual_spans: list[dict] | None = None,
    manual_entities: list[dict] | None = None,
) -> dict:
    score.setdefault("image_sha256", "a" * 64)
    form = adjudication_template("engine-a", "G01", score)
    for index, review in enumerate(form["reviews"]):
        review["reviewer"] = f"reviewer-{index + 1}"
        review["full_page_reviewed"] = True
        for item in review["candidate_labels"]:
            item["label"] = "supported"
        for item in review["entity_labels"]:
            item["label"] = "supported"
    for item in form["spans"]:
        item["label"] = "supported"
    for item in form["entities"]:
        item["label"] = "supported"
    for span in manual_spans or []:
        form["spans"].append(dict(span))
        for review in form["reviews"]:
            review["added_spans"].append(dict(span))
    for entity in manual_entities or []:
        form["manual_entities"].append(dict(entity))
        for review in form["reviews"]:
            review["manual_entities"].append(dict(entity))
    return form


def _set_candidate_label(form: dict, candidate_id: str, label: str) -> None:
    for review in form["reviews"]:
        next(
            item
            for item in review["candidate_labels"]
            if item["candidate_id"] == candidate_id
        )["label"] = label
    next(item for item in form["spans"] if item["candidate_id"] == candidate_id)[
        "label"
    ] = label


def _set_entity_label(form: dict, candidate_id: str, label: str) -> None:
    for review in form["reviews"]:
        next(
            item
            for item in review["entity_labels"]
            if item["candidate_id"] == candidate_id
        )["label"] = label
    next(item for item in form["entities"] if item["candidate_id"] == candidate_id)[
        "label"
    ] = label


def _score(form: dict, hyp: str, page_score: dict) -> dict:
    return score_adjudication(
        form,
        engine="engine-a",
        page="G01",
        hyp_norm=hyp,
        page_score=page_score,
    )


def test_adjudication_derives_fabrication_and_degenerate_rates():
    hyp = "eins zwei drei fremder inhalt ohne bild jetzt loop loop loop"
    score = score_page(hyp, hyp)
    fab_start, fab_end = hyp.index("fremder"), hyp.index(" loop")
    degenerate_start = hyp.index("loop")
    form = _form(
        score,
        manual_spans=[
            {"start": fab_start, "end": fab_end, "label": "fluent_fabrication"},
            {
                "start": degenerate_start,
                "end": len(hyp),
                "label": "degenerate_generation",
            },
        ],
    )
    result = _score(form, hyp, score)
    assert result["adjudication_status"] == "complete"
    assert result["fab_chars_adj"] == fab_end - fab_start
    assert result["fab_page"] is True
    assert result["trust_failure_chars_adj"] == (fab_end - fab_start) + (
        len(hyp) - degenerate_start
    )


def test_entity_candidates_must_all_be_labeled_and_can_be_fabricated():
    hyp = "Brief von Hans Müller am 18.12.1924"
    score = score_page("brief", hyp)
    form = _form(score)
    for candidate in score["entity_risk_candidates"]:
        if candidate["text"] in {"Hans Müller", "18.12.1924"}:
            _set_entity_label(form, candidate["id"], "fabricated")
    result = _score(form, hyp, score)
    assert [item["text"] for item in result["fabricated_entities"]] == [
        "Hans Müller",
        "18.12.1924",
    ]
    assert result["entity_precision_adj"] < 1.0

    form["reviews"][0]["entity_labels"].pop()
    with pytest.raises(AdjudicationError, match="unlabeled"):
        _score(form, hyp, score)


def test_every_automatic_candidate_requires_independent_and_consensus_labels():
    hyp = "eins zwei drei fremder inhalt ohne bild jetzt"
    score = score_page("eins zwei drei", hyp)
    assert score["review_candidate_spans_auto"]
    form = _form(score)
    form["reviews"][1]["candidate_labels"].pop()
    with pytest.raises(AdjudicationError, match="unlabeled"):
        _score(form, hyp, score)

    form = _form(score)
    form["spans"].pop()
    with pytest.raises(AdjudicationError, match="automatic candidates unlabeled"):
        _score(form, hyp, score)


def test_adjudication_rejects_stale_hash_and_overlapping_spans():
    hyp = "eins zwei drei vier"
    score = score_page(hyp, hyp)
    stale = _form(score)
    stale["hypothesis_sha256"] = "0" * 64
    with pytest.raises(AdjudicationError, match="hypothesis_sha256"):
        _score(stale, hyp, score)

    same_length_hyp = "vier drei zwei eins"
    with pytest.raises(AdjudicationError, match="not bound"):
        _score(_form(score), same_length_hyp, score)

    stale_image = _form(score)
    stale_image["image_sha256"] = "b" * 64
    with pytest.raises(AdjudicationError, match="image_sha256"):
        _score(stale_image, hyp, score)

    unbound_score = score_page(hyp, hyp)
    with pytest.raises(AdjudicationError, match="valid image SHA-256"):
        _score(
            adjudication_template("engine-a", "G01", unbound_score), hyp, unbound_score
        )

    overlap = _form(score)
    overlap["spans"] += [
        {"start": 0, "end": 8, "label": "perception_error"},
        {"start": 5, "end": 12, "label": "fluent_fabrication"},
    ]
    for review in overlap["reviews"]:
        review["added_spans"] = [dict(item) for item in overlap["spans"]]
    with pytest.raises(AdjudicationError, match="must not overlap"):
        _score(overlap, hyp, score)


def test_disagreement_requires_distinct_resolver_and_reports_reliability():
    hyp = "eins zwei drei fremder inhalt ohne bild jetzt"
    score = score_page("eins zwei drei", hyp)
    candidate_id = score["review_candidate_spans_auto"][0]["id"]
    form = _form(score)
    _set_candidate_label(form, candidate_id, "fluent_fabrication")
    form["reviews"][1]["candidate_labels"][0]["label"] = "perception_error"
    form["resolver"] = "reviewer-3"
    result = _score(form, hyp, score)
    agreement = result["candidate_review_agreement"]
    assert agreement["items"] == 1
    assert agreement["agreements"] == 0
    assert agreement["raw_agreement"] == 0.0
    assert agreement["confusion"] == {"fluent_fabrication": {"perception_error": 1}}

    form["resolver"] = " REVIEWER-1 "
    with pytest.raises(AdjudicationError, match="distinct"):
        _score(form, hyp, score)

    form["resolver"] = "TODO-resolver"
    with pytest.raises(AdjudicationError, match="template placeholder"):
        _score(form, hyp, score)


def test_reviewer_ids_are_distinct_after_normalization():
    hyp = "eins zwei"
    score = score_page(hyp, hyp)
    form = _form(score)
    form["reviews"][0]["reviewer"] = "Reviewer  A"
    form["reviews"][1]["reviewer"] = " reviewer a "
    with pytest.raises(AdjudicationError, match="distinct reviewer IDs"):
        _score(form, hyp, score)

    placeholder = _form(score)
    placeholder["reviews"][0]["reviewer"] = "TODO-reviewer-1"
    with pytest.raises(AdjudicationError, match="template placeholder"):
        _score(placeholder, hyp, score)

    legitimate_name = _form(score)
    legitimate_name["reviews"][0]["reviewer"] = "Todorov"
    assert _score(legitimate_name, hyp, score)["adjudication_status"] == "complete"


def test_automatic_entity_display_fields_are_bound_to_the_candidate():
    hyp = "Brief von Hans Müller am 18.12.1924"
    score = score_page("brief", hyp)
    form = _form(score)
    entity = form["entities"][0]
    for field, replacement in (
        ("text", "anderer Text"),
        ("kind", "place" if entity["kind"] != "place" else "person"),
        ("start", entity["start"] + 1),
    ):
        tampered = _form(score)
        tampered["entities"][0][field] = replacement
        with pytest.raises(AdjudicationError, match="automatic candidate"):
            _score(tampered, hyp, score)


def test_non_entity_candidates_are_excluded_from_entity_precision():
    hyp = "Hans Müller. Dieser Brief"
    score = score_page("brief", hyp)
    form = _form(score)
    candidates = {item["text"]: item["id"] for item in score["entity_risk_candidates"]}
    _set_entity_label(form, candidates["Hans Müller"], "fabricated")
    _set_entity_label(form, candidates["Dieser Brief"], "not_entity")
    result = _score(form, hyp, score)
    assert result["fabricated_entity_count"] == 1
    assert result["entity_decided_adj"] == 1
    assert result["entity_not_entity_adj"] == 1
    assert result["entity_precision_adj"] == 0.0


def test_comma_separated_entities_can_receive_different_decisions():
    hyp = "Hans Müller, Karl Schmidt"
    score = score_page("brief", hyp)
    form = _form(score)
    candidates = {item["text"]: item["id"] for item in score["entity_risk_candidates"]}
    _set_entity_label(form, candidates["Hans Müller"], "supported")
    _set_entity_label(form, candidates["Karl Schmidt"], "fabricated")
    result = _score(form, hyp, score)
    assert result["entity_supported_adj"] == 1
    assert result["fabricated_entity_count"] == 1
    assert result["entity_precision_adj"] == 0.5


def test_resolver_can_reject_a_one_reviewer_manual_entity_proposal():
    hyp = "dieser begriff steht hier"
    score = score_page(hyp, hyp)
    form = _form(score)
    rejected = {
        "start": 0,
        "end": 6,
        "kind": "person",
        "label": "not_entity",
    }
    form["reviews"][0]["manual_entities"] = [rejected]
    form["manual_entities"] = [rejected]
    form["resolver"] = "reviewer-3"
    result = _score(form, hyp, score)
    assert result["entity_not_entity_adj"] == 1
    assert result["entity_decided_adj"] == 0
    assert result["entity_precision_adj"] is None


def test_resolver_can_canonicalize_disputed_manual_boundaries():
    hyp = "Hans Müller schrieb heute"
    score = score_page(hyp, hyp)
    form = _form(score)
    form["reviews"][0]["added_spans"] = [
        {"start": 0, "end": 11, "label": "fluent_fabrication"}
    ]
    form["reviews"][1]["added_spans"] = [
        {"start": 1, "end": 11, "label": "fluent_fabrication"}
    ]
    form["spans"] = [{"start": 0, "end": 11, "label": "fluent_fabrication"}]
    form["resolver"] = "reviewer-3"
    result = _score(form, hyp, score)
    agreement = result["manual_span_review_agreement"]
    assert agreement["items"] == 1
    assert agreement["agreements"] == 0
    assert agreement["raw_agreement"] == 0.0
    assert agreement["label_raw_agreement"] == 1.0
    assert agreement["cohen_kappa"] is None
    assert result["fab_chars_adj"] == 11

    form["spans"][0]["label"] = "perception_error"
    with pytest.raises(AdjudicationError, match="contradicts agreeing reviewers"):
        _score(form, hyp, score)


def test_resolver_can_canonicalize_disputed_manual_entity_boundaries():
    hyp = "abcdefghij schrieb heute"
    score = score_page(hyp, hyp)
    form = _form(score)
    first = {"start": 0, "end": 10, "kind": "person", "label": "fabricated"}
    second = {"start": 1, "end": 10, "kind": "person", "label": "fabricated"}
    form["reviews"][0]["manual_entities"] = [dict(first)]
    form["reviews"][1]["manual_entities"] = [dict(second)]
    form["manual_entities"] = [dict(first)]
    form["resolver"] = "reviewer-3"
    result = _score(form, hyp, score)
    assert result["manual_entity_review_agreement"]["items"] == 1
    assert result["manual_entity_review_agreement"]["agreements"] == 0
    assert result["fabricated_entity_count"] == 1


def test_resolver_can_canonicalize_disputed_manual_entity_kind():
    hyp = "abcdefghij schrieb heute"
    score = score_page(hyp, hyp)
    form = _form(score)
    first = {"start": 0, "end": 10, "kind": "person", "label": "fabricated"}
    second = {"start": 0, "end": 10, "kind": "place", "label": "fabricated"}
    form["reviews"][0]["manual_entities"] = [dict(first)]
    form["reviews"][1]["manual_entities"] = [dict(second)]
    form["manual_entities"] = [dict(first)]
    form["resolver"] = "reviewer-3"
    result = _score(form, hyp, score)
    assert result["manual_entity_review_agreement"]["items"] == 1
    assert result["manual_entity_review_agreement"]["agreements"] == 0
    assert result["adjudicated_entities"][0]["kind"] == "person"

    form["manual_entities"][0]["label"] = "supported"
    with pytest.raises(AdjudicationError, match="contradicts agreeing reviewers"):
        _score(form, hyp, score)


def test_manual_kappa_uses_label_agreement_not_boundary_agreement():
    first = [
        {"start": 0, "end": 2, "label": "supported"},
        {"start": 4, "end": 6, "label": "fluent_fabrication"},
    ]
    second = [
        {"start": 0, "end": 3, "label": "supported"},
        {"start": 4, "end": 6, "label": "supported"},
    ]
    agreement = manual_agreement(first, second, entity=False)
    assert agreement["raw_agreement"] == 0.0
    assert agreement["label_raw_agreement"] == 0.5
    assert agreement["cohen_kappa"] == 0.0


def test_manual_entities_cannot_duplicate_other_candidates():
    hyp = "Brief von Hans Müller"
    score = score_page(hyp, hyp)
    automatic = next(
        item
        for item in score["entity_risk_candidates"]
        if item["text"] == "Hans Müller"
    )
    duplicate = {
        "start": automatic["start"],
        "end": automatic["end"],
        "kind": "person",
        "label": "supported",
    }
    form = _form(score)
    for review in form["reviews"]:
        review["manual_entities"] = [duplicate]
    form["manual_entities"] = [duplicate]
    with pytest.raises(AdjudicationError, match="duplicate automatic"):
        _score(form, hyp, score)

    score = score_page("abcdefghij", "abcdefghij")
    form = _form(
        score,
        manual_entities=[
            {"start": 0, "end": 5, "kind": "person", "label": "supported"},
            {"start": 3, "end": 8, "kind": "place", "label": "supported"},
        ],
    )
    with pytest.raises(AdjudicationError, match="must not overlap"):
        _score(form, "abcdefghij", score)


def test_empty_hypothesis_can_be_cleanly_adjudicated_but_remains_omission():
    score = score_page("eins zwei", "")
    result = _score(_form(score), "", score)
    assert result["fab_rate_adj"] == 0.0
    assert result["trust_failure_rate_adj"] == 0.0
    assert score["omission_rate"] == 1.0
