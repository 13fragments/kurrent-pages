import pytest

from harness.entities import extract_entity_risk_candidates, score_entities
from harness.gold import Entity


def _person(name, variants=()):
    return Entity(
        type="person", surface=name, normalized=name, variants=tuple(variants)
    )


def test_exact_and_fuzzy_token_match():
    result = score_entities(
        [_person("Marie Dittrich")], "Protokoll von Marie Dittrich 1936"
    )
    assert result["entity_recall"] == 1.0
    # one edit per token allowed
    result = score_entities(
        [_person("Marie Dittrich")], "Protokoll von Maria Ditrich 1936"
    )
    assert result["entity_recall"] == 1.0
    # two edits in one token: no match
    result = score_entities(
        [_person("Marie Dittrich")], "Protokoll von Maria Duttrach 1936"
    )
    assert result["entity_recall"] == 0.0


def test_variant_forms_count():
    entity = _person("Elisabeth Reiss", variants=["E. Reiss"])
    assert (
        score_entities([entity], "Tagebuch der E. Reiss aus Karlsruhe")["entity_recall"]
        == 1.0
    )


def test_date_requires_exact_digits():
    date = Entity(type="date", surface="29.7.40", normalized="29.7.40")
    assert (
        score_entities([date], "Bromberg den 29. 7. 40 geschrieben")["entity_recall"]
        == 1.0
    )
    assert (
        score_entities([date], "Bromberg den 29. 7. 41 geschrieben")["entity_recall"]
        == 0.0
    )
    # digits embedded in a longer digit run must not match
    assert score_entities([date], "Nummer 129740 im Register")["entity_recall"] == 0.0


def test_date_survives_spaced_punctuation():
    date = Entity(type="date", surface="18.12.1924", normalized="18.12.1924")
    assert (
        score_entities([date], "Eger den 18 . 12 . 1924 geschrieben")["entity_recall"]
        == 1.0
    )
    assert score_entities([date], "Eger den 18 , 12 , 1924")["entity_recall"] == 1.0


def test_date_month_words_require_month_match():
    date = Entity(type="date", surface="18. Sept 1916", normalized="18. Sept 1916")
    assert (
        score_entities([date], "Karlsruhe den 18. September 1916")["entity_recall"]
        == 1.0
    )
    assert score_entities([date], "Karlsruhe den 18 Okt 1916")["entity_recall"] == 0.0
    assert score_entities([date], "Karlsruhe den 18 1916")["entity_recall"] == 0.0


def test_date_month_aliases_match():
    march = Entity(type="date", surface="03.03.1910", normalized="03.03.1910")
    assert score_entities([march], "Berlin 3. Mrz. 1910")["entity_recall"] == 1.0
    assert score_entities([march], "Berlin 3. Marz 1910")["entity_recall"] == 1.0

    january = Entity(type="date", surface="01.01.1910", normalized="01.01.1910")
    assert score_entities([january], "Wien 1. Jänner 1910")["entity_recall"] == 1.0
    assert score_entities([january], "Wien 1. Jaenner 1910")["entity_recall"] == 1.0

    july = Entity(type="date", surface="02.07.1910", normalized="02.07.1910")
    assert score_entities([july], "Bonn 2. Julii 1910")["entity_recall"] == 1.0


def test_date_roman_months_require_month_match():
    date = Entity(type="date", surface="23.III.1942", normalized="23.III.1942")
    assert score_entities([date], "Russland 23. III. 1942")["entity_recall"] == 1.0
    assert score_entities([date], "Russland 23. IV. 1942")["entity_recall"] == 0.0
    assert score_entities([date], "Russland 23 1942")["entity_recall"] == 0.0


def test_partial_dates_use_exact_digit_fallback():
    year = Entity(type="date", surface="1940", normalized="1940")
    assert score_entities([year], "im Jahre 1940")["entity_recall"] == 1.0
    assert score_entities([year], "im Jahre 1941")["entity_recall"] == 0.0

    date_range = Entity(type="date", surface="1911/12", normalized="1911/12")
    assert score_entities([date_range], "Schuljahr 1911/12")["entity_recall"] == 1.0
    assert score_entities([date_range], "Schuljahr 1911/13")["entity_recall"] == 0.0


