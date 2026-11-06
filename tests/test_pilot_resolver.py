"""Resolve two disagreeing fixture reviews in the resolver page, then import."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml

from harness.pilot import export_pilot, import_annotations, pilot_status
from harness.pilot_resolver import write_resolver_page
from harness.pilot_types import REVIEW_SCHEMA_VERSION

FAKE_DOM = Path(__file__).parent / "fixtures" / "fake_dom.cjs"
# Normalized: "alpha beta gamma delta epsilon zeta eta theta", one line break at 23.
HYPOTHESIS = "alpha beta gamma delta\nepsilon zeta eta theta"
SPAN = {"id": "span-1", "start": 11, "end": 22, "text": "gamma delta"}
ENTITIES = [
    {"id": "ent-zeta", "start": 31, "end": 35, "text": "zeta", "kind": "person"},
    {"id": "ent-eta", "start": 36, "end": 39, "text": "eta", "kind": "place"},
]


def _unit(tmp_path: Path, page: str) -> dict:
    image = tmp_path / "identifying-scan-name.jpg"
    image.write_bytes(b"fixture-scan")
    return {
        "engine": "engine-secret",
        "page": page,
        "image_path": str(image),
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "reference": "alpha beta",
        "hypothesis": HYPOTHESIS,
        "score": {
            "review_candidate_spans_auto": [SPAN],
            "entity_risk_candidates": ENTITIES,
        },
    }


def _review(unit: dict, *, span: str, zeta: str, added: list, manual: list) -> dict:
    return {
        "binding_sha256": unit["binding_sha256"],
        "image_sha256": unit["image_sha256"],
        "hypothesis_sha256": unit["hypothesis_sha256"],
        "full_page_reviewed": True,
        "candidate_labels": [{"candidate_id": "span-1", "label": span}],
        "added_spans": added,
        "entity_labels": [
            {"candidate_id": "ent-zeta", "label": zeta},
            {"candidate_id": "ent-eta", "label": "supported"},
        ],
        "manual_entities": manual,
    }


def _reviews(pilot_dir: Path, tmp_path: Path) -> tuple[list[Path], str]:
    map_units = json.loads((pilot_dir / "coordinator/map.json").read_text())["units"]
    split_id = next(
        unit_id
        for unit_id, unit in map_units.items()
        if unit["source"]["page"] == "dev_split"
    )
    paths = []
    for index, packet_path in enumerate(sorted(pilot_dir.glob("packets/*/packet.json"))):
        packet = json.loads(packet_path.read_text())
        units = {}
        for unit in packet["units"]:
            if unit["unit_id"] != split_id:
                units[unit["unit_id"]] = _review(
                    unit, span="supported", zeta="not_entity", added=[], manual=[]
                )
            elif index == 0:
                units[unit["unit_id"]] = _review(
                    unit,
                    span="supported",
                    zeta="not_entity",
                    added=[{"start": 0, "end": 5, "label": "fluent_fabrication"}],
                    manual=[{"start": 40, "end": 45, "kind": "place", "label": "supported"}],
                )
            else:
                units[unit["unit_id"]] = _review(
                    unit,
                    span="fluent_fabrication",
                    zeta="fabricated",
                    added=[{"start": 0, "end": 10, "label": "fluent_fabrication"}],
                    manual=[],
                )
            units[unit["unit_id"]]["unit_note"] = f"note from reviewer {index + 1}"
        document = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "packet_id": packet["packet_id"],
            "packet_sha256": packet["packet_sha256"],
            "reviewer": f"reviewer-{index + 1}",
            "units": units,
        }
        path = tmp_path / f"review-{index + 1}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths, split_id


_NODE = r"""
const fs = require('fs');
const vm = require('vm');
const {Element, TextNode} = require(process.argv[4]);
const html = fs.readFileSync(process.argv[2], 'utf8');
function assert(condition, message) { if (!condition) throw new Error('FAILED: ' + message); }
const embedded = (id) => {
  const open = '<script type="application/json" id="' + id + '">';
  const start = html.indexOf(open) + open.length;
  return html.slice(start, html.indexOf('</script>', start));
};
const scripts = [];
for (let cursor = 0; ;) {
  const start = html.indexOf('  <script>\n', cursor);
  if (start < 0) break;
  const end = html.indexOf('\n  </script>', start);
  scripts.push(html.slice(start + 11, end));
  cursor = end;
}
const store = new Map();
const localStorage = {getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v))};
const blobs = [];
function boot() {
  const elements = {};
  for (const [id, tag] of [['bundle-data', 'script'], ['ui-config', 'script'], ['site-config', 'script'], ['unit', 'main'],
    ['resolver', 'input'], ['unit-strip', 'nav'], ['save-status', 'div'], ['howto', 'details'],
    ['notice', 'p'], ['error', 'p'], ['summary', 'p'], ['export', 'button'], ['load', 'button'],
    ['load-file', 'input'], ['resolver-row', 'p']]) {
    elements[id] = new Element(tag);
    elements[id].id = id;
  }
  elements['bundle-data'].textContent = embedded('bundle-data');
  elements['ui-config'].textContent = embedded('ui-config');
  elements['site-config'].textContent = embedded('site-config');
  elements.howto.open = true;
  const document = {body: new Element('body'), getElementById: (id) => elements[id] || null,
    createElement: (tag) => new Element(tag), createTextNode: (text) => new TextNode(text)};
  class Blob { constructor(parts) { this.content = parts.join(''); } }
  const context = {document, localStorage, Blob, console, setTimeout, clearTimeout,
    URL: {createObjectURL(blob) { blobs.push(blob); return 'blob:x'; }, revokeObjectURL() {}}};
  scripts.forEach((code) => vm.runInNewContext(code, context));
  return {elements, api: context.pilotResolver};
}
const choose = (node, value) => { node.value = value; node.dispatchEvent('change'); };
const bundle = JSON.parse(embedded('bundle-data'));
const split = bundle.units.filter((unit) => unit.disagreement);
assert(split.length === 1 && bundle.units.length === 2, 'one disagreeing and one agreeing unit');

