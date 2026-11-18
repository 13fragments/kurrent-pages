#!/usr/bin/env python3
"""Conservative-union resolution of two model reviews (docs/T3_MODEL_REVIEW.md, "Resolver").

Candidate labels: the more severe label of the two reviewers. Added spans and added entities:
the importer pairs the two reviewers' proposals one-to-one (`manual_alignment`) and needs exactly
one consensus claim per pair, overlapping every proposal of the pair, with the agreed label when
the two agree. So the union is built per pair:

1. Each pair gets a witness: the shared characters of two overlapping proposals, or the single
   proposal. Witnesses never overlap.
2. The characters of the union between witnesses go to a neighbouring pair. A pair whose two
   reviewers agree keeps its label and takes only characters no more severe than that label; an
   exact agreeing pair takes none. Other pairs take any characters.
3. A pair with agreeing reviewers keeps the agreed label; any other pair takes the most severe
   label among the proposals that cover its characters.

So every character keeps at least the most severe label of the proposals that cover it, except
characters that no neighbour can take; their count is printed (`unrepresentable_chars`).
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.adjudication_reliability import _manual_key, manual_alignment  # noqa: E402
from harness.pilot_forms import review_disagreement  # noqa: E402
from harness.pilot_packets import load_review_documents  # noqa: E402
from harness.pilot_types import RESOLUTION_SCHEMA_VERSION, json_text  # noqa: E402

RESOLVER = "rule:conservative-union"
SPAN_ORDER = ["fluent_fabrication", "degenerate_generation", "perception_error", "order_layout_error",
              "convention_error", "gt_or_image_uncertain", "supported"]
ENTITY_ORDER = ["fabricated", "uncertain", "supported", "not_entity"]


def union_claims(first: list[dict], second: list[dict], order: list[str], entity: bool) -> tuple[list[dict], int]:
    pairs = manual_alignment(first, second, entity=entity)
    severity: dict[int, int] = {}
    for item in first + second:
        for x in range(item["start"], item["end"]):
            severity[x] = min(severity.get(x, len(order)), order.index(item["label"]))
    claims = []
    for left, right in pairs:
        members = [m for m in (left, right) if m is not None]
        start, end = max(m["start"] for m in members), min(m["end"] for m in members)
        agreed = left is not None and right is not None and left["label"] == right["label"]
        exact = agreed and _manual_key(left, entity) == _manual_key(right, entity)
        claims.append({"start": start, "end": end, "agreed": agreed, "exact": exact, "label": members[0]["label"]
                       if agreed else min((m["label"] for m in members), key=order.index),
                       "kind": members[0].get("kind")})
    claims.sort(key=lambda c: c["start"])
    lost = 0

    def can_take(claim: dict | None, gap: range) -> bool:
        if claim is None or claim["exact"]:
            return False
        return not claim["agreed"] or min(severity[x] for x in gap) >= order.index(claim["label"])

    # gaps: maximal runs of union characters outside every witness
    witness = {x for c in claims for x in range(c["start"], c["end"])}
    gaps, run = [], []
    for x in sorted(severity):
        if x in witness or (run and x != run[-1] + 1):
            if run:
                gaps.append(range(run[0], run[-1] + 1))
            run = [] if x in witness else [x]
        else:
            run.append(x)
    if run:
        gaps.append(range(run[0], run[-1] + 1))
    for gap in gaps:
        before = next((c for c in reversed(claims) if c["end"] == gap.start), None)
        after = next((c for c in claims if c["start"] == gap.stop), None)
        options = [c for c in (before, after) if can_take(c, gap)]
        options.sort(key=lambda c: (c["agreed"], order.index(c["label"])))
        if not options:
            lost += sum(severity[x] < len(order) - 1 for x in gap)
            continue
        target = options[0]
        target["start"], target["end"] = min(target["start"], gap.start), max(target["end"], gap.stop)
    for claim in claims:
        if not claim["agreed"]:
            claim["label"] = order[min(severity[x] for x in range(claim["start"], claim["end"]))]
    keys = ("start", "end", "kind", "label") if entity else ("start", "end", "label")
    return [{k: c[k] for k in keys} for c in claims], lost


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pilot-dir", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    map_payload, _, documents = load_review_documents(args.pilot_dir, [args.first, args.second])
    first, second = documents
    units, lost = {}, 0
    shared = sorted(set(first["units"]) & set(second["units"]))
    for unit_id in shared:
        a, b = first["units"][unit_id], second["units"][unit_id]
        if not review_disagreement(a, b):
            continue
        worse = lambda x, y, order: min(x, y, key=order.index)  # noqa: E731
        spans, lost_spans = union_claims(a["added_spans"], b["added_spans"], SPAN_ORDER, entity=False)
        entities, lost_entities = union_claims(a["manual_entities"], b["manual_entities"], ENTITY_ORDER, entity=True)
        lost += lost_spans + lost_entities
        units[unit_id] = {
            "resolver": RESOLVER, "reason": "reviewers disagree",
            "candidate_labels": [{"candidate_id": c, "label": worse(a["candidate_labels"][c], b["candidate_labels"][c], SPAN_ORDER)}
                                 for c in sorted(a["candidate_labels"])],
            "manual_spans": spans,
            "entity_labels": [{"candidate_id": c, "label": worse(a["entity_labels"][c], b["entity_labels"][c], ENTITY_ORDER)}
                              for c in sorted(a["entity_labels"])],
            "manual_entities": entities,
        }
    document = {"schema_version": RESOLUTION_SCHEMA_VERSION, "map_sha256": map_payload["map_sha256"],
                "resolver": RESOLVER, "units": units}
    args.out.write_text(json_text(document), encoding="utf-8")
    print(f"resolved {len(units)} disagreeing units of {len(shared)}; unrepresentable_chars {lost}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
