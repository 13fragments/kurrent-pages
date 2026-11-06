"""Build the private resolver page for two independent pilot reviews.

The page shows one review unit at a time: the scan, the two reviews side by
side with their disagreements marked, and controls for the consensus label
and boundary.  It writes a ``fabrication-pilot-resolution-v01`` document that
``python -m harness.pilot import --resolutions`` turns into adjudication forms
validated by :mod:`harness.adjudication`.

The page embeds the reference text and the hypotheses and sits next to copies
of the scans.  It belongs in private coordinator storage or behind the hosted
site's Access gate, never on a public host.  Engine identity, page IDs, and
reviewer identities stay out of it: the two reviews appear as A and B in the
order the annotation files were given.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Sequence

from harness.adjudication_reliability import manual_alignment
from harness.pilot_forms import review_disagreement
from harness.pilot_html import _embed_json, ui_config
from harness.pilot_packets import load_review_documents
from harness.pilot_types import (
    PACKET_COUNT,
    RESOLUTION_SCHEMA_VERSION,
    PilotError,
    digest_value,
    sha256_file,
)

RESOLVER_SCHEMA_VERSION = "fabrication-pilot-resolver-v01"
_ASSET_DIR = Path(__file__).resolve().parent


def build_resolver_bundle(pilot_dir: Path, annotations: Sequence[Path]) -> dict:
    """Collect what the resolver needs to decide every disagreement blind."""
    pilot_dir = Path(pilot_dir)
    if len(annotations) != PACKET_COUNT:
        raise PilotError("the resolver page needs both independent reviews")
    map_payload, packet_index, documents = load_review_documents(
        pilot_dir, annotations
    )
    raw_documents = [
        json.loads(Path(path).read_text(encoding="utf-8")) for path in annotations
    ]
    first_packet = documents[0]["packet_id"]
    public_units = {
        unit["unit_id"]: unit for unit in packet_index[first_packet]["units"]
    }
    units = []
    for unit_id in sorted(map_payload["units"]):
        reviews = [document["units"].get(unit_id) for document in documents]
        if any(review is None for review in reviews):
            raise PilotError("both reviewers must complete every unit first")
        public = public_units[unit_id]
        first, second = reviews
        units.append(
            {
                "unit_id": unit_id,
                "binding_sha256": public["binding_sha256"],
                "image_file": public["image_file"],
                "image_source": str(
                    pilot_dir / "packets" / first_packet / public["image_file"]
                ),
                "hypothesis_normalized": public["hypothesis_normalized"],
                "line_breaks": public.get("line_breaks", []),
                "reference": public["silver_reference"],
                "candidate_spans": public["candidate_spans"],
                "entity_candidates": public["entity_candidates"],
                "disagreement": review_disagreement(first, second),
                "reviews": [
                    _review_view(review, raw, unit_id)
                    for review, raw in zip(reviews, raw_documents)
                ],
                "manual_span_pairs": _pairs(
                    first["added_spans"], second["added_spans"], entity=False
                ),
                "manual_entity_pairs": _pairs(
                    first["manual_entities"], second["manual_entities"], entity=True
                ),
            }
        )
    payload = {
        "schema_version": RESOLVER_SCHEMA_VERSION,
        "resolution_schema_version": RESOLUTION_SCHEMA_VERSION,
        "map_sha256": map_payload["map_sha256"],
        "reference_source": map_payload.get("reference_source", "silver"),
        "units": [
            {key: value for key, value in unit.items() if key != "image_source"}
            for unit in units
        ],
    }
    payload["bundle_sha256"] = digest_value(payload)
    payload["bundle_id"] = "r_" + payload["bundle_sha256"][:24]
    return {"page": payload, "images": {u["image_file"]: u["image_source"] for u in units}}


def write_resolver_page(
    pilot_dir: Path,
    annotations: Sequence[Path],
    out_dir: Path | None = None,
    *,
    hosted: bool = False,
    gitignore: bool = True,
) -> dict:
    """Write ``resolve.html`` and its scans to a private directory."""
    pilot_dir = Path(pilot_dir)
    bundle = build_resolver_bundle(pilot_dir, annotations)
    page = bundle["page"]
    target = (
        Path(out_dir)
        if out_dir is not None
        else pilot_dir / "coordinator" / "resolver" / page["bundle_id"]
    )
    if target.exists() and any(target.iterdir()):
        raise PilotError(f"output directory is not empty: {target}")
    (target / "images").mkdir(parents=True, exist_ok=True)
    if gitignore:
        (target / ".gitignore").write_text("*\n", encoding="utf-8")
    for image_file, source in bundle["images"].items():
        relative = Path(image_file)
        if relative.is_absolute() or ".." in relative.parts:
            raise PilotError("packet image path is invalid")
        shutil.copyfile(source, target / relative)
        if sha256_file(target / relative) != sha256_file(Path(source)):
            raise PilotError("copied scan changed")
    (target / "resolve.html").write_text(
        render_resolver_html(page, hosted=hosted), encoding="utf-8"
    )
    return {
        "bundle_id": page["bundle_id"],
        "unit_count": len(page["units"]),
        "disagreeing_units": sum(unit["disagreement"] for unit in page["units"]),
        "page": str(target / "resolve.html"),
    }


def render_resolver_html(page: dict, *, hosted: bool = False) -> str:
    template = (_ASSET_DIR / "pilot_resolver.html").read_text(encoding="utf-8")
    replacements = {
        "__STYLE__": (_ASSET_DIR / "pilot_resolver.css").read_text(encoding="utf-8"),
        "__BUNDLE_JSON__": _embed_json(page),
        "__UI_JSON__": _embed_json(ui_config()),
        "__SITE_JSON__": _embed_json({"hosted": bool(hosted)}),
        "__CORE_SCRIPT__": (_ASSET_DIR / "pilot_resolver_core.js").read_text(
            encoding="utf-8"
        ),
        "__SCRIPT__": (_ASSET_DIR / "pilot_resolver.js").read_text(encoding="utf-8"),
    }
    for token, value in replacements.items():
        assert template.count(token) == 1, token
        template = template.replace(token, value)
    return template


def _review_view(review: dict, raw: dict, unit_id: str) -> dict:
    """Labels plus the free-text notes the importer ignores."""
    raw_units = raw.get("units")
    if isinstance(raw_units, list):
        raw_units = {item.get("unit_id"): item for item in raw_units if isinstance(item, dict)}
    raw_unit = raw_units.get(unit_id, {}) if isinstance(raw_units, dict) else {}
    notes = [
        {
            "candidate_id": str(note.get("candidate_id")),
            "mixed": note.get("mixed") is True,
            "text": str(note.get("text") or ""),
        }
        for note in raw_unit.get("notes", [])
        if isinstance(note, dict)
    ]
    unit_note = raw_unit.get("unit_note")
    return {
        "candidate_labels": review["candidate_labels"],
        "entity_labels": review["entity_labels"],
        "added_spans": review["added_spans"],
        "manual_entities": review["manual_entities"],
        "notes": notes,
        "unit_note": unit_note if isinstance(unit_note, str) else "",
    }


def _pairs(first: list[dict], second: list[dict], *, entity: bool) -> list[list]:
    """Index pairs in the scorer's own one-to-one alignment of proposals."""
    index_first = {id(item): index for index, item in enumerate(first)}
    index_second = {id(item): index for index, item in enumerate(second)}
    return [
        [
            index_first[id(left)] if left is not None else None,
            index_second[id(right)] if right is not None else None,
        ]
        for left, right in manual_alignment(first, second, entity=entity)
    ]