def test_by_type_breakdown_does_not_expose_missed_target_text():
    entities = [
        _person("Otto Schröder"),
        Entity(type="place", surface="Metz", normalized="Metz"),
    ]
    result = score_entities(entities, "Brief des Otto Schröder aus dem Lazarett")
    assert result["entity_by_type"]["person"]["recall"] == 1.0
    assert result["entity_by_type"]["place"]["recall"] == 0.0
    assert "entity_missed" not in result


def test_no_entities_gives_none_recall():
    assert score_entities([], "irgendein Text")["entity_recall"] is None


def test_surface_form_counts_even_when_normalized_differs():
    date = Entity(type="date", surface="18.12.1924", normalized="1924-12-18")
    assert (
        score_entities([date], "Eger den 18.12.1924 geschrieben")["entity_recall"]
        == 1.0
    )
    person = Entity(
        type="person", surface="Frid. Wagener", normalized="Friedrich Wagener"
    )
    assert (
        score_entities([person], "Brief des Frid. Wagener hier")["entity_recall"] == 1.0
    )


def test_entity_risk_candidates_cover_names_dates_amounts_and_identifiers():
    text = "Erich Wagener schrieb am 18.12.1924 über 25 RM unter Nr. A-419."
    result = extract_entity_risk_candidates(text)
    by_kind = {kind: [] for kind in ("name_or_place", "date", "amount", "identifier")}
    for candidate in result["entity_risk_candidates"]:
        by_kind[candidate["kind"]].append(candidate["text"])
        assert text[candidate["start"] : candidate["end"]] == candidate["text"]
    assert by_kind == {
        "name_or_place": ["Erich Wagener"],
        "date": ["18.12.1924"],
        "amount": ["25 RM"],
        "identifier": ["Nr. A-419"],
    }


def test_amount_candidates_cover_historical_currency_forms():
    text = "25,- RM; 1.200 RM; RM 25; 25 fl.; 20/10/25 K; 25 fs"
    candidates = extract_entity_risk_candidates(text)["entity_risk_candidates"]
    assert [item["text"] for item in candidates if item["kind"] == "amount"] == [
        "25,- RM",
        "1.200 RM",
        "RM 25",
        "25 fl.",
        "20/10/25 K",
        "25 fs",
    ]
    assert not [item for item in candidates if item["kind"] == "date"]


def test_one_token_name_reaches_entity_risk_review():
    candidates = extract_entity_risk_candidates("geschrieben von Solingen")
    assert [
        (item["kind"], item["text"]) for item in candidates["entity_risk_candidates"]
    ] == [("name_or_place", "Solingen")]

    lowercase = extract_entity_risk_candidates("Nach solingen")[
        "entity_risk_candidates"
    ]
    assert ("name_or_place", "solingen") in [
        (item["kind"], item["text"]) for item in lowercase
    ]


def test_date_candidate_grammar_covers_benchmark_forms():
    text = "1940; 1911/12; 23.III.1942; 1. Jänner 1895; 2. Julii 1910; 22. Januar"
    candidates = extract_entity_risk_candidates(text)["entity_risk_candidates"]
    assert [item["text"] for item in candidates if item["kind"] == "date"] == [
        "1940",
        "1911/12",
        "23.III.1942",
        "1. Jänner 1895",
        "2. Julii 1910",
        "22. Januar",
    ]


def test_name_candidates_support_case_unicode_initials_and_context():
    text = "E. Wagener aus BERLIN sprach mit Émile. Danach reiste er nach solingen."
    candidates = extract_entity_risk_candidates(text)["entity_risk_candidates"]
    names = [item["text"] for item in candidates if item["kind"] == "name_or_place"]
    assert "E. Wagener" in names
    assert "BERLIN" in names
    assert "Émile" in names
    assert "solingen" in names


def test_name_candidates_stop_at_sentence_boundaries():
    candidates = extract_entity_risk_candidates("Hans Müller. Dieser Brief")
    names = [item["text"] for item in candidates["entity_risk_candidates"]]
    assert names == ["Hans Müller", "Dieser Brief"]


