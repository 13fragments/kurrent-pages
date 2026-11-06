"""Prepare caller-provided silver units and their private bindings."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Iterable

from harness import normalization
from harness.entities import extract_entity_risk_candidates
from harness.pilot_types import PilotError, canonical, overlap
from harness.trust import score_trust_diagnostics
from harness.adjudication_schema import ENTITY_KINDS


def prepare_units(units: Iterable[dict]) -> list[dict]:
    """Normalize and bind loaded units without discovering any input files."""
    if isinstance(units, dict):
        units = units.get("units", [])
    if not isinstance(units, Iterable) or isinstance(units, (str, bytes)):
        raise PilotError("units must be a list of loaded silver records")
    records = []
    seen_source: set[str] = set()
    for index, raw in enumerate(units):
        if not isinstance(raw, dict):
            raise PilotError(f"unit {index} must be an object")
        for field in ("engine", "page", "image_path", "reference", "hypothesis"):
            if not isinstance(raw.get(field), (str, Path)):
                raise PilotError(f"unit {index}.{field} is required")
        image_path = Path(raw["image_path"])
        if not image_path.is_file():
            raise PilotError(f"unit {index}: image does not exist: {image_path}")
        image_sha = _sha256_file(image_path)
        declared_image_sha = raw.get("image_sha256")
        if declared_image_sha is not None:
            if (
                not isinstance(declared_image_sha, str)
                or declared_image_sha.casefold() != image_sha
            ):
                raise PilotError(
                    f"unit {index}: image SHA-256 does not match image_path"
                )
        reference = str(raw["reference"])
        hypothesis = str(raw["hypothesis"])
        reference_scored, hypothesis_scored = normalization.scoring_texts(
            reference, hypothesis
        )
        reference_normalized = normalization.normalize(reference_scored)
        hypothesis_normalized = normalization.normalize(hypothesis_scored)
        for field, expected in (
            ("reference_normalized", reference_normalized),
            ("hypothesis_normalized", hypothesis_normalized),
        ):
            if field in raw and raw[field] != expected:
                raise PilotError(
                    f"unit {index}: {field} does not match normalized text"
                )
        hypothesis_sha = hashlib.sha256(
            hypothesis_normalized.encode("utf-8")
        ).hexdigest()
        source = {
            key: str(raw[key])
            for key in (
                "engine",
                "page",
                "stratum",
                "source_run",
                "source_run_sha256",
                "source_record_sha256",
                "silver_manifest_sha256",
                "source_model_id",
                "source_config_sha256",
            )
            if raw.get(key) is not None
        }
        source_key = canonical(
            {
                "engine": source["engine"],
                "page": source["page"],
                "stratum": source.get("stratum"),
                "source_run": source.get("source_run"),
                "source_record_sha256": source.get("source_record_sha256"),
                "image_sha256": image_sha,
                "hypothesis_sha256": hypothesis_sha,
            }
        )
        if source_key in seen_source:
            raise PilotError(f"duplicate silver unit: {raw['engine']}/{raw['page']}")
        seen_source.add(source_key)
        score = copy.deepcopy(raw.get("score")) if raw.get("score") is not None else {}
        if not isinstance(score, dict):
            raise PilotError(f"unit {index}.score must be an object")
        if (
            not score.get("review_candidate_spans_auto")
            or "entity_risk_candidates" not in score
        ):
            score = {
                **score_trust_diagnostics(reference_normalized, hypothesis_normalized),
                **extract_entity_risk_candidates(hypothesis_normalized),
                **score,
            }
        if score.get("hypothesis_sha256") not in (None, hypothesis_sha):
            raise PilotError(f"unit {index}: score is bound to a different hypothesis")
        if score.get("image_sha256") not in (None, image_sha):
            raise PilotError(f"unit {index}: score is bound to a different image")
        declared_hyp_chars = score.get("hyp_chars")
        if declared_hyp_chars is not None and (
            isinstance(declared_hyp_chars, bool)
            or not isinstance(declared_hyp_chars, int)
            or declared_hyp_chars != len(hypothesis_normalized)
        ):
            raise PilotError(
                f"unit {index}: score hypothesis length does not match hypothesis"
            )
        score["hypothesis_sha256"] = hypothesis_sha
        score["hyp_chars"] = len(hypothesis_normalized)
        score["image_sha256"] = image_sha
        line_breaks = line_starts(hypothesis_scored, hypothesis_normalized)
        candidate_spans = candidate_spans_from_score(
            score.get("review_candidate_spans_auto", []), hypothesis_normalized
        )
        entity_candidates = entity_candidates_from_score(
            score.get("entity_risk_candidates", []), hypothesis_normalized
        )
        reference_sha = raw.get("reference_sha256")
        expected_reference_sha = hashlib.sha256(reference.encode("utf-8")).hexdigest()
        if reference_sha is not None:
            if (
                not isinstance(reference_sha, str)
                or reference_sha.casefold() != expected_reference_sha
            ):
                raise PilotError(
                    f"unit {index}: reference_sha256 does not match reference"
                )
        records.append(
            {
                "source_key": source_key,
                "source": source,
                "image_path": image_path,
                "image_sha256": image_sha,
                "reference": reference,
                "reference_normalized": reference_normalized,
                "reference_sha256": reference_sha,
                "hypothesis_normalized": hypothesis_normalized,
                "hypothesis_sha256": hypothesis_sha,
                "line_breaks": line_breaks,
                "score": score,
                "candidate_spans": candidate_spans,
                "entity_candidates": entity_candidates,
            }
        )
    return sorted(records, key=lambda record: record["source_key"])


def line_starts(scored: str, normalized: str) -> list[int]:
    """Offsets in ``normalized`` where a line of the engine output begins.

    Normalization joins lines, so the form cannot show the scan's line breaks
    from the scored text alone.  Each output line is normalized on its own and
    matched at the running cursor.  Normalization always drops a stroke that
    directly precedes a newline, so the walk drops it too; a line that held
    only that stroke disappears.  The first mismatch ends the walk, and the
    form then shows the remaining text unbroken.  Offsets count code points,
    like all spans.
    """
    starts: list[int] = []
    cursor = 0
    lines = scored.split("\n")
    for number, line in enumerate(lines):
        if number < len(lines) - 1 and line[-1:] in ("-", "=", "⸗"):
            line = line[:-1]
        piece = normalization.normalize(line)
        if not piece:
            continue
        if cursor and cursor < len(normalized) and normalized[cursor] == " ":
            cursor += 1
        if not normalized.startswith(piece, cursor):
            break
        if cursor:
            starts.append(cursor)
        cursor += len(piece)
    return [start for start in starts if 0 < start < len(normalized)]


def validate_line_breaks(value: object, hypothesis: str) -> list[int]:
    if not isinstance(value, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise PilotError("line breaks must be a list of offsets")
    if value != sorted(set(value)) or any(
        not 0 < item < len(hypothesis) for item in value
    ):
        raise PilotError("line breaks must be increasing offsets inside the text")
    return value


def candidate_spans_from_score(value: object, hypothesis: str) -> list[dict]:
    if not isinstance(value, list):
        raise PilotError("review candidate spans must be a list")
    result = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise PilotError(f"candidate span {index} is invalid")
        start, end = range_from(raw, hypothesis, f"candidate span {index}")
        candidate_id = raw["id"]
        if candidate_id in seen:
            raise PilotError(f"duplicate candidate span ID: {candidate_id}")
        seen.add(candidate_id)
        result.append(
            {
                "id": candidate_id,
                "start": start,
                "end": end,
                "text": hypothesis[start:end],
            }
        )
    require_nonoverlap(result, "candidate spans")
    return result


def entity_candidates_from_score(value: object, hypothesis: str) -> list[dict]:
    if not isinstance(value, list):
        raise PilotError("entity candidates must be a list")
    result = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
            raise PilotError(f"entity candidate {index} is invalid")
        start, end = range_from(raw, hypothesis, f"entity candidate {index}")
        kind = raw.get("kind")
        if kind not in ENTITY_KINDS:
            raise PilotError(f"entity candidate {index} has unknown kind")
        if raw["id"] in seen:
            raise PilotError(f"duplicate entity candidate ID: {raw['id']}")
        seen.add(raw["id"])
        result.append(
            {
                "id": raw["id"],
                "start": start,
                "end": end,
                "text": hypothesis[start:end],
                "kind": kind,
            }
        )
    require_nonoverlap(result, "entity candidates")
    return result


def range_from(raw: dict, hypothesis: str, field: str) -> tuple[int, int]:
    start, end = raw.get("start"), raw.get("end")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
    ):
        raise PilotError(f"{field} offsets must be integers")
    if not 0 <= start < end <= len(hypothesis):
        raise PilotError(f"{field} offsets are outside the hypothesis")
    if "text" in raw and raw["text"] != hypothesis[start:end]:
        raise PilotError(f"{field} text does not match hypothesis offsets")
    return start, end


def binding_payload(record: dict, unit_id: str) -> dict:
    return {
        "unit_id": unit_id,
        "image_sha256": record["image_sha256"],
        "hypothesis_sha256": record["hypothesis_sha256"],
        "hypothesis_normalized": record["hypothesis_normalized"],
        "reference_sha256": record.get("reference_sha256"),
        "candidate_spans": record["candidate_spans"],
        "entity_candidates": record["entity_candidates"],
    }


def binding_payload_from_map(unit_id: str, unit: dict) -> dict:
    return {
        "unit_id": unit_id,
        "image_sha256": unit.get("image_sha256"),
        "hypothesis_sha256": unit.get("hypothesis_sha256"),
        "hypothesis_normalized": unit.get("hypothesis_normalized"),
        "reference_sha256": unit.get("reference_sha256"),
        "candidate_spans": unit.get("candidate_spans"),
        "entity_candidates": unit.get("entity_candidates"),
    }


def require_nonoverlap(items: list[dict], field: str) -> None:
    ordered = sorted(items, key=lambda item: (item["start"], item["end"]))
    for previous, current in zip(ordered, ordered[1:]):
        if overlap(
            previous["start"], previous["end"], current["start"], current["end"]
        ):
            raise PilotError(f"{field} must not overlap")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
