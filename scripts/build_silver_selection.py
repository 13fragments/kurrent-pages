#!/usr/bin/env python3
"""Build the gitignored silver harness inputs from the dev manifest.

This is an adapter only: it does not read or modify transcript text. Silver GT
is model-generated and remains harness-plumbing data, never gold.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from harness.gold import sha256_file


ENTITY_TYPES = (("persons", "person"), ("places", "place"), ("dates", "date"))


def build_silver_selection(
    manifest_path: Path,
    gt_dir: Path,
    images_dir: Path,
    out_selection: Path,
    out_entities_dir: Path,
) -> None:
    manifest = _load_json(manifest_path)
    pages = manifest.get("pages")
    if not isinstance(pages, dict):
        raise ValueError(f"{manifest_path}: expected object key 'pages'")
    page_count = manifest.get("page_count")
    if page_count != len(pages):
        raise ValueError(f"{manifest_path}: page_count {page_count!r} != {len(pages)} pages")

    selection: list[dict[str, Any]] = []
    stratum_counts: Counter[str] = Counter()
    for page_id in sorted(pages):
        info = pages[page_id]
        if not isinstance(info, dict):
            raise ValueError(f"{manifest_path}: page {page_id!r} must be an object")
        manifest_stratum = _required_str(info, "stratum", f"{manifest_path}:{page_id}")
        meta_path = gt_dir / f"{page_id}.meta.json"
        # Verify the meta file too: it carries the person/place/date entities that feed
        # entity-recall scoring, so unchecked drift would silently change results.
        _require_hash(meta_path, info.get("meta_sha256"), f"{page_id} meta")
        meta = _load_json(meta_path)
        if meta.get("id") != page_id:
            raise ValueError(f"{meta_path}: id {meta.get('id')!r} != {page_id!r}")
        meta_stratum = _required_str(meta, "stratum", str(meta_path))
        if meta_stratum != manifest_stratum:
            raise ValueError(
                f"{page_id}: manifest stratum {manifest_stratum!r} != meta stratum {meta_stratum!r}"
            )
        # Enforce the manifest's integrity hashes: the silver pages are gitignored, so
        # the manifest is the only tracked guarantee that the on-disk transcript/image
        # the adapter feeds into run/score is the one recorded. Fail closed on drift.
        _require_hash(gt_dir / f"{page_id}.txt", info.get("gt_sha256"), f"{page_id} GT")
        _require_hash(images_dir / f"{page_id}.jpg", info.get("image_sha256"), f"{page_id} image")
        stratum_counts[manifest_stratum] += 1
        selection.append(
            {
                "id": page_id,
                "file": f"pages/{page_id}.jpg",
                "primary": manifest_stratum,
                "strata": [manifest_stratum],
                "hand": "",
                "period": "",
                "license": "",
                "note": _note(meta),
            }
        )
        _write_entity_yaml(out_entities_dir / f"{page_id}.yml", meta)

    document = {
        # No timestamp: the output must be byte-deterministic so its sha256 is stable
        # across regenerations (score/report reject a selection whose hash drifted from
        # the one recorded at run time).
        "purpose": (
            "Silver dev-set adapter for harness plumbing validation only. "
            "Transcripts/entities are model-generated and never gold."
        ),
        "source_manifest": str(manifest_path),
        "strata_totals": dict(sorted(stratum_counts.items())),
        "selection": selection,
    }
    out_selection.parent.mkdir(parents=True, exist_ok=True)
    out_selection.write_text(
        yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected JSON object")
    return data


def _required_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}: expected non-empty string key {key!r}")
    return value


def _require_hash(path: Path, expected: Any, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label}: missing file {path}")
    if not isinstance(expected, str) or not expected:
        raise ValueError(f"{label}: manifest has no sha256 to verify {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"{label}: {path} sha256 {actual[:12]}… != manifest {expected[:12]}… "
            "(silver data drifted from the manifest; regenerate or restore it)"
        )


def _note(meta: dict[str, Any]) -> str:
    parts = []
    confidence = meta.get("confidence")
    if confidence:
        parts.append(f"silver confidence: {confidence}")
    notes = meta.get("notes")
    if notes:
        parts.append(str(notes))
    return " | ".join(parts)


def _write_entity_yaml(path: Path, meta: dict[str, Any]) -> None:
    entities = meta.get("entities")
    if not isinstance(entities, dict):
        raise ValueError(f"{meta.get('id', '<unknown>')}: expected object key 'entities'")
    rows: list[dict[str, str]] = []
    for source_key, entity_type in ENTITY_TYPES:
        values = entities.get(source_key, [])
        if not isinstance(values, list):
            raise ValueError(f"{meta.get('id', '<unknown>')}: entities.{source_key} must be a list")
        seen: set[str] = set()
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            rows.append({"type": entity_type, "surface": text, "normalized": text})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"entities": rows}, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("harness/dev_manifest.json"))
    parser.add_argument("--gt", type=Path, default=Path("data/dev_silver/gt"))
    parser.add_argument("--images", type=Path, default=Path("data/dev_silver/pages"))
    parser.add_argument("--out-selection", type=Path, default=Path("data/dev_silver/selection.yml"))
    parser.add_argument("--out-entities", type=Path, default=Path("data/dev_silver/entities"))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    build_silver_selection(
        args.manifest, args.gt, args.images, args.out_selection, args.out_entities
    )
    print(f"selection: {args.out_selection}")
    print(f"entities: {args.out_entities}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
