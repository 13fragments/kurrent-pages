"""Shared constants and small serialization helpers for the review pilot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


PILOT_SCHEMA_VERSION = "fabrication-pilot-v01"
REVIEW_SCHEMA_VERSION = "fabrication-pilot-review-v01"
RESOLUTION_SCHEMA_VERSION = "fabrication-pilot-resolution-v01"
PACKET_COUNT = 2
DEFAULT_SEED = "20260906"


class PilotError(ValueError):
    """A pilot packet, review, or coordinator binding is unsafe or incomplete."""


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest_value(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def yaml_text(value: dict) -> str:
    import yaml

    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def overlap(start: int, end: int, other_start: int, other_end: int) -> bool:
    return start < other_end and end > other_start