const {elements, api} = boot();
const root = elements.unit;
const card = () => root.querySelector('article');
const count = () => card().querySelector('.card-count').textContent;
const next = () => root.querySelector('.card-nav .nav-next').click();
const strip = () => elements['unit-strip'].querySelectorAll('button');
assert(root.querySelector('section').dataset.unitId === split[0].unit_id, 'opens on the disagreeing unit');
assert(strip().length === 2 && strip()[0].className.includes('open') !== strip()[1].className.includes('open'), 'page strip marks the open page');
assert(root.querySelector('.passage.full').textContent === 'alpha beta gamma delta\nepsilon zeta eta theta', 'machine text keeps its line break');
assert(root.textContent.includes('Anmerkung von Prüfer A: note from reviewer 1'), 'reviewer notes shown');
assert(root.querySelectorAll('select').length === 0, 'no dropdowns');
assert(root.querySelector('.unit-state').textContent === '0 von 4 Fragen entschieden', 'four questions on this page');

// Question 1: an added span, both say "Erfunden", boundaries differ.
assert(count() === 'Frage 1 von 4' && card().textContent.includes('Beide sagen: Nein: Erfunden. Das bleibt so.'), 'agreed label of an added span is stated, not asked');
const claim = api.state.units[split[0].unit_id].manualSpans[0];
claim.start = 18; claim.end = 22;
api.step(0);
assert(card().textContent.includes('überschneidet eine gelbe Stelle') && card().textContent.includes('beide Markierungen berühren'), 'an invalid boundary is explained in plain words');
card().querySelector('button.use-b').click();
assert(card().textContent.includes('Gewählt: „alpha beta“') && card().className.includes('is-done'), 'B boundary chosen');

// Question 2: the highlighted span; neither reviewer is right.
next();
assert(count() === 'Frage 2 von 4' && card().querySelector('.pick-a .pick-what').textContent === 'Steht so im Scan' &&
  card().querySelector('.pick-b .pick-what').textContent === 'Nein: Erfunden', 'both answers in the reviewers words');
card().querySelectorAll('.chip').find((chip) => chip.dataset.label === 'perception_error').click();
assert(count() === 'Frage 3 von 4', 'an answer moves on to the next open question');

// Question 3: the disputed entity; B is right.
assert(card().textContent.includes('„zeta“') && card().querySelector('.pick-a .pick-what').textContent === 'Kein Name, nur ein Wort', 'entity question');
card().querySelector('.verdict .pick-b').click();

