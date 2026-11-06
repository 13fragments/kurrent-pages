import json

from harness.gold import Entity
from harness.scoring import score_annex, score_page


GOLD = "Erſte Zeile des Briefes\nZweite Zeile mit Worten\nDritte Zeile am Ende"


def test_perfect_match():
    scores = score_page(GOLD, GOLD)
    assert scores["cer_dipl"] == 0.0
    assert scores["cer_norm"] == 0.0
    assert scores["wer_norm"] == 0.0
    assert scores["nls_norm"] == 1.0
    assert scores["fab_rate"] == 0.0
    assert scores["seg_fail"] is False
    assert scores["correction_bucket"] == "<5%"


def test_dipl_vs_norm_layers_diverge():
    hyp = GOLD.replace(
        "ſ", "s"
    )  # modernized long s: wrong diplomatically, fine normalized
    scores = score_page(GOLD, hyp)
    assert scores["cer_norm"] == 0.0
    assert scores["cer_dipl"] > 0.0


def test_empty_output_is_seg_fail():
    scores = score_page(GOLD, "")
    assert scores["seg_fail"] is True
    assert scores["cer_norm"] == 1.0
    assert scores["correction_bucket"] == ">30%"


def test_fabrication_run_of_five_words_flagged():
    hyp = GOLD + "\nund hier stehen fünf erfundene Wörter dazu"
    scores = score_page(GOLD, hyp)
    assert len(scores["fab_spans"]) == 1
    assert scores["fab_rate"] > 0.0


def test_fabrication_short_insertion_not_flagged():
    hyp = GOLD + "\nnur vier neue Wörter"
    scores = score_page(GOLD, hyp)
    assert scores["fab_spans"] == []
    assert scores["fab_rate"] == 0.0


def test_split_long_word_is_not_fabrication():
    # A gold compound split into >=5 pieces must NOT read as an insertion run
    # (this is the char-alignment vs word-alignment distinction of §5.3).
    gold = "Weihnachtsmannkostümverleih und so weiter am Ende"
    hyp = "Weih nachts mann kostüm ver leih und so weiter am Ende"
    scores = score_page(gold, hyp)
    assert scores["fab_spans"] == []
    assert scores["fab_rate"] == 0.0


def test_fabrication_name_candidates():
    hyp = GOLD + "\nErich Wagener aus Solingen war angeblich dort"
    scores = score_page(GOLD, hyp)
    assert "Erich Wagener" in scores["fab_name_candidates"]
    assert "Wagener" not in scores["fab_name_candidates"]


def test_reading_order_cost_isolated():
    lines = GOLD.split("\n")
    swapped = "\n".join([lines[2], lines[1], lines[0]])
    scores = score_page(GOLD, swapped)
    assert scores["cer_norm"] > 0.2  # order error hurts linear CER
    assert scores["ro_cost"] > 0.15  # ...and is attributed to ordering
    assert (
        abs(scores["cer_norm"] - scores["ro_cost"]) < 0.1
    )  # recognition itself was perfect


def test_abstention_marker_respected():
    gold = "Anfang [unleserlich] Ende"
    scores_good = score_page(gold, "Anfang [unleserlich] Ende")
    assert scores_good["abstention_ok"] == 1.0
    scores_bad = score_page(gold, "Anfang erfundener Text hier Ende")
    assert scores_bad["abstention_ok"] == 0.0
    assert score_page(GOLD, GOLD)["abstention_ok"] is None


def test_abstention_marker_plus_invented_content_fails():
    gold = "Anfang [unleserlich] Ende"
    hyp = "Anfang unleserlich Hans Müller aus Berlin gewesen Ende"
    assert score_page(gold, hyp)["abstention_ok"] == 0.0


def test_annex_scoring():
    ok = score_annex("[unleserlich]")
    assert ok["abstention_ok"] is True
    assert ok["hallucinated_chars"] == 0
    assert score_annex("")["abstention_ok"] is True
    bad = score_annex("Es war einmal ein langer erfundener Text")
    assert bad["abstention_ok"] is False
    assert bad["hallucinated_chars"] > 20


