"""Checks against the real frozen gold/selection.yml in this repo."""

from pathlib import Path

from harness.gold import HARD_STRATA, hard_strata_pages, load_selection

REPO = Path(__file__).parents[1]


def _pages():
    return load_selection(REPO / "gold" / "selection.yml")


def test_frozen_counts():
    pages = _pages()
    assert sum(p.scored for p in pages) == 53
    assert sum(not p.scored for p in pages) == 2


def test_page_fields():
    pages = {p.id: p for p in _pages()}
    g01 = pages["G01"]
    assert g01.image_name == "G01.jpg"
    assert g01.primary_stratum == "suetterlin"
    assert g01.strata == ("ugly_kurrent", "suetterlin")
    assert g01.scored
    assert pages["A01"].image_name == "A01_annex.jpg"
    assert not pages["A01"].scored


def test_placeholder_files_do_not_count_as_gold(tmp_path):
    from harness.gold import load_entities, load_gt

    (tmp_path / "G01.txt").write_text("   \n\n", encoding="utf-8")
    assert load_gt(tmp_path, "G01") is None  # whitespace placeholder != GT
    (tmp_path / "G01.yml").write_text("", encoding="utf-8")
    assert load_entities(tmp_path, "G01") is None  # empty file != annotation
    (tmp_path / "G02.yml").write_text("notes: later\n", encoding="utf-8")
    assert load_entities(tmp_path, "G02") is None  # no entities key != annotation
    (tmp_path / "G03.yml").write_text("entities: []\n", encoding="utf-8")
    assert load_entities(tmp_path, "G03") == []  # explicit empty annotation counts
    (tmp_path / "G04.yml").write_text("entities:\n", encoding="utf-8")
    assert load_entities(tmp_path, "G04") is None  # bare key (null) is a placeholder


def test_stratum_totals_crosscheck_is_clean():
    from harness.gold import stratum_total_mismatches

    assert stratum_total_mismatches(REPO / "gold" / "selection.yml") == []


def test_hard_strata_subset_is_nonempty_and_correct():
    pages = _pages()
    hard = hard_strata_pages(pages)
    assert hard, "hard-strata set must not be empty"
    assert all(p.primary_stratum in HARD_STRATA for p in hard)
    assert all(p.scored for p in hard)
    assert len(hard) == 33
    assert not any(p.id == "G46" for p in hard)
    # degraded_fraktur is print territory, never in the kill-criterion set (§8)
    assert not any(p.primary_stratum == "degraded_fraktur" for p in hard)
