from harness.scoring import score_page


def test_hypothesis_error_and_omission_have_separate_denominators():
    scores = score_page("abc", "axcd")
    assert scores["hyp_char_error"] == 0.5
    assert scores["omission_rate"] == 0.0

    empty_hyp = score_page("abc", "")
    assert empty_hyp["hyp_char_error"] == 0.0
    assert empty_hyp["omission_rate"] == 1.0

    empty_gold = score_page("", "abcd")
    assert empty_gold["hyp_char_error"] == 1.0
    assert empty_gold["omission_rate"] == 0.0
    assert empty_gold["excess_length_rate"] == 1.0


def test_v01_long_insertion_semantics_are_retained_under_explicit_name():
    scores = score_page(
        "eins zwei drei", "eins zwei drei fünf neue Wörter stehen nun hier"
    )
    assert scores["long_ins_rate_v01"] > 0.0
    assert scores["long_ins_rate_v01"] == scores["fab_rate"]
    assert scores["long_ins_chars_v01"] == scores["fab_chars"]
    assert scores["long_ins_spans_v01"] == scores["fab_spans"]


def test_equal_length_replacement_becomes_review_candidate():
    gold = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    hyp = "alpha beta fremder inhalt steht sicher ohne bild kappa"
    scores = score_page(gold, hyp)
    assert scores["long_ins_rate_v01"] == 0.0
    assert [span["text"] for span in scores["review_candidate_spans_auto"]] == [
        "fremder inhalt steht sicher ohne bild"
    ]


def test_shorter_replacement_becomes_review_candidate():
    gold = "alpha beta eins zwei drei vier fünf sechs sieben acht neun zehn omega"
    hyp = "alpha beta fremder inhalt ganz ohne bild omega"
    scores = score_page(gold, hyp)
    assert scores["excess_length_rate"] == 0.0
    assert len(scores["review_candidate_spans_auto"]) == 1


def test_two_bridge_words_do_not_split_review_candidate():
    gold = "alpha beta eins zwei drei vier fünf sechs sieben acht omega"
    hyp = "alpha beta fremder und inhalt die bleibt ohne bild omega"
    spans = score_page(gold, hyp)["review_candidate_spans_auto"]
    assert len(spans) == 1
    assert spans[0]["total_words"] <= 7
    assert spans[0]["candidate_words"] >= 5


def test_one_character_typo_is_not_review_candidate():
    gold = "eins zwei drei vier fünf sechs sieben acht"
    hyp = "eins zwei drei vier funf sechs sieben acht"
    scores = score_page(gold, hyp)
    assert scores["review_candidate_spans_auto"] == []
    assert scores["review_candidate_rate_auto"] == 0.0


def test_compound_split_uses_global_character_support_override():
    gold = "Weihnachtsmannkostümverleih und Schluss"
    hyp = "Weih nachts mann kostüm ver leih und Schluss"
    scores = score_page(gold, hyp)
    assert scores["review_candidate_spans_auto"] == []
    assert scores["long_ins_rate_v01"] == 0.0


def test_repeated_fourgram_counts_only_later_occurrence_positions():
    scores = score_page("a b c d", "a b c d a b c d")
    assert scores["repeat_4gram_rate"] == 0.5


def test_candidate_offsets_slice_normalized_hypothesis():
    hyp = "eins zwei drei fremder Inhalt ganz ohne Bild heute"
    scores = score_page("eins zwei drei", hyp)
    span = scores["review_candidate_spans_auto"][0]
    assert hyp[span["start"] : span["end"]] == span["text"]
    assert scores["review_candidate_version"] == "fabrication-review-v02-draft"
    assert "aligned_gold_word" not in span["words"][0]
    assert span["words"][0]["char_counts"]["ins"] == len(span["words"][0]["text"])