// Question 4: an entity only A added; it is not an entity.
assert(count() === 'Frage 4 von 4' && card().textContent.includes('Nur Prüfer A hat hier etwas eingetragen'), 'one-sided entity');
assert(card().querySelectorAll('.chip.kind').find((chip) => chip.className.includes('chosen')).dataset.kind === 'place', 'kind preset from A');
card().querySelector('.verdict .pick-other').click();
assert(root.querySelector('.unit-state').textContent === '4 von 4 Fragen entschieden', 'all decided');
assert(root.querySelector('.card-nav').textContent.includes('Alle Seiten sind entschieden'), 'tells the resolver what is left');

elements.resolver.value = 'resolver-3';
elements.resolver.dispatchEvent('input');
elements.export.click();
const doc = JSON.parse(blobs[blobs.length - 1].content);
assert(Object.keys(doc.units).length === 1 && doc.units[split[0].unit_id].resolver === 'resolver-3', 'only the resolved disagreeing unit is written');
fs.writeFileSync(process.argv[3], JSON.stringify(doc));

const again = boot();
assert(again.elements['unit-strip'].querySelectorAll('button').some((b) => b.className.includes('resolved')) && again.elements.resolver.value === 'resolver-3', 'autosaved state restores');
assert(again.elements.howto.open === false, 'help folds away for a returning resolver');
console.log('resolver runtime checks passed');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="resolver check needs Node.js")
def test_resolver_page_writes_an_importable_resolution(tmp_path: Path) -> None:
    pilot_dir = tmp_path / "pilot"
    export_pilot(
        [_unit(tmp_path, "dev_split"), _unit(tmp_path, "dev_agree")], pilot_dir
    )
    reviews, split_id = _reviews(pilot_dir, tmp_path)
    assert import_annotations(pilot_dir, reviews)["pending_units"] == [split_id]

    page = write_resolver_page(pilot_dir, reviews, tmp_path / "resolver")
    assert page["disagreeing_units"] == 1
    html = Path(page["page"]).read_text(encoding="utf-8")
    for secret in ("engine-secret", "dev_split", "identifying-scan-name", "reviewer-1"):
        assert secret not in html
    assert len(list((tmp_path / "resolver/images").iterdir())) == 2

    script = tmp_path / "resolver-runtime.js"
    script.write_text(_NODE, encoding="utf-8")
    resolution = tmp_path / "resolution.json"
    result = subprocess.run(
        ["node", str(script), page["page"], str(resolution), str(FAKE_DOM)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    # The agreeing unit was written by the first import; re-importing it
    # unchanged is allowed, overwriting it with different content is not.
    imported = import_annotations(
        pilot_dir, reviews, resolutions=resolution, allow_existing=True
    )
    assert imported["status"] == "complete", imported["units"]
    forms = {
        path.stem: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in (pilot_dir / "coordinator/adjudications/engine-secret").glob("*.yml")
    }
    assert forms["dev_agree"]["resolver"] is None
    split = forms["dev_split"]
    assert split["resolver"] == "resolver-3"
    assert {(s["start"], s["end"], s["label"]) for s in split["spans"]} == {
        (11, 22, "perception_error"),
        (0, 10, "fluent_fabrication"),
    }
    assert split["manual_entities"][0]["label"] == "not_entity"
    status = pilot_status(pilot_dir)
    assert status["status"] == "complete" and not status["invalid_imports"]


def test_resolver_identity_must_differ_from_reviewers(tmp_path: Path) -> None:
    pilot_dir = tmp_path / "pilot"
    export_pilot([_unit(tmp_path, "dev_split")], pilot_dir)
    reviews, split_id = _reviews(pilot_dir, tmp_path)
    resolution = {
        "schema_version": "fabrication-pilot-resolution-v01",
        "units": {
            split_id: {
                "resolver": " Reviewer-1 ",
                "candidate_labels": [{"candidate_id": "span-1", "label": "supported"}],
                "entity_labels": [{"candidate_id": "ent-zeta", "label": "fabricated"}],
                "manual_spans": [{"start": 0, "end": 10, "label": "fluent_fabrication"}],
                "manual_entities": [
                    {"start": 40, "end": 45, "kind": "place", "label": "not_entity"}
                ],
            }
        },
    }
    path = tmp_path / "resolution.json"
    path.write_text(json.dumps(resolution), encoding="utf-8")
    result = import_annotations(pilot_dir, reviews, resolutions=path)
    assert result["status"] == "pending"
    assert "distinct" in result["units"][split_id]["reason"]
    resolution["map_sha256"] = "0" * 64
    path.write_text(json.dumps(resolution), encoding="utf-8")
    with pytest.raises(ValueError, match="different pilot map"):
        import_annotations(pilot_dir, reviews, resolutions=path)
