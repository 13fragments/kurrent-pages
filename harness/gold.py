"""Gold v1 set access: selection.yml pages, GT text, entity annotations, freeze check.

Layout (protocol §1/§2):
  gold/selection.yml                  page list (scored + unscored annex)
  gold/v1_pages.sha256                freeze hashes for all images
  $BENCHMARK_EVAL_ROOT/data/benchmark_gold/v1_pages/{GID}.jpg
                                      images under test (private)
  $BENCHMARK_EVAL_ROOT/data/benchmark_gold/gt/{GID}.txt
                                      diplomatic GT, linearized per §3.2 (private)
  $BENCHMARK_EVAL_ROOT/data/benchmark_gold/entities/{GID}.yml
                                      gold entity lists (§2.5; private — §7
                                      forbids publishing annotations)

Entity YAML format:
  entities:
    - {type: person, surface: "Erich Wagener", normalized: "Erich Wagener",
       variants: ["E. Wagener"]}     # variants optional; type: person|place|date
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Protocol §8: strata whose primary-tagged pages form the kill-criterion set.
HARD_STRATA = frozenset(
    {
        "ugly_kurrent",
        "suetterlin",
        "table_registry",
        "marginalia",
        "mixed_print_handwriting",
    }
)


@dataclass(frozen=True)
class GoldPage:
    id: str
    image_name: str
    strata: tuple[str, ...]
    scored: bool
    primary: str = ""
    source: str = ""
    hand: str = ""
    hand_cluster: str = ""
    period: str = ""
    license: str = ""
    note: str = ""

    @property
    def primary_stratum(self) -> str:
        return self.primary or (self.strata[0] if self.strata else "annex")

    @property
    def hand_cluster_id(self) -> str:
        """Stable reporting cluster; explicit IDs may join pages across sources."""
        if self.hand_cluster.strip():
            return f"explicit:{self.hand_cluster.strip().casefold()}"
        source = self.source.strip() or self.id
        hand = self.hand.strip() or self.id
        return f"{source.casefold()}:{hand.casefold()}"


@dataclass(frozen=True)
class Entity:
    type: str  # person | place | date
    surface: str
    normalized: str
    variants: tuple[str, ...] = field(default=())

    def forms(self) -> tuple[str, ...]:
        # The diplomatic surface counts too: a transcription preserving the
        # page's own form must never score as a miss (e.g. surface 18.12.1924
        # vs an ISO-normalized value).
        return tuple(dict.fromkeys((self.normalized, self.surface, *self.variants)))


def load_selection(path: Path) -> list[GoldPage]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    pages = [
        GoldPage(
            id=str(entry["id"]),
            image_name=f"{entry['id']}.jpg",
            strata=tuple(entry.get("strata", [])),
            scored=True,
            primary=str(entry.get("primary", "")),
            source=_source_name(entry.get("file", "")),
            hand=str(entry.get("hand", "")),
            hand_cluster=str(entry.get("hand_cluster", "")),
            period=str(entry.get("period", "")),
            license=str(entry.get("license", "")),
            note=str(entry.get("note", "")),
        )
        for entry in data["selection"]
    ]
    for page in pages:
        if page.primary and page.primary not in page.strata:
            raise ValueError(
                f"{page.id}: primary {page.primary!r} is not in strata {page.strata!r}"
            )
    # Annex IDs are positional (A01 = first list entry) because the frozen
    # selection.yml carries no explicit ids for annex entries; the list order is
    # frozen together with the images, and verify_freeze() catches any drift.
    # Adding explicit ids to selection.yml would be a protocol §10 amendment.
    for i, entry in enumerate(data.get("unscored_annex_candidates", []), start=1):
        gid = f"A{i:02d}"
        pages.append(
            GoldPage(
                id=gid,
                image_name=f"{gid}_annex.jpg",
                strata=(),
                scored=False,
                source=_source_name(entry.get("file", "")),
                note=str(entry.get("note", "")),
            )
        )
    return pages


def _source_name(file_name: object) -> str:
    parts = Path(str(file_name)).parts
    return parts[0] if parts else ""


def hard_strata_pages(pages: list[GoldPage]) -> list[GoldPage]:
    return [p for p in pages if p.scored and p.primary_stratum in HARD_STRATA]


def load_gt(gt_dir: Path, page_id: str) -> str | None:
    """None = no usable GT. A whitespace-only file is a placeholder, not a
    transcription — it must not satisfy the §2 pre-run gate (no gold page in
    this set is legitimately blank)."""
    path = gt_dir / f"{page_id}.txt"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    return text if text.strip() else None


def load_entities(entities_dir: Path, page_id: str) -> list[Entity] | None:
    """None = page not annotated yet (skipped in entity metrics); [] = annotated,
    no entities. "Annotated" requires an explicit `entities:` key — an empty or
    malformed file is a placeholder and must not satisfy the §2 pre-run gate."""
    path = entities_dir / f"{page_id}.yml"
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("entities"), list):
        return None  # includes `entities:` (null) placeholders
    return [
        Entity(
            type=str(entry["type"]),
            surface=str(entry.get("surface", entry["normalized"])),
            normalized=str(entry["normalized"]),
            variants=tuple(str(v) for v in entry.get("variants", [])),
        )
        for entry in data["entities"]
    ]


def stratum_total_mismatches(path: Path) -> list[str]:
    """Cross-check explicit/fallback primary strata against strata_totals."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    declared = {
        name: count
        for name, count in (data.get("strata_totals") or {}).items()
        if isinstance(count, int)
    }
    counted: dict[str, int] = {}
    for page in load_selection(path):
        if page.scored:
            counted[page.primary_stratum] = counted.get(page.primary_stratum, 0) + 1
    return [
        f"stratum {name!r}: strata_totals says {count}, first-tag primaries give "
        f"{counted.get(name, 0)}"
        for name, count in sorted(declared.items())
        if counted.get(name, 0) != count
    ]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_freeze(
    images_dir: Path, sha_file: Path, expected_names: list[str] | None = None
) -> list[str]:
    """Check every frozen image hash (§7 freeze integrity). Returns problems, [] = clean.

    expected_names (e.g. every selection.yml image) additionally verifies that
    each page under test is covered by the manifest — an image swapped in
    without a hash line must not pass the freeze check."""
    problems: list[str] = []
    hashed: set[str] = set()
    for line in sha_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        expected, name = line.split(None, 1)
        name = name.strip()
        hashed.add(name)
        path = images_dir / name
        if not path.exists():
            problems.append(f"missing image: {name}")
        elif sha256_file(path) != expected:
            problems.append(f"hash mismatch (image differs from freeze): {name}")
    for name in expected_names or []:
        if name not in hashed:
            problems.append(f"page image not covered by freeze manifest: {name}")
    return problems