def test_name_candidates_split_comma_and_semicolon_lists():
    text = "Hans Müller, Karl Schmidt; Berlin, Hamburg, München"
    candidates = extract_entity_risk_candidates(text)["entity_risk_candidates"]
    names = [item["text"] for item in candidates if item["kind"] == "name_or_place"]
    assert names == ["Hans Müller", "Karl Schmidt", "Berlin", "Hamburg", "München"]


def test_name_candidates_keep_titles_and_abbreviations_together_without_nested_names():
    text = "Dr. Hans Müller traf Fr. Xav. Jetz in St. Peter."
    candidates = extract_entity_risk_candidates(text)["entity_risk_candidates"]
    names = [item["text"] for item in candidates if item["kind"] == "name_or_place"]
    assert names == ["Dr. Hans Müller", "Fr. Xav. Jetz", "St. Peter"]


def test_same_kind_contained_candidates_are_suppressed():
    candidates = extract_entity_risk_candidates("Hans Müller aus BERLIN")[
        "entity_risk_candidates"
    ]
    names = [item["text"] for item in candidates if item["kind"] == "name_or_place"]
    assert names == ["Hans Müller", "BERLIN"]


# Historical month forms (§10 2026-10-17). Failure modes, written before the code:
# D1 A historical German or Latin form is not read as its month: the date falls back to
#    digits, and a correct modern transcription ("10. September 1812") misses.
# D2 A numeral form (7ber, 8bre, 9bris, Xber, 10br.: the old Roman count, September to
#    December) is read as its digit, so 13 7ber 1812 matches 13.7.1812 (July).
# D3 An abbreviation with an apostrophe ("Sep'") stops matching.
# D4 A new form matches another month, or turns a word without day and year into a date.
# D5 The Germanic month names of some 20th-century letters (Hornung, Scheiding,
#    Julmond, ...) are not read.


def _date(surface: str) -> Entity:
    return Entity(type="date", surface=surface, normalized=surface)


def _recall(surface: str, hypothesis: str) -> float:
    return score_entities([_date(surface)], hypothesis)["entity_recall"]


@pytest.mark.parametrize(
    ("surface", "modern"),
    [
        ("10 Septem 1812", "10. September 1812"),  # D1
        ("13. Septbr. 1812", "13.09.1812"),
        ("5 Augusti 1812", "5. August 1812"),
        ("3 Octobris 1812", "3. Oktober 1812"),
        ("1 Decembr. 1812", "1. Dezember 1812"),
        ("2 Febr. 1813", "2. Februar 1813"),
        ("9 Martii 1813", "9.3.1813"),
        ("13ten Julij 1812", "13. Juli 1812"),  # "-ij" spelling of the Latin "-ii"
        ("2 Maij 1813", "2.5.1813"),
        ("13ten Septr. 1812", "13. September 1812"),  # "-r" abbreviations
        ("1 Octr. 1812", "1.10.1812"),
        ("13 7ber 1812", "13. September 1812"),  # D2
        ("13 7bris 1812", "13.9.1812"),
        ("4 8bre 1812", "4. Oktober 1812"),
        ("6 9br. 1812", "6. November 1812"),
        ("24 Xbris 1812", "24. Dezember 1812"),
        ("13 Sep' 1812", "13. September 1812"),  # D3
        ("12. Hornung 1942", "12.2.1942"),  # D5
        ("3. Scheiding 1940", "3. September 1940"),
        ("1. Julmond 1941", "1.12.1941"),
    ],
)
def test_historical_month_forms_match_modern_dates(surface, modern):
    assert _recall(surface, f"geschrieben {modern} abends") == 1.0
    assert _recall(modern, f"geschrieben {surface} abends") == 1.0


def test_numeral_month_forms_are_not_their_digit():
    assert _recall("13 7ber 1812", "am 13.7.1812") == 0.0  # D2
    assert _recall("24 Xbris 1812", "am 24.10.1812") == 0.0


def test_new_month_forms_do_not_widen_matches():
    assert _recall("13. Septbr. 1812", "am 13. Okt. 1812") == 0.0  # D4
    assert _recall("12. Hornung 1942", "am 12. März 1942") == 0.0
    assert _recall("1942", "Herr Hornung kam 1942") == 1.0
    assert _recall("12. Hornung 1942", "Herr Hornung kam 1942") == 0.0
