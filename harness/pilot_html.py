"""Dependency-free German browser form for blinded pilot reviews.

The form is one self-contained HTML file per reviewer packet.  The packet is
embedded as JSON, so the page works from ``file://`` without a web server.  The
export written by the page is the ``fabrication-pilot-review-v01`` document
that :mod:`harness.pilot_packets` imports; only the presentation lives here.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness.adjudication_schema import ENTITY_KINDS, ENTITY_LABELS, SPAN_LABELS

_ASSET_DIR = Path(__file__).resolve().parent

# Reviewer-facing wording.  The ``id`` values are the schema identifiers that
# reach the export; reviewers only ever see ``name`` and ``help``.  ``answer``
# is the first comparison question the form asks: ``ja``,
# ``nein`` (then one of the ``nein`` reasons), or ``unsicher``.
SPAN_LABEL_UI = [
    {"id": "supported", "answer": "ja", "name": "Ja", "help": ""},
    {
        "id": "perception_error",
        "answer": "nein",
        "name": "Lesefehler",
        "help": "Das Programm hat Buchstaben im Scan links falsch gelesen. Die Buchstaben sehen ähnlich aus.",
        "example": "Im Scan links steht „der Schmied Johann Kranz“. Das Programm schreibt „der Schmid Johanna Kranich“. "
        "Sie erkennen, welche Stelle im Scan links gemeint ist. Die Buchstaben sehen ähnlich aus. "
        "Das Programm hat sie falsch gelesen. Antwort: „Nein“, Grund „Lesefehler“. "
        "Das gilt auch, wenn fast jedes Wort falsch ist. Die Zahl der Wörter muss nicht stimmen: "
        "Auch getrennte oder zusammengezogene Wörter sind ein Lesefehler.",
    },
    {
        "id": "convention_error",
        "answer": "nein",
        "name": "Nur die Schreibweise",
        "help": "Das Programm schreibt eine Abkürzung aus. Oder es nutzt die heutige Schreibweise. Oder es setzt Zeichen anders als im Scan links.",
    },
    {
        "id": "order_layout_error",
        "answer": "nein",
        "name": "Steht woanders",
        "help": "Der Text steht im Scan links an einer anderen Stelle. Oder die Reihenfolge ist anders.",
    },
    {
        "id": "fluent_fabrication",
        "answer": "nein",
        "name": "Erfunden",
        "help": "Der Text ist lesbar. Im Scan links steht nichts, das so gelesen werden könnte. "
        "Auch eigene Sätze des Programms wie „Hier ist die Abschrift …“ zählen als „Erfunden“. "
        "Zusätzliche Tabellenstriche oder ein anderes Aussehen des Textes zählen zu „Nur die Schreibweise“.",
        "example": "Im Scan links endet die Seite mit „gegeben zu Freiberg“. Das Programm schreibt danach noch "
        "„im Beisein der ehrbaren Zeugen und des Herrn Pfarrers“. Im Scan links steht dort nichts. "
        "Antwort: „Nein“, Grund „Erfunden“.",
    },
    {
        "id": "degenerate_generation",
        "answer": "nein",
        "name": "Wiederholung",
        "help": "Das Programm wiederholt denselben Text. Im Scan links steht er nicht so oft.",
    },
    {"id": "gt_or_image_uncertain", "answer": "unsicher", "name": "Weiß nicht", "help": ""},
]

# Order is the order of the answers in step 2.  Every candidate word needs
# one of them; there is no default answer (pilot v2).
ENTITY_LABEL_UI = [
    {"id": "supported", "answer": "ja", "name": "Steht so im Scan", "help": ""},
    {"id": "fabricated", "answer": "nein", "name": "Steht nicht im Scan", "help": ""},
    {
        "id": "not_entity",
        "answer": "kein",
        "name": "Kein Name, nur ein Wort",
        "help": "Das Wort ist kein Name, kein Ort, kein Datum, kein Betrag, keine Nummer und kein Kennzeichen.",
    },
    {"id": "uncertain", "answer": "unsicher", "name": "Weiß nicht", "help": ""},
]

ENTITY_KIND_UI = [
    {"id": "name_or_place", "name": "Name oder Ort"},
    {"id": "person", "name": "Name einer Person"},
    {"id": "place", "name": "Ort"},
    {"id": "date", "name": "Datum"},
    {"id": "amount", "name": "Betrag"},
    {"id": "identifier", "name": "Nummer oder Kennzeichen"},
]

assert {item["id"] for item in SPAN_LABEL_UI} == set(SPAN_LABELS)
assert {item["id"] for item in ENTITY_LABEL_UI} == set(ENTITY_LABELS)
assert {item["id"] for item in ENTITY_KIND_UI} == set(ENTITY_KINDS)


def _embed_json(value: object) -> str:
    # A packet can contain arbitrary transcription text.  Escaping ``<`` keeps
    # a transcription from terminating the JSON script element.
    return json.dumps(value, ensure_ascii=False, sort_keys=True).replace(
        "<", "\\u003c"
    )


def ui_config() -> dict:
    return {
        "spanLabels": SPAN_LABEL_UI,
        "entityLabels": ENTITY_LABEL_UI,
        "entityKinds": ENTITY_KIND_UI,
    }


def render_review_html(packet: dict, *, hosted: bool = False) -> str:
    """Render one reviewer packet as a self-contained HTML form.

    Source metadata is absent from ``packet`` by construction; the page shows
    no engine, run, or page identity.  With ``hosted`` the form saves to and
    submits through the site worker (``/api/state``, ``/api/submit``) instead
    of the Downloads folder.
    """
    template = (_ASSET_DIR / "pilot_review.html").read_text(encoding="utf-8")
    css = (_ASSET_DIR / "pilot_review.css").read_text(encoding="utf-8")
    core = (_ASSET_DIR / "pilot_review_core.js").read_text(encoding="utf-8")
    script = (_ASSET_DIR / "pilot_review.js").read_text(encoding="utf-8")
    tokens = ("__STYLE__", "__PACKET_JSON__", "__UI_JSON__", "__SITE_JSON__", "__CORE_SCRIPT__", "__SCRIPT__")
    for token in tokens:
        assert template.count(token) == 1, token
    return (
        template.replace("__STYLE__", css)
        .replace("__PACKET_JSON__", _embed_json(packet))
        .replace("__UI_JSON__", _embed_json(ui_config()))
        .replace("__SITE_JSON__", _embed_json({"hosted": bool(hosted)}))
        .replace("__CORE_SCRIPT__", core)
        .replace("__SCRIPT__", script)
    )
