from harness import normalization as n


def test_diplomatic_keeps_convention():
    text = "Die Verſamm-\nlung war groß"
    dipl = n.diplomatic(text)
    assert "ſ" in dipl
    assert "-\n" in dipl  # hyphenation preserved in the diplomatic layer


def test_normalize_long_s_and_ligatures():
    assert n.normalize("Waſſer") == "Wasser"
    assert n.normalize("Auﬂage") == "Auflage"
    assert n.normalize("Herꝛ") == "Herr"


def test_normalize_dehyphenates_line_ends():
    assert n.normalize("Verſamm-\nlung") == "Versammlung"
    assert n.normalize("Ver=\nein war da") == "Verein war da"
    assert n.normalize("Bindestrich-Wort bleibt") == "Bindestrich-Wort bleibt"


def test_normalize_joins_lines_and_collapses_whitespace():
    assert n.normalize("eine  Zeile\nnoch    eine") == "eine Zeile noch eine"


def test_lowercase_variant():
    assert n.normalize("Großes Haus", lowercase=True) == "großes haus"
    assert n.normalize("Großes Haus") == "Großes Haus"


def test_marker_keyed_marginalia_inlined():
    assert n.strip_markers("Text ⟪M: 50 K⟫ weiter") == "Text 50 K weiter"


def test_marker_prefixes_stripped():
    assert n.strip_markers("⟪M⟫ Randnotiz") == "Randnotiz"
    assert n.strip_markers("⟪S⟫ POLIZEY BUREAU TORGAU") == "POLIZEY BUREAU TORGAU"


def test_unscored_regions_dropped():
    assert n.strip_markers("oben\n⟪G⟫\nunten") == "oben\nunten"
    assert n.strip_markers("bleibt ⟪P: unscored⟫") == "bleibt"
    assert n.strip_markers("bleibt\n⟪P: PRINT\nBLOCK⟫\nauch") == "bleibt\nauch"


def test_closing_mark_placeholder_dropped():
    # §3.1/§3.2 rule 5/§10 2026-09-03: closing/section flourishes → ⟪Z⟫,
    # unscored like ⟪G⟫ in gold; a bare hypothesis-side ⟪Z⟫ is dropped inline.
    assert n.strip_markers("laß kalt werden ⟪Z⟫\nEin Öpfelmuß") == "laß kalt werden\nEin Öpfelmuß"
    assert n.strip_markers("Zaichen 'c' ⟪Z⟫") == "Zaichen 'c'"
    assert n.strip_markers("oben\n⟪Z⟫\nunten") == "oben\nunten"
    assert n.strip_hyp_markers("laß kalt werden ⟪Z⟫") == "laß kalt werden"


def test_uncertain_reading_scored_normally():
    assert n.strip_markers("das ⟦Haus⟧ dort") == "das Haus dort"


def test_deletion_marker_content_scored():
    # §3.1/§10 2026-07-14: readable strikethrough → ⟪D: …⟫, content scored,
    # glyphs stripped — same treatment as keyed ⟪M: …⟫.
    assert n.strip_markers("Krämer ⟪D: drey⟫ zwey Pfund") == "Krämer drey zwey Pfund"
    assert n.strip_markers("⟪D⟫ ganze Zeile gestrichen") == "ganze Zeile gestrichen"
    # symmetric on the hypothesis side: an engine emitting the marker is unwrapped
    assert n.strip_hyp_markers("Krämer ⟪D: drey⟫ zwey") == "Krämer drey zwey"
    # authoring rule: D markers never span line breaks
    assert "⟪" in n.strip_markers("vorher ⟪D: erste\nzweite⟫ nachher")


def test_nfc_applied():
    decomposed = "über"  # ü as combining diaeresis
    assert n.normalize(decomposed) == "über"


def test_norm_lines_keeps_line_structure():
    lines = n.norm_lines("Erſte Zeile\n⟪G⟫\nZweite-\nZeile")
    assert lines == ["Erste Zeile", "Zweite-", "Zeile"]  # no dehyphenation per-line


def test_digit_normalize():
    assert n.digit_normalize("18.12.1924") == "18121924"
    assert n.digit_normalize("am 7ten") == "7"


def test_markers_are_single_line_by_authoring_rule():
    # A marker spanning a line break is NOT a marker (GT authoring rule);
    # its glyphs stay literal and would surface as a CER hit during GT review.
    text = "vorher ⟪M: erste\nzweite⟫ nachher"
    assert "⟪" in n.strip_markers(text)
    assert n.strip_markers("a ⟪M: eins⟫ b\nc ⟪M: zwei⟫ d") == "a eins b\nc zwei d"


def test_abstention_regex_variants():
    for phrase in ("[unleserlich]", "unlesbar", "This is illegible.", "nicht lesbar"):
        assert n.ABSTENTION_RE.search(phrase)
    assert not n.ABSTENTION_RE.search("ganz normaler Text")


# Line-end strokes (§4 step 2, revised 2026-10-17). Failure modes, written before the code:
# H1 A hyphen (-, =, ⸗ directly after a letter, also a letter with a combining mark or one
#    whose ⟦ ⟧ was stripped) stops joining the two halves of the word.
# H2 A stroke after punctuation (a filler, §3.1: "1812.-") glues the next line's first word
#    to the line's last word.
# H3 A free-standing stroke after a space is kept, or the words are glued.
# H4 A stroke that does not join is kept in the normalized layer (line-end strokes never
#    count there).
# H5 The diplomatic layer or the per-line layer changes.


def test_line_end_hyphen_after_a_letter_joins():
    assert n.normalize("Mül-\nler kam") == "Müller kam"
    assert n.normalize("Jo=\nhann") == "Johann"
    assert n.normalize("Jo⸗\nhann") == "Johann"
    assert n.normalize("⟦Mül⟧-\nler") == "Müller"
    assert n.normalize("Bruͦ=\nder") == "Bruͦder"  # H1: combining mark


def test_line_end_stroke_after_punctuation_drops_without_joining():
    assert n.normalize("am 3. Mai 1812.-\nJohann Weber") == "am 3. Mai 1812. Johann Weber"  # H2, H4
    assert n.normalize("Anna ⟦Weber⟧.-\nJohann") == "Anna Weber. Johann"
    assert n.normalize("bis 1812,=\nJohann") == "bis 1812, Johann"
    assert n.normalize('Herr "-\nJohann') == 'Herr " Johann'


def test_free_standing_line_end_stroke_drops():
    assert n.normalize("Ende -\nJohann") == "Ende Johann"  # H3
    assert n.normalize("Ende =\nJohann") == "Ende Johann"


def test_other_layers_keep_line_end_strokes():
    assert "1812.-\nJohann" in n.diplomatic("am 3. Mai 1812.-\nJohann")  # H5
    assert n.norm_lines("1812.-\nJohann") == ["1812.-", "Johann"]
