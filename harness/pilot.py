"""Export and import a small, blinded fabrication-review pilot.

The pilot accepts already-loaded silver units. It never discovers evaluation
data, reads benchmark gold paths, or trusts archived run metadata. Coordinator
data is kept below ``coordinator/``; only opaque packet data is intended for a
reviewer.

Typical use::

    python -m harness.pilot export --units scored-silver.json --out pilot
    python -m harness.pilot import --pilot-dir pilot --annotations a.json --annotations b.json
    python -m harness.pilot resolver --pilot-dir pilot --annotations a.json --annotations b.json
    python -m harness.pilot import --pilot-dir pilot --annotations a.json \
        --annotations b.json --resolutions resolution-r_....json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import Iterable, Sequence

import yaml

from harness.adjudication import load_adjudication
from harness.pilot_data import binding_payload, prepare_units
from harness.pilot_forms import (
    form_path,
    forms_for_documents,
    load_resolutions,
    write_resolution_template,
)
from harness.pilot_html import render_review_html
from harness.pilot_packets import load_map, load_review_documents
from harness.pilot_resolver import write_resolver_page
from harness.pilot_types import (
    DEFAULT_SEED,
    PACKET_COUNT,
    PILOT_SCHEMA_VERSION,
    PilotError,
    digest_value,
    json_text,
    sha256_file,
    yaml_text,
)


_SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def export_pilot(
    units: Iterable[dict],
    out_dir: Path,
    *,
    seed: str | int = DEFAULT_SEED,
    reference_source: str | None = None,
) -> dict:
    """Export two independent, engine-blind packets from loaded units.

    ``reference_source="gold"`` labels the reference text as a human
    transcription in the form; silver packets leave it out.
    """
    out_dir = Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise PilotError(f"output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    records = prepare_units(units)
    if not records:
        raise PilotError("at least one silver unit is required")

    used_ids: set[str] = set()
    for record in records:
        record["unit_id"] = _opaque_token(seed, "unit", record["source_key"])
        if record["unit_id"] in used_ids:
            raise PilotError("opaque unit ID collision")
        used_ids.add(record["unit_id"])

    map_units: dict[str, dict] = {}
    map_packets: dict[str, dict] = {}
    packet_specs: list[tuple[str, list[dict]]] = []
    for packet_number in range(1, PACKET_COUNT + 1):
        packet_id = _opaque_token(seed, "packet", str(packet_number))
        ordered = sorted(
            records,
            key=lambda record: _digest(
                seed, f"packet-order:{packet_number}", record["unit_id"]
            ),
        )
        packet_specs.append((packet_id, ordered))

    for packet_id, ordered in packet_specs:
        packet_dir = out_dir / "packets" / packet_id
        image_dir = packet_dir / "images"
        image_dir.mkdir(parents=True, exist_ok=False)
        public_units = []
        packet_unit_ids = []
        for record in ordered:
            unit_id = record["unit_id"]
            image_name = _opaque_token(
                seed, f"image:{packet_id}", unit_id
            ) + _image_suffix(record["image_path"])
            image_file = f"images/{image_name}"
            shutil.copyfile(record["image_path"], packet_dir / image_file)
            if sha256_file(packet_dir / image_file) != record["image_sha256"]:
                raise PilotError(f"copied image changed: {record['image_path']}")
            binding_sha = digest_value(binding_payload(record, unit_id))
            public = {
                "unit_id": unit_id,
                "binding_sha256": binding_sha,
                "image_sha256": record["image_sha256"],
                "hypothesis_sha256": record["hypothesis_sha256"],
                "image_file": image_file,
                "hypothesis_normalized": record["hypothesis_normalized"],
                "line_breaks": record["line_breaks"],
                "silver_reference": record["reference_normalized"],
                "candidate_spans": record["candidate_spans"],
                "entity_candidates": record["entity_candidates"],
            }
            public_units.append(public)
            packet_unit_ids.append(unit_id)
            unit_map = map_units.setdefault(
                unit_id,
                {
                    "source": record["source"],
                    "image_path": str(record["image_path"]),
                    "image_sha256": record["image_sha256"],
                    "hypothesis_normalized": record["hypothesis_normalized"],
                    "hypothesis_sha256": record["hypothesis_sha256"],
                    "line_breaks": record["line_breaks"],
                    "reference": record["reference"],
                    "reference_normalized": record["reference_normalized"],
                    "reference_sha256": record.get("reference_sha256"),
                    "score": record["score"],
                    "candidate_spans": record["candidate_spans"],
                    "entity_candidates": record["entity_candidates"],
                    "binding_sha256": binding_sha,
                    "packet_bindings": {},
                },
            )
            unit_map["packet_bindings"][packet_id] = {
                "image_file": image_file,
                "binding_sha256": binding_sha,
            }
        packet = {
            "schema_version": PILOT_SCHEMA_VERSION,
            "packet_id": packet_id,
            "unit_ids": packet_unit_ids,
            "units": public_units,
        }
        if reference_source is not None:
            packet["reference_source"] = reference_source
        packet["packet_sha256"] = digest_value(packet)
        _write_exclusive(packet_dir / "packet.json", json_text(packet))
        _write_exclusive(packet_dir / "review.html", render_review_html(packet))
        map_packets[packet_id] = {
            "path": str(Path("packets") / packet_id / "packet.json"),
            "html": str(Path("packets") / packet_id / "review.html"),
            "unit_ids": packet_unit_ids,
            "packet_sha256": packet["packet_sha256"],
        }

    map_payload = {
        "schema_version": PILOT_SCHEMA_VERSION,
        "seed_commitment": hashlib.sha256(str(seed).encode("utf-8")).hexdigest(),
        "packets": map_packets,
        "units": map_units,
    }
    if reference_source is not None:
        map_payload["reference_source"] = reference_source
    map_payload["map_sha256"] = digest_value(map_payload)
    coordinator = out_dir / "coordinator"
    coordinator.mkdir(parents=True, exist_ok=False)
    _write_exclusive(coordinator / ".gitignore", "*\n!.gitignore\n")
    _write_exclusive(coordinator / "map.json", json_text(map_payload))
    _write_exclusive(coordinator / "map.sha256", map_payload["map_sha256"] + "\n")
    packet_ids = [packet_id for packet_id, _ in packet_specs]
    return {
        "status": "pending",
        "unit_count": len(records),
        "packet_count": PACKET_COUNT,
        "packet_ids": packet_ids,
        "pending_units": sorted(map_units),
        "review_files": [
            str(out_dir / "packets" / packet_id / "review.html")
            for packet_id in packet_ids
        ],
        "map_path": str(coordinator / "map.json"),
    }


def import_annotations(
    pilot_dir: Path,
    annotations: Sequence[Path],
    *,
    resolutions: Path | None = None,
    out_dir: Path | None = None,
    allow_existing: bool = False,
) -> dict:
    """Import reviewer exports and write only validated private forms.

    Incomplete reviews return ``status=pending`` and write no adjudication. A
    third-party resolver is required for any disagreement before a form is
    accepted by the existing adjudication scorer.
    """
    pilot_dir = Path(pilot_dir)
    map_payload, _, documents = load_review_documents(pilot_dir, annotations)
    resolution_map = (
        load_resolutions(Path(resolutions), map_payload["map_sha256"])
        if resolutions
        else {}
    )
    states, forms = forms_for_documents(map_payload, documents, resolution_map)
    complete_ids = sorted(forms)
    target_dir = (
        Path(out_dir)
        if out_dir is not None
        else pilot_dir / "coordinator" / "adjudications"
    )
    paths = {
        unit_id: form_path(target_dir, map_payload["units"][unit_id])
        for unit_id in complete_ids
    }
    rendered = {unit_id: yaml_text(forms[unit_id]) for unit_id in complete_ids}
    for unit_id, path in paths.items():
        _check_existing(path, rendered[unit_id], allow_existing)
    for unit_id, path in paths.items():
        _write_exclusive(path, rendered[unit_id], allow_existing=allow_existing)
    pending = sorted(
        unit_id for unit_id, state in states.items() if state["status"] != "complete"
    )
    if pending and not resolution_map:
        write_resolution_template(pilot_dir, map_payload, states)
    return {
        "status": "complete"
        if not pending and len(forms) == len(map_payload["units"])
        else "pending",
        "unit_count": len(map_payload["units"]),
        "complete_units": complete_ids,
        "pending_units": pending,
        "units": states,
        "written": [str(paths[unit_id]) for unit_id in complete_ids],
    }


def pilot_status(pilot_dir: Path, annotations: Sequence[Path] = ()) -> dict:
    """Report whether each opaque unit awaits review, resolution, or import."""
    pilot_dir = Path(pilot_dir)
    map_payload, _, documents = load_review_documents(pilot_dir, annotations)
    states, _ = forms_for_documents(map_payload, documents, {})
    imported, invalid_imports = _load_imported_adjudications(pilot_dir, map_payload)
    for unit_id, scored in imported.items():
        states[unit_id] = {
            "status": "complete",
            "reason": "validated imported adjudication",
            "reviewers": scored["adjudication_reviewers"],
            "resolver": scored["adjudication_resolver"],
            "disagreements": scored["adjudication_disagreements"],
        }
    for unit_id, error in invalid_imports.items():
        if unit_id not in imported:
            states[unit_id] = {
                "status": "pending",
                "reason": f"invalid imported adjudication: {error}",
            }
    pending = sorted(
        unit_id for unit_id, state in states.items() if state["status"] != "complete"
    )
    reviewer_ids = {document["reviewer"].casefold() for document in documents}
    for scored in imported.values():
        reviewer_ids.update(
            reviewer.casefold() for reviewer in scored["adjudication_reviewers"]
        )
    return {
        "status": "complete" if not pending and states else "pending",
        "unit_count": len(states),
        "review_count": len(reviewer_ids),
        "complete_units": sorted(
            unit_id
            for unit_id, state in states.items()
            if state["status"] == "complete"
        ),
        "pending_units": pending,
        "imported_units": sorted(imported),
        "invalid_imports": invalid_imports,
        "units": states,
    }


def _load_imported_adjudications(
    pilot_dir: Path, map_payload: dict
) -> tuple[dict[str, dict], dict[str, str]]:
    """Load coordinator forms and validate each with the shared scorer."""
    target_dir = pilot_dir / "coordinator" / "adjudications"
    imported = {}
    invalid = {}
    if not target_dir.is_dir():
        return imported, invalid
    for unit_id in sorted(map_payload["units"]):
        unit = map_payload["units"][unit_id]
        try:
            path = form_path(target_dir, unit)
        except (PilotError, KeyError, TypeError, ValueError) as exc:
            invalid[unit_id] = str(exc)
            continue
        if not path.is_file():
            continue
        try:
            imported[unit_id] = load_adjudication(
                path,
                engine=unit["source"]["engine"],
                page=unit["source"]["page"],
                hyp_norm=unit["hypothesis_normalized"],
                page_score=unit["score"],
            )
        except (OSError, KeyError, TypeError, ValueError, yaml.YAMLError) as exc:
            invalid[unit_id] = str(exc)
    return imported, invalid


# Useful names for callers that already hold a pre-scored unit list.
export_units = export_pilot
status = pilot_status


def _image_suffix(path: Path) -> str:
    suffix = path.suffix.casefold()
    return (
        suffix
        if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".tif", ".tiff"}
        else ".bin"
    )


def _opaque_token(seed: str | int, purpose: str, value: str) -> str:
    return "u_" + _digest(seed, purpose, value)[:24]


def _digest(seed: str | int, purpose: str, value: str) -> str:
    payload = f"fabrication-pilot\0{seed}\0{purpose}\0{value}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_exclusive(path: Path, text: str, allow_existing: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if allow_existing and path.read_text(encoding="utf-8") == text:
            return
        raise PilotError(f"refusing to overwrite existing file: {path}")
    path.write_text(text, encoding="utf-8")


def _check_existing(path: Path, text: str, allow_existing: bool) -> None:
    if not path.exists():
        return
    if allow_existing and path.read_text(encoding="utf-8") == text:
        return
    raise PilotError(f"refusing to overwrite existing human work: {path}")


def _parse_units_file(path: Path) -> list[dict]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotError(f"cannot read units {path}: {exc}") from exc
    if isinstance(value, dict) and "units" in value:
        value = value["units"]
    if not isinstance(value, list):
        raise PilotError("units file must contain a JSON list or {units: [...]}")
    return value


def _export_gold(args: argparse.Namespace) -> dict:
    # Imported here: the gold loader builds on export_pilot in this module.
    from harness.cli import DEFAULTS
    from harness.pilot_gold import export_gold_packets, gold_dry_run, load_gold_units

    units = load_gold_units(
        args.run_dir,
        args.engine,
        selection=args.selection or DEFAULTS["selection"],
        sha=args.sha or DEFAULTS["sha"],
        images=args.images or DEFAULTS["images"],
        gt_dir=args.gt or DEFAULTS["gt"],
    )
    if args.dry_run:
        return {"dry_run": True, **gold_dry_run(units)}
    if not args.seed:
        raise PilotError("gold export needs a fresh --seed")
    return export_gold_packets(units, args.out, seed=args.seed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m harness.pilot", description=__doc__
    )
    sub = parser.add_subparsers(dest="command", required=True)
    export_parser = sub.add_parser("export", help="create two blinded review packets")
    export_parser.add_argument("--units", type=Path, required=True)
    export_parser.add_argument("--out", type=Path, required=True)
    export_parser.add_argument("--seed", default=DEFAULT_SEED)
    import_parser = sub.add_parser(
        "import", help="validate reviewer JSON and write adjudications"
    )
    import_parser.add_argument("--pilot-dir", type=Path, required=True)
    import_parser.add_argument("--annotations", type=Path, action="append", default=[])
    import_parser.add_argument("--reviewer-one", type=Path)
    import_parser.add_argument("--reviewer-two", type=Path)
    import_parser.add_argument("--resolutions", "--resolution", type=Path)
    import_parser.add_argument("--out", type=Path)
    import_parser.add_argument("--allow-existing", action="store_true")
    resolver_parser = sub.add_parser(
        "resolver", help="write the private resolver page for two reviews"
    )
    resolver_parser.add_argument("--pilot-dir", type=Path, required=True)
    resolver_parser.add_argument(
        "--annotations", type=Path, action="append", required=True
    )
    resolver_parser.add_argument("--out", type=Path)
    resolver_parser.add_argument("--hosted", action="store_true")
    gold_parser = sub.add_parser(
        "export-gold", help="blinded T3 packets for a sealed gold run (or a dry run)"
    )
    gold_parser.add_argument("--run-dir", type=Path, required=True)
    gold_parser.add_argument("--engine", action="append", required=True)
    gold_parser.add_argument("--seed", help="fresh seed; required unless --dry-run")
    target = gold_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--out", type=Path)
    target.add_argument("--dry-run", action="store_true", help="validate and count only")
    for name in ("selection", "sha", "images", "gt"):
        gold_parser.add_argument(f"--{name}", type=Path)
    status_parser = sub.add_parser("status", help="show pending review units")
    status_parser.add_argument("--pilot-dir", type=Path, required=True)
    status_parser.add_argument("--annotations", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            summary = export_pilot(
                _parse_units_file(args.units), args.out, seed=args.seed
            )
        elif args.command == "import":
            paths = list(args.annotations)
            paths.extend(
                path
                for path in (args.reviewer_one, args.reviewer_two)
                if path is not None
            )
            summary = import_annotations(
                args.pilot_dir,
                paths,
                resolutions=args.resolutions,
                out_dir=args.out,
                allow_existing=args.allow_existing,
            )
        elif args.command == "export-gold":
            summary = _export_gold(args)
        elif args.command == "resolver":
            summary = write_resolver_page(
                args.pilot_dir, args.annotations, args.out, hosted=args.hosted
            )
        else:
            summary = pilot_status(args.pilot_dir, args.annotations)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (PilotError, OSError, yaml.YAMLError) as exc:
        print(f"error: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
