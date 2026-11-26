"""Output map unlimited-remove-det: the Unlimited-OCR card's remove_det() (revision 8249d20b), §10 2026-11-25.

Ways it could fail, written before the code:
  U1 It keeps the <|det|>category [bbox]<|/det|> markers or the coordinates in the scored text.
  U2 It joins lines of one block with blank lines or separates blocks without one (the card: lines of a block
     joined by a newline, blocks by a blank line).
  U3 It keeps the content of image blocks, which the card drops.
  U4 It drops text that comes before the first marker or a marker line without a box.
"""

from harness.output_maps import OUTPUT_MAPS

remove_det = OUTPUT_MAPS["unlimited-remove-det"]


def test_markers_and_boxes_are_removed_and_blocks_kept():  # U1, U2
    raw = ("<|det|>title [12, 30, 400, 60]<|/det|>Hochgeehrter Herr!\n"
           "<|det|>text [12, 80, 900, 300]<|/det|>Ihren Brief vom 3. d. M.\n"
           "habe ich erhalten.\n")
    assert remove_det(raw) == "Hochgeehrter Herr!\n\nIhren Brief vom 3. d. M.\nhabe ich erhalten."


def test_image_blocks_are_dropped():  # U3
    raw = "<|det|>image [0, 0, 10, 10]<|/det|>Stempel\n<|det|>text [0, 20, 10, 30]<|/det|>Zeile"
    assert remove_det(raw) == "Zeile"


def test_text_before_markers_and_boxless_markers_are_kept():  # U4
    raw = "Vorspann\n<|det|>text<|/det|>Zeile eins\n\nZeile zwei"
    assert remove_det(raw) == "Vorspann\n\nZeile eins\nZeile zwei"
