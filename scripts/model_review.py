#!/usr/bin/env python3
"""T3 fabrication review by two model reviewers (docs/T3_MODEL_REVIEW.md).

Subcommands:
  review    one model reviews every unit of one packet of a pilot or gold coordinator dir and
            writes a review export that `harness.pilot import` accepts
  probes    build the silver probe units (clean, planted, misread) from data/dev_silver
  review-probes  one model reviews the probe units
  calibrate gates C1 and C2 and the reported agreement with reviewer 1 (silver only)
(The conservative-union resolution is scripts/model_review_resolve.py.)

Each unit is one CLI session (the isolation of engines `fable51_max` and `gpt6_astra_max`):
the scan as an image, then the instructions with the reference, the numbered machine text, and
the candidates. The reply is one JSON object; added spans come back as line numbers and quotes
and are mapped to offsets here. Replies are cached per unit under `<out>.d/` and reused on a
rerun when the instruction digest matches. Gold runs print counts only, never page text.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import difflib
import hashlib
import json
from pathlib import Path
import random
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from harness.adjudication_schema import ENTITY_KINDS, ENTITY_LABELS, SPAN_LABELS  # noqa: E402
from harness.engines.base import EngineError, EngineUnavailable  # noqa: E402
from harness.engines.claude_cli import ClaudeCliEngine  # noqa: E402
from harness.engines.codex_cli import CodexCliEngine  # noqa: E402
from harness.pilot_packets import load_map, load_packets  # noqa: E402
from harness.pilot_types import REVIEW_SCHEMA_VERSION, json_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = ROOT / "configs/prompts/vlm_default.txt"  # engine init only; replaced per unit
JUDGES = {
    "fable": (ClaudeCliEngine, {"model": "claude-fable-5-1", "effort": "max", "timeout": 3600}),
    "astra": (CodexCliEngine, {"model": "gpt-6-astra", "reasoning_effort": "max", "timeout": 3600}),
}
REVIEWER = {"fable": "model:claude-fable-5-1:max", "astra": "model:gpt-6-astra:max"}
SPAN_ORDER = ["fluent_fabrication", "degenerate_generation", "perception_error", "order_layout_error",
              "convention_error", "gt_or_image_uncertain", "supported"]
INSTRUCTIONS = (ROOT / "configs/prompts/t3_model_review.txt")
PLANTED = [  # fluent German sentences that appear on no probe page; fixed before any run
    "Am folgenden Morgen reisten wir mit der Post nach Leipzig, wo uns der Onkel am Bahnhof erwartete.",
    "Der Bürgermeister ließ bekanntgeben, dass die Brücke über die Saale bis zum Herbst gesperrt bleibe.",
    "Meine Schwester Wilhelmine hat inzwischen das Haus in der Gartenstraße für dreihundert Taler verkauft.",
    "Wir haben beschlossen, die Ernte in diesem Jahr gemeinsam mit den Nachbarn aus Oberweiler einzubringen.",
    "Der Herr Pfarrer Lindemann bittet um baldige Nachricht wegen der Taufe am zweiten Sonntag im Mai.",
    "Nach langer Krankheit ist der alte Förster Brandauer am vergangenen Dienstag sanft entschlafen.",
    "Bitte sende mir mit dem nächsten Brief die Rechnung des Schneiders und zwei Paar wollene Strümpfe.",
    "Die Versammlung des Gewerbevereins wurde wegen des schlechten Wetters auf den Donnerstag verlegt.",
]
LOOKALIKE = {"e": "c", "c": "e", "n": "u", "u": "n", "m": "w", "w": "m", "a": "o", "o": "a", "i": "j",
             "l": "t", "t": "l", "h": "k", "f": "s", "s": "f", "r": "v", "d": "o", "g": "y", "b": "h"}


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def lines_of(hypothesis: str, breaks: list[int]) -> list[tuple[int, str]]:
    bounds = [0, *breaks, len(hypothesis)]
    return [(bounds[i], hypothesis[bounds[i]:bounds[i + 1]]) for i in range(len(bounds) - 1)]


def line_number(lines: list[tuple[int, str]], offset: int) -> int:
    return max(i for i, (start, _) in enumerate(lines) if start <= offset) + 1


def build_prompt(unit: dict, reference_kind: str) -> tuple[str, dict, dict]:
    lines = lines_of(unit["hypothesis_normalized"], unit.get("line_breaks") or [])
    spans = {f"S{i + 1}": c for i, c in enumerate(unit["candidate_spans"])}
    entities = {f"E{i + 1}": c for i, c in enumerate(unit["entity_candidates"])}
    numbered = "\n".join(f"L{i + 1}: {text.strip()}" for i, (_, text) in enumerate(lines))
    span_list = "\n".join(f"{k} (line {line_number(lines, c['start'])}): {c['text']}" for k, c in spans.items())
    entity_list = "\n".join(f"{k} (line {line_number(lines, c['start'])}, {c['kind']}): {c['text']}"
                            for k, c in entities.items())
    prompt = INSTRUCTIONS.read_text(encoding="utf-8").format(
        reference_kind=reference_kind, reference=unit["reference"], machine_text=numbered,
        span_candidates=span_list or "(none)", entity_candidates=entity_list or "(none)")
    return prompt, spans, entities


def ask(judge: str, image: Path, prompt: str, attempts: int = 2) -> dict:
    engine_class, config = JUDGES[judge]
    last = None
    for _ in range(attempts):
        engine = engine_class(judge, {**config, "prompt_file": str(PROMPT_FILE)})
        engine.prompt = prompt
        try:
            output = engine.transcribe(image)
        except EngineError as error:  # EngineUnavailable (usage limit, auth) propagates
            last = f"engine error: {error}"[:300]
            continue
        match = re.search(r"\{.*\}", output.text, re.S)
        try:
            reply = json.loads(match.group(0)) if match else None
        except json.JSONDecodeError:
            reply = None
        if isinstance(reply, dict):
            return {"reply": reply, "model_id": output.model_id, "seconds": round(output.duration_s, 1),
                    "usage": output.meta.get("usage")}
        last = "reply is not one JSON object"
    return {"error": last}


def find_quote(text: str, quote: str, last: bool = False) -> tuple[int, int] | None:
    quote = " ".join(str(quote).split())
    if not quote:
        return None
    index = text.rfind(quote) if last else text.find(quote)
    if index >= 0:
        return index, index + len(quote)
    matcher = difflib.SequenceMatcher(None, text, quote, autojunk=False)
    block = max(matcher.get_matching_blocks(), key=lambda b: b.size)
    if block.size == 0:
        return None
    start = max(0, block.a - block.b)
    window = text[start:start + len(quote)]
    if difflib.SequenceMatcher(None, window, quote).ratio() >= 0.8:
        return start, start + len(window)
    return None


def subtract(start: int, end: int, ranges: list[tuple[int, int]], text: str) -> list[tuple[int, int]]:
    pieces = [(start, end)]
    for r_start, r_end in sorted(ranges):
        pieces = [p for s, e in pieces for p in ((s, min(e, r_start)), (max(s, r_end), e)) if p[0] < p[1]]
    result = []
    for s, e in pieces:
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if s < e and any(ch.isalnum() for ch in text[s:e]):
            result.append((s, e))
    return result


def merge(items: list[dict], order: list[str]) -> list[dict]:
    merged: list[dict] = []
    for item in sorted(items, key=lambda x: (x["start"], x["end"])):
        if merged and item["start"] < merged[-1]["end"]:
            last = merged[-1]
            last["end"] = max(last["end"], item["end"])
            last["label"] = min(last["label"], item["label"], key=order.index)
        else:
            merged.append(dict(item))
    return merged


def map_reply(unit: dict, reply: dict, spans: dict, entities: dict) -> tuple[dict, dict]:
    """Review entry for one unit plus mapping counts; unknown or missing labels fail the unit."""
    hypothesis = unit["hypothesis_normalized"]
    lines = lines_of(hypothesis, unit.get("line_breaks") or [])
    span_labels = {spans[k]["id"]: v for k, v in (reply.get("spans") or {}).items() if k in spans}
    entity_labels = {entities[k]["id"]: v for k, v in (reply.get("entities") or {}).items() if k in entities}
    if set(span_labels) != {c["id"] for c in spans.values()} or set(span_labels.values()) - SPAN_LABELS:
        raise ValueError("span candidates not all labelled with known labels")
    if set(entity_labels) != {c["id"] for c in entities.values()} or set(entity_labels.values()) - ENTITY_LABELS:
        raise ValueError("entity candidates not all labelled with known labels")
    counts = {"added": 0, "unmapped": 0, "added_entities": 0, "unmapped_entities": 0}
    candidate_ranges = [(c["start"], c["end"]) for c in unit["candidate_spans"]]
    added = []
    for item in reply.get("added_spans") or []:
        try:
            first, last = int(item["line"]) - 1, int(item.get("end_line", item["line"])) - 1
            label = item["label"]
            start_line, end_line = lines[first], lines[last]
        except (KeyError, ValueError, TypeError, IndexError):
            counts["unmapped"] += 1
            continue
        a = find_quote(start_line[1], item.get("start", ""))
        b = find_quote(end_line[1], item.get("end", item.get("start", "")), last=True)
        if label not in SPAN_LABELS or a is None or b is None or end_line[0] + b[1] <= start_line[0] + a[0]:
            counts["unmapped"] += 1
            continue
        for s, e in subtract(start_line[0] + a[0], end_line[0] + b[1], candidate_ranges, hypothesis):
            added.append({"start": s, "end": e, "label": label})
        counts["added"] += 1
    entity_ranges = [(c["start"], c["end"]) for c in unit["entity_candidates"]]
    manual = []
    for item in reply.get("added_entities") or []:
        try:
            start, text = lines[int(item["line"]) - 1]
            kind, label = item["kind"], item["label"]
        except (KeyError, ValueError, TypeError, IndexError):
            counts["unmapped_entities"] += 1
            continue
        found = find_quote(text, item.get("text", ""))
        if found is None or kind not in ENTITY_KINDS or label not in ENTITY_LABELS:
            counts["unmapped_entities"] += 1
            continue
        s, e = start + found[0], start + found[1]
        taken = entity_ranges + [(m["start"], m["end"]) for m in manual]
        if not any(s < r_end and e > r_start for r_start, r_end in taken):
            manual.append({"start": s, "end": e, "kind": kind, "label": label})
            counts["added_entities"] += 1
    entry = {
        "full_page_reviewed": True,
        "candidate_labels": [{"candidate_id": k, "label": v} for k, v in sorted(span_labels.items())],
        "added_spans": merge(added, SPAN_ORDER),
        "entity_labels": [{"candidate_id": k, "label": v} for k, v in sorted(entity_labels.items())],
        "manual_entities": sorted(manual, key=lambda m: (m["start"], m["end"])),
        "unit_note": str(reply.get("note", ""))[:500],
    }
    return entry, counts


def run_units(judge: str, units: list[dict], cache: Path, reference_kind: str, workers: int) -> dict:
    cache.mkdir(parents=True, exist_ok=True)
    digest = sha256(INSTRUCTIONS.read_text(encoding="utf-8"))
    results, todo = {}, []
    for unit in units:
        path = cache / f"{unit['unit_id']}.json"
        if path.exists():
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("instructions_sha256") == digest and "reply" in cached:
                results[unit["unit_id"]] = cached
                continue
        todo.append(unit)
    print(f"{judge}: {len(units)} units, {len(results)} cached, {len(todo)} to review", file=sys.stderr, flush=True)

    def one(unit: dict) -> tuple[str, dict]:
        prompt, _, _ = build_prompt(unit, reference_kind)
        answer = ask(judge, unit["image"], prompt)
        answer.update(instructions_sha256=digest, prompt_sha256=sha256(prompt))
        (cache / f"{unit['unit_id']}.json").write_text(json_text(answer), encoding="utf-8")
        return unit["unit_id"], answer

    with ThreadPoolExecutor(workers) as pool:
        futures = [pool.submit(one, unit) for unit in todo]
        for done, future in enumerate(as_completed(futures), 1):
            unit_id, answer = future.result()
            results[unit_id] = answer
            print(f"{judge}: {done}/{len(todo)} {'error' if 'error' in answer else 'ok'}", file=sys.stderr, flush=True)
    return results


def packet_units(pilot_dir: Path, packet_id: str) -> tuple[dict, list[dict]]:
    map_payload = load_map(pilot_dir)
    packet = load_packets(pilot_dir, map_payload)[packet_id]
    units = []
    for public in packet["units"]:
        unit = dict(public)
        unit["reference"] = public.get("silver_reference") or map_payload["units"][public["unit_id"]]["reference_normalized"]
        unit["image"] = pilot_dir / "packets" / packet_id / public["image_file"]
        units.append(unit)
    return packet, units


def command_review(args: argparse.Namespace) -> int:
    map_payload = load_map(args.pilot_dir)
    packet_id = list(map_payload["packets"])[args.packet_index]
    packet, units = packet_units(args.pilot_dir, packet_id)
    results = run_units(args.judge, units, Path(str(args.out) + ".d"), args.reference_kind, args.workers)
    review, totals, failed = {}, {"added": 0, "unmapped": 0, "added_entities": 0, "unmapped_entities": 0}, []
    for unit in units:
        _, spans, entities = build_prompt(unit, args.reference_kind)
        answer = results.get(unit["unit_id"], {})
        try:
            entry, counts = map_reply(unit, answer["reply"], spans, entities)
        except (KeyError, ValueError) as error:
            failed.append(unit["unit_id"])
            print(f"{args.judge}: unit {len(failed)} not usable: {str(error)[:120]}", file=sys.stderr)
            continue
        entry.update({k: unit[k] for k in ("binding_sha256", "image_sha256", "hypothesis_sha256")})
        review[unit["unit_id"]] = entry
        totals = {k: totals[k] + counts[k] for k in totals}
    document = {"schema_version": REVIEW_SCHEMA_VERSION, "packet_id": packet_id,
                "packet_sha256": packet["packet_sha256"], "reviewer": REVIEWER[args.judge], "draft": bool(failed),
                "units": review, "model_review": {"judge": args.judge, "config": JUDGES[args.judge][1],
                "instructions_sha256": sha256(INSTRUCTIONS.read_text(encoding="utf-8")),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "mapping": totals,
                "failed_units": len(failed)}}
    args.out.write_text(json_text(document), encoding="utf-8")
    print(f"{args.judge}: wrote {len(review)}/{len(units)} units, mapping {totals}", file=sys.stderr)
    return 1 if failed else 0


def clean_line(line: str) -> str:
    return " ".join(line.replace("⟦", "").replace("⟧", "").split())


def command_probes(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    pages = sorted(p.stem for p in (ROOT / "data/dev_silver/gt").glob("*.txt"))
    rng.shuffle(pages)
    kinds = ["clean"] * 8 + ["planted"] * 8 + ["misread"] * 8
    sentences = list(PLANTED)
    rng.shuffle(sentences)
    probes = []
    for page, kind in zip(pages, kinds):
        lines = [clean_line(x) for x in (ROOT / f"data/dev_silver/gt/{page}.txt").read_text(encoding="utf-8").splitlines()]
        lines = [x for x in lines if x]
        reference = "\n".join(lines)
        target = None
        if kind == "planted":
            at = rng.randrange(1, len(lines))
            lines.insert(at, sentences.pop())
            target = at
        elif kind == "misread":
            at = rng.randrange(len(lines))
            chars = list(lines[at])
            for i, ch in enumerate(chars):
                if ch.lower() in LOOKALIKE and rng.random() < 0.35:
                    chars[i] = LOOKALIKE[ch.lower()]
            lines[at] = "".join(chars)
            target = at
        starts, offset = [], 0
        for line in lines:
            starts.append(offset)
            offset += len(line) + 1
        hypothesis = " ".join(lines)
        span = (starts[target], starts[target] + len(lines[target])) if target is not None else None
        probes.append({"unit_id": f"probe-{kind}-{page}", "kind": kind, "page": page,
                       "image": str(ROOT / f"data/dev_silver/pages/{page}.jpg"), "reference": reference,
                       "hypothesis_normalized": hypothesis, "line_breaks": starts[1:], "target": span,
                       "candidate_spans": [], "entity_candidates": []})
    args.out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in probes), encoding="utf-8")
    print(f"wrote {len(probes)} probes: {dict((k, kinds.count(k)) for k in set(kinds))}", file=sys.stderr)
    return 0


def command_review_probes(args: argparse.Namespace) -> int:
    probes = [json.loads(x) for x in args.probes.read_text(encoding="utf-8").splitlines() if x.strip()]
    for probe in probes:
        probe["image"] = Path(probe["image"])
    results = run_units(args.judge, probes, Path(str(args.out) + ".d"), "silver", args.workers)
    rows = []
    for probe in probes:
        answer = results.get(probe["unit_id"], {})
        try:
            entry, counts = map_reply(probe, answer["reply"], {}, {})
        except (KeyError, ValueError) as error:
            rows.append({"unit_id": probe["unit_id"], "error": str(error)[:200]})
            continue
        rows.append({"unit_id": probe["unit_id"], "added_spans": entry["added_spans"], "mapping": counts})
    args.out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return 1 if any("error" in r for r in rows) else 0


def kappa(pairs: list[tuple[str, str]]) -> dict:
    if not pairs:
        return {"n": 0}
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    labels = {x for pair in pairs for x in pair}
    expected = sum((sum(a == x for a, _ in pairs) / n) * (sum(b == x for _, b in pairs) / n) for x in labels)
    return {"n": n, "raw": round(observed, 3),
            "kappa": round((observed - expected) / (1 - expected), 3) if expected < 1 else None}


def covered(spans: list[dict], start: int, end: int) -> int:
    marks = set()
    for span in spans:
        if span["label"] == "fluent_fabrication":
            marks.update(range(max(start, span["start"]), min(end, span["end"])))
    return len(marks)


def review_labels(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for unit_id, unit in document["units"].items():
        out[unit_id] = ({x["candidate_id"]: x["label"] for x in unit["candidate_labels"]},
                        {x["candidate_id"]: x["label"] for x in unit["entity_labels"]})
    return out


def command_calibrate(args: argparse.Namespace) -> int:
    probes = {p["unit_id"]: p for p in map(json.loads, args.probes.read_text(encoding="utf-8").splitlines()) if p}
    reviews = {}
    for judge, path in (("fable", args.probe_fable), ("astra", args.probe_astra)):
        reviews[judge] = {r["unit_id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines()) if r}
    report = {"C1_planted": {}, "C2_clean": {}, "C3_misread": {}}
    for kind in ("planted", "clean", "misread"):
        units = [p for p in probes.values() if p["kind"] == kind]
        for who in ("fable", "astra", "union"):
            values = []
            for probe in units:
                rows = [reviews[j].get(probe["unit_id"], {}) for j in (("fable", "astra") if who == "union" else (who,))]
                if any("added_spans" not in r for r in rows):
                    values.append(None)
                    continue
                spans = [s for r in rows for s in r["added_spans"]]
                if kind == "clean":
                    values.append(covered(spans, 0, len(probe["hypothesis_normalized"])) / len(probe["hypothesis_normalized"]))
                else:
                    s, e = probe["target"]
                    values.append(covered(spans, s, e) / (e - s))
            done = sorted(v for v in values if v is not None)
            key = {"planted": "C1_planted", "clean": "C2_clean", "misread": "C3_misread"}[kind]
            if kind == "planted":
                report[key][who] = {"caught": sum(v >= 0.5 for v in done), "of": len(units), "missing_reviews": values.count(None)}
            elif kind == "clean":
                report[key][who] = {"median_fab_rate": round(done[len(done) // 2], 4) if done else None,
                                    "max_fab_rate": round(max(done), 4) if done else None, "missing_reviews": values.count(None)}
            else:
                report[key][who] = {"lines_mostly_fabrication": sum(v >= 0.5 for v in done), "of": len(units)}
    c1 = report["C1_planted"]
    c2 = report["C2_clean"]["union"]
    report["gate_C1"] = c1["union"]["caught"] >= 7 and c1["fable"]["caught"] >= 6 and c1["astra"]["caught"] >= 6 \
        and not any(c1[w]["missing_reviews"] for w in c1)
    report["gate_C2"] = c2["median_fab_rate"] is not None and c2["median_fab_rate"] <= 0.01 \
        and c2["max_fab_rate"] <= 0.10 and not c2["missing_reviews"]
    if args.human:
        human = review_labels(args.human)
        judges = {"fable": review_labels(args.pilot_fable), "astra": review_labels(args.pilot_astra)}
        pairs = {"fable_vs_human": (judges["fable"], human), "astra_vs_human": (judges["astra"], human),
                 "fable_vs_astra": (judges["fable"], judges["astra"])}
        report["agreement"] = {}
        for name, (a, b) in pairs.items():
            spans = [(a[u][0][c], b[u][0][c]) for u in a if u in b for c in a[u][0] if c in b[u][0]]
            entities = [(a[u][1][c], b[u][1][c]) for u in a if u in b for c in a[u][1] if c in b[u][1]]
            fab = [(x == "fluent_fabrication", y == "fluent_fabrication") for x, y in spans]
            report["agreement"][name] = {"span_labels": kappa(spans), "entity_labels": kappa(entities),
                                         "span_fabrication_yes_no": kappa([(str(x), str(y)) for x, y in fab])}
        report["agreement"]["pilot_v1_human_pair"] = {"span_labels": {"raw": 0.45, "kappa": 0.15},
                                                      "entity_labels": {"raw": 0.03, "kappa": 0.01}}
    print(json.dumps(report, indent=2))
    return 0 if report["gate_C1"] and report["gate_C2"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review")
    review.add_argument("--pilot-dir", type=Path, required=True)
    review.add_argument("--packet-index", type=int, choices=(0, 1), required=True)
    review.add_argument("--judge", choices=sorted(JUDGES), required=True)
    review.add_argument("--reference-kind", choices=("silver", "gold"), required=True)
    review.add_argument("--out", type=Path, required=True)
    review.add_argument("--workers", type=int, default=4)
    probes = sub.add_parser("probes")
    probes.add_argument("--out", type=Path, required=True)
    probes.add_argument("--seed", default="20261106")
    review_probes = sub.add_parser("review-probes")
    review_probes.add_argument("--probes", type=Path, required=True)
    review_probes.add_argument("--judge", choices=sorted(JUDGES), required=True)
    review_probes.add_argument("--out", type=Path, required=True)
    review_probes.add_argument("--workers", type=int, default=4)
    calibrate = sub.add_parser("calibrate")
    for name in ("--probes", "--probe-fable", "--probe-astra"):
        calibrate.add_argument(name, type=Path, required=True)
    for name in ("--human", "--pilot-fable", "--pilot-astra"):
        calibrate.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        return {"review": command_review, "probes": command_probes, "review-probes": command_review_probes,
                "calibrate": command_calibrate}[args.command](args)
    except EngineUnavailable as error:
        print(f"model unavailable (usage limit or login?): {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