def test_annex_explicit_illegible_statement_is_clean():
    # §5.6: an explicit "illegible" statement counts as correct abstention
    assert score_annex("This page is illegible.")["abstention_ok"] is True
    assert score_annex("Die Seite ist unleserlich.")["abstention_ok"] is True
    # ...but a fluent page that merely mentions the word is not clean
    fluent = (
        "unleserlich "
        + "erfundener fließender Text über das Dorf und seine Bewohner " * 5
    )
    assert score_annex(fluent)["abstention_ok"] is False


def test_annex_hypothesis_print_markup_cannot_hide_hallucination():
    scores = score_annex("⟪P: five fabricated words here now⟫")
    assert scores["abstention_ok"] is False
    assert scores["hallucinated_chars"] > 0


def test_ro_cost_not_negative_for_unwrapped_output():
    one_line = GOLD.replace("\n", " ")  # perfect text, no line breaks
    scores = score_page(GOLD, one_line)
    assert scores["cer_norm"] == 0.0
    assert scores["ro_cost"] == 0.0


def test_unscored_print_region_plain_hyp_is_not_penalized():
    gold = "hand\n⟪P: PRINTED BLOCK⟫\ntext"
    hyp = "hand\nPRINTED BLOCK\ntext"
    scores = score_page(gold, hyp)
    assert scores["cer_dipl"] == 0.0
    assert scores["cer_norm"] == 0.0
    assert scores["fab_rate"] == 0.0


def test_multiline_unscored_print_region_plain_hyp_is_not_penalized():
    gold = "hand\n⟪P: PRINTED\nBLOCK⟫\ntext"
    hyp = "hand\nPRINTED\nBLOCK\ntext"
    scores = score_page(gold, hyp)
    assert scores["cer_dipl"] == 0.0
    assert scores["cer_norm"] == 0.0
    assert scores["fab_rate"] == 0.0


def test_trailing_unscored_print_ocr_variant_is_not_penalized():
    scores = score_page("hand\n⟪P: PRINTED BLOCK⟫", "hand\nPRlNTED BLOCK")
    assert scores["cer_dipl"] == 0.0
    assert scores["cer_norm"] == 0.0


def test_trailing_unscored_placeholder_cannot_hide_hallucinated_suffix():
    gold = "hand text\n⟪P: unscored⟫"
    hyp = "hand text\nfive fabricated words here now"
    scores = score_page(gold, hyp)
    assert scores["cer_norm"] > 0.0
    assert scores["fab_rate"] > 0.0


def test_hypothesis_print_markup_cannot_hide_fabrication():
    scores = score_page("hand text", "hand text ⟪P: five fabricated words here now⟫")
    assert scores["cer_norm"] > 0.0
    assert scores["fab_rate"] > 0.0


def test_entities_scored_when_present():
    gold = "Brief von Erich Wagener aus Solingen am 18.12.1924"
    entities = [
        Entity(type="person", surface="Erich Wagener", normalized="Erich Wagener"),
        Entity(type="place", surface="Solingen", normalized="Solingen"),
        Entity(type="date", surface="18.12.1924", normalized="18.12.1924"),
    ]
    hyp = (
        "Brief von Erich Wagner aus Solingen am 18. 12. 1924"  # 1 char off + split date
    )
    scores = score_page(gold, hyp, entities=entities)
    assert scores["entity_recall"] == 1.0
    hyp_bad = "Brief von Heinrich Schmidt aus Berlin am 1.1.1900"
    scores_bad = score_page(gold, hyp_bad, entities=entities)
    assert scores_bad["entity_recall"] == 0.0


def test_page_scores_do_not_serialize_private_gold_targets():
    gold = "GeheimesGoldwort im privaten Zieltext"
    entities = [
        Entity(
            type="place",
            surface="VerborgenerGoldort",
            normalized="VerborgenerGoldort",
        )
    ]
    serialized = json.dumps(
        score_page(gold, "vollkommen andere Ausgabe", entities=entities)
    )
    assert "GeheimesGoldwort" not in serialized
    assert "VerborgenerGoldort" not in serialized
