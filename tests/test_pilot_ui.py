"""Run the dependency-free German reviewer form in a small Node DOM harness."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest

from harness.adjudication_schema import ENTITY_KINDS, ENTITY_LABELS, SPAN_LABELS
from harness.pilot_html import (
    ENTITY_KIND_UI,
    ENTITY_LABEL_UI,
    SPAN_LABEL_UI,
    render_review_html,
)

FAKE_DOM = Path(__file__).parent / "fixtures" / "fake_dom.cjs"


def _packet() -> dict:
    return {
        "schema_version": "fabrication-pilot-v01",
        "packet_id": "u_packet",
        "packet_sha256": "packet-digest",
        "unit_ids": ["u_one", "u_two"],
        "units": [
            {
                "unit_id": "u_one",
                "binding_sha256": "binding-one",
                "image_sha256": "image-one",
                "hypothesis_sha256": "hyp-one",
                "image_file": "images/u_one.png",
                "hypothesis_normalized": "A😀BC",
                "silver_reference": "A BC <b>",
                "candidate_spans": [{"id": "s_one", "start": 1, "end": 2, "text": "😀"}],
                "entity_candidates": [
                    {"id": "e_one", "start": 2, "end": 4, "text": "BC", "kind": "person"}
                ],
            },
            {
                "unit_id": "u_two",
                "binding_sha256": "binding-two",
                "image_sha256": "image-two",
                "hypothesis_sha256": "hyp-two",
                "image_file": "images/u_two.png",
                "hypothesis_normalized": "second linethird end",
                "line_breaks": [7, 11, 17],
                "silver_reference": "second",
                "candidate_spans": [{"id": "s_two", "start": 0, "end": 2, "text": "se"}],
                "entity_candidates": [
                    {"id": "e_two", "start": 0, "end": 2, "text": "se", "kind": "person"}
                ],
            },
        ],
    }


def test_reviewer_wording_covers_every_schema_label() -> None:
    assert {item["id"] for item in SPAN_LABEL_UI} == set(SPAN_LABELS)
    assert {item["id"] for item in ENTITY_LABEL_UI} == set(ENTITY_LABELS)
    assert {item["id"] for item in ENTITY_KIND_UI} == set(ENTITY_KINDS)
    # The form asks about scan support: exactly one span label per plain
    # answer, the rest are reasons behind "Nein".
    span_answers = [item["answer"] for item in SPAN_LABEL_UI]
    assert span_answers.count("ja") == 1 and span_answers.count("unsicher") == 1
    assert span_answers.count("nein") == len(SPAN_LABELS) - 2
    assert {item["answer"] for item in ENTITY_LABEL_UI} == {"ja", "nein", "unsicher", "kein"}
    for item in SPAN_LABEL_UI + ENTITY_LABEL_UI:
        assert item["name"]
        if item["answer"] == "nein" and item["id"] != "fabricated":
            assert item["help"]


def test_render_is_german_and_escapes_embedded_text() -> None:
    html = render_review_html(_packet())
    assert 'lang="de"' in html
    assert "Datei für die Abgabe speichern" in html
    assert html.count("Steht das so im Scan links?") == 2
    assert "Steht der Rest so im Scan links?" in html
    assert "Teils" in html
    assert "Welches Programm" not in html
    assert "Blinded transcription review" not in html
    # Transcription text must not be able to close the JSON script element.
    assert "<b>" not in html.split('id="packet-data">', 1)[1].split("</script>", 1)[0]
    assert "\\u003cb>" in html


def test_render_hosted_flag() -> None:
    assert '<script type="application/json" id="site-config">{"hosted": false}</script>' in render_review_html(_packet())
    assert '{"hosted": true}' in render_review_html(_packet(), hosted=True)


_NODE_HARNESS = r"""
const fs = require('fs');
const vm = require('vm');

const {Element, TextNode} = require(process.argv[4]);
function makeDocument(packetJson, uiJson, siteJson) {
  const elements = {};
  for (const [id, tag] of [
    ['packet-data', 'script'], ['ui-config', 'script'], ['units', 'main'], ['reviewer', 'input'],
    ['save-draft', 'button'], ['load', 'button'], ['load-file', 'input'], ['error', 'p'],
    ['notice', 'p'], ['export', 'button'], ['progress', 'div'], ['nav-prev', 'button'],
    ['nav-next', 'button'], ['intro', 'details'], ['site-config', 'script'], ['save-status', 'div'],
    ['finish-help', 'p'], ['advanced', 'details'], ['reviewer-row', 'p'],
  ]) {
    const element = new Element(tag);
    element.id = id;
    elements[id] = element;
  }
  elements['packet-data'].textContent = packetJson;
  elements['ui-config'].textContent = uiJson;
  elements['site-config'].textContent = siteJson;
  return {
    body: new Element('body'),
    getElementById(id) { return elements[id] || null; },
    createElement(tag) { return new Element(tag); },
    createTextNode(text) { return new TextNode(text); },
    _elements: elements,
  };
}
class FileReader { readAsText(file) { this.result = file.text; if (this.onload) this.onload(); } }
class CapturedBlob { constructor(parts) { this.content = parts.join(''); } }
function assert(condition, message) { if (!condition) throw new Error('FAILED: ' + message); }
function same(a, b, message) { assert(JSON.stringify(a) === JSON.stringify(b), message + ' — got ' + JSON.stringify(a)); }
function throws(fn, needle, message) {
  try { fn(); } catch (caught) { assert(String(caught.message).includes(needle), message + ' — got ' + caught.message); return; }
  throw new Error('FAILED: ' + message + ' (no error)');
}
function pick(scope, className, value) {
  const radio = scope.querySelectorAll('input.' + className).find((input) => input.value === value);
  assert(radio, 'radio ' + className + '=' + value + ' exists');
  radio.checked = true;
  radio.dispatchEvent('change');
  return radio;
}
function tick(box, checked) { box.checked = checked; box.dispatchEvent('change'); }

function parse(html) {
  const embedded = (id) => {
    const open = '<script type="application/json" id="' + id + '">';
    const start = html.indexOf(open) + open.length;
    return html.slice(start, html.indexOf('</script>', start));
  };
  // Every inline <script> without a type attribute, in document order (core, then UI).
  const scripts = [];
  let cursor = 0;
  while (true) {
    const start = html.indexOf('  <script>\n', cursor);
    if (start < 0) break;
    const bodyStart = start + '  <script>\n'.length;
    const end = html.indexOf('\n  </script>', bodyStart);
    scripts.push(html.slice(bodyStart, end));
    cursor = end;
  }
  if (scripts.length !== 2) throw new Error('expected core and UI scripts, found ' + scripts.length);
  return {packetJson: embedded('packet-data'), uiJson: embedded('ui-config'), siteJson: embedded('site-config'), scripts};
}
const main = parse(fs.readFileSync(process.argv[2], 'utf8'));
const {packetJson, uiJson} = main;
const packet = JSON.parse(packetJson);

const store = new Map();
const localStorage = {
  getItem(key) { return store.has(key) ? store.get(key) : null; },
  setItem(key, value) { store.set(key, String(value)); },
  removeItem(key) { store.delete(key); },
};
const blobs = [];
function boot(parsed = main, extra = {}) {
  const document = makeDocument(parsed.packetJson, parsed.uiJson, parsed.siteJson);
  const context = {
    document, localStorage, FileReader, Blob: CapturedBlob, console,
    URL: {createObjectURL(blob) { blobs.push(blob); return 'blob:captured'; }, revokeObjectURL() {}},
    ...extra,
  };
  parsed.scripts.forEach((code, index) => vm.runInNewContext(code, context, {filename: 'pilot-review-' + index + '.js'}));
  return {context, elements: document._elements, api: context.pilotReview};
}
const sectionsOf = (session) => session.elements.units.querySelectorAll('section');

// --- first session -------------------------------------------------------
const one = boot();
const {elements, api} = one;
let reviewerFocused = false;
let reviewerScrolled = false;
let errorsScrolled = false;
elements.reviewer.focus = () => { reviewerFocused = true; };
elements.reviewer.scrollIntoView = () => { reviewerScrolled = true; };
elements.error.scrollIntoView = () => { errorsScrolled = true; };
elements.export.click();
assert(blobs.length === 0 && reviewerFocused && reviewerScrolled, 'missing initials bring the reviewer back to the field without exporting');
let [first, second] = sectionsOf(one);
assert(sectionsOf(one).length === 2, 'both packet units rendered');
assert(first.hidden === false && second.hidden === true, 'only the first unit is visible');
assert(first.querySelector('.hypothesis').textContent === 'A😀BC', 'hypothesis text rendered without the CSS-drawn numbers');
assert(first.querySelector('.hypothesis mark').dataset.no === '1', 'yellow spot carries its number');
assert(first.querySelector('.hypothesis mark').className !== 'answered', 'an unanswered passage must not appear already reviewed');
assert(first.querySelector('.card.candidate-span .card-title').textContent === 'Gelbe Stelle 1', 'card names the numbered spot');
assert(elements.progress.textContent.includes('Aufgabe 1 von 2'), 'progress shows position');
same(api.unitProblems('u_one'), ['1 gelbe Stelle ohne Antwort', '1 Wort in Schritt 2 ohne Antwort', 'Beantworten Sie die Frage in Schritt 3'], 'a name candidate without an answer stays open; there is no not_entity default');
// Line breaks of the engine output: a line-ending space shows as a newline, a
// dehyphenated join as <br>; neither changes the text the offsets count.
assert(second.querySelector('.hypothesis').textContent === 'second\nlinethird\nend', 'hypothesis keeps the output line breaks');
assert(second.querySelectorAll('.hypothesis br').length === 1, 'a joined line break is drawn as <br>');
assert(second.querySelector('.card.candidate-span .quote').textContent === 'se' + 'cond\nlinethird\nend', 'context quotes keep the line breaks');
assert(first.querySelectorAll('.hypothesis br').length === 0, 'a packet without line breaks renders one line');
const reasonExamples = first.querySelectorAll('.card.candidate-span details.example');
same(reasonExamples.map((node) => node.querySelector('summary').textContent), ['Beispiel', 'Beispiel'], 'Lesefehler and Erfunden each carry one worked example');

throws(() => api.addManualSpan('u_one', 1, 2), 'enthält Text aus einer gelben Stelle', 'manual span may not overlap a candidate');
throws(() => api.addManualSpan('u_one', 3, 9), 'lässt sich nicht eintragen', 'manual span must stay inside the text');
api.addManualSpan('u_one', 3, 4);
throws(() => api.addManualSpan('u_one', 3, 4), 'schon eingetragen', 'duplicate manual span rejected');
throws(() => api.addManualEntity('u_one', 2, 3), 'enthält Text aus der Liste', 'manual entity may not overlap a candidate');
api.addManualEntity('u_one', 0, 1);
assert(first.querySelectorAll('.card.manual').length === 2, 'manual span and entity cards rendered');

elements.reviewer.value = 'reviewer-one';
elements.reviewer.dispatchEvent('input');
elements['save-draft'].click();
assert(blobs.length === 1, 'draft download created');
const draft = JSON.parse(blobs[0].content);
assert(draft.draft === true && draft.schema_version === 'fabrication-pilot-review-v01', 'draft is marked pending');
same(draft.units.u_one.added_spans, [{start: 3, end: 4, label: ''}], 'draft keeps the unanswered manual span with numeric offsets');
same(draft.units.u_one.manual_entities, [{start: 0, end: 1, kind: '', label: ''}], 'draft keeps the unanswered manual entity');
same(draft.units.u_one.entity_labels, [], 'an unanswered name is exported as unanswered, not as not_entity');

elements.export.click();
assert(blobs.length === 1, 'incomplete export creates no file');
assert(elements.error.textContent.includes('Aufgabe 1') && elements.error.textContent.includes('Aufgabe 2'), 'export names the unfinished units');
assert(errorsScrolled, 'unfinished-task errors are brought into view');

// Candidate span: Nein → reason, then switch to Ja.
const spanCard = first.querySelector('.card.candidate-span');
pick(spanCard, 'q1-choice', 'nein');
assert(api.state.units.u_one.candidateLabels.s_one === undefined, 'Nein alone leaves the label open');
assert(first.querySelector('.hypothesis mark').className !== 'answered', 'choosing Nein without a reason keeps the passage open');
assert(spanCard.querySelector('.q2').hidden === false, 'reasons appear after Nein');
pick(spanCard, 'q2-choice', 'fluent_fabrication');
assert(api.state.units.u_one.candidateLabels.s_one === 'fluent_fabrication', 'reason sets the schema label');
pick(spanCard, 'q1-choice', 'ja');
assert(api.state.units.u_one.candidateLabels.s_one === 'supported' && spanCard.querySelector('.q2').hidden === true, 'Ja maps to supported and hides the reasons');
assert(first.querySelector('.hypothesis mark').className === 'answered', 'a completed decision marks its passage as reviewed');
pick(spanCard, 'q1-choice', 'unsicher');
assert(api.state.units.u_one.candidateLabels.s_one === 'gt_or_image_uncertain', 'Weiß nicht maps to gt_or_image_uncertain');
pick(spanCard, 'q1-choice', 'teils');
assert(api.state.units.u_one.candidateLabels.s_one === 'gt_or_image_uncertain', 'Teils keeps the schema label uncertain');
assert(spanCard.querySelector('.q2.mixed').hidden === false, 'Teils reveals the remark field');
const mixedNote = spanCard.querySelector('input.mixed-note');
mixedNote.value = 'Anfang erfunden';
mixedNote.dispatchEvent('input');
same(api.serialize(true).units.u_one.notes, [{candidate_id: 's_one', mixed: true, text: 'Anfang erfunden'}], 'Teils exports a mixed note');
pick(spanCard, 'q1-choice', 'ja');
assert(spanCard.querySelector('.q2.mixed').hidden === true, 'leaving Teils hides the remark field');

// Manual span card and manual entity card.
const [manualSpan, manualEntity] = first.querySelectorAll('.card.manual');
pick(manualSpan, 'q1-choice', 'nein');
pick(manualSpan, 'q2-choice', 'fluent_fabrication');
pick(manualEntity, 'kind-choice', 'person');
pick(manualEntity, 'entity-choice', 'ja');

// Name list: one explicit answer per word, "Kein Name, nur ein Wort" included.
same(first.querySelectorAll('.entity input.entity-choice').map((input) => input.value), ['ja', 'nein', 'kein', 'unsicher'], 'every word offers four answers');
assert(first.querySelector('.entity').textContent.includes('Kein Name, nur ein Wort'), 'the not-a-name answer is spelled out');
assert(!first.querySelector('.entity-context').open, 'word context starts folded');
pick(first.querySelector('.entity'), 'entity-choice', 'kein');
assert(api.state.units.u_one.entityLabels.e_one === 'not_entity', '"Kein Name, nur ein Wort" maps to not_entity');
pick(first.querySelector('.entity'), 'entity-choice', 'nein');
assert(api.state.units.u_one.entityLabels.e_one === 'fabricated', '"Steht nicht im Scan" maps to fabricated');

pick(first, 'rest-choice', 'found');
same(api.unitProblems('u_one'), [], 'first unit complete: found-with-entries counts as the full-text audit');
assert(api.state.units.u_one.audit === true, 'answering the rest-of-text question sets full_page_reviewed');
assert(first.querySelector('.unit-status').textContent === 'fertig', 'unit status shows done');
assert(first.querySelector('.status-line').textContent.includes('fertig'), 'status line shows done');

pick(second.querySelector('.card.candidate-span'), 'q1-choice', 'ja');
pick(second.querySelector('.entity'), 'entity-choice', 'kein');
const unitNote = second.querySelector('textarea.unit-note');
unitNote.value = 'Seite stark verblasst';
unitNote.dispatchEvent('input');
pick(second, 'rest-choice', 'found');
assert(api.unitProblems('u_two').some((p) => p.includes('Markierte Stelle eintragen')), 'found without an entry stays open');
pick(second, 'rest-choice', 'ok');
same(api.unitProblems('u_two'), [], 'the rest is fine completes the unit');
assert(elements.progress.textContent.includes('fertig: 2 von 2'), 'progress counts finished units');

elements.export.click();
assert(blobs.length === 2, 'complete export creates the file');
const final = JSON.parse(blobs[1].content);
assert(!('draft' in final), 'final export is not a draft');
assert(final.schema_version === 'fabrication-pilot-review-v01' && final.packet_id === packet.packet_id &&
  final.packet_sha256 === packet.packet_sha256 && final.reviewer === 'reviewer-one', 'final export header');
same(final.units.u_one, {
  binding_sha256: 'binding-one', image_sha256: 'image-one', hypothesis_sha256: 'hyp-one', full_page_reviewed: true,
  candidate_labels: [{candidate_id: 's_one', label: 'supported'}],
  added_spans: [{start: 3, end: 4, label: 'fluent_fabrication'}],
  entity_labels: [{candidate_id: 'e_one', label: 'fabricated'}],
  manual_entities: [{start: 0, end: 1, kind: 'person', label: 'supported'}],
  notes: [{candidate_id: 's_one', mixed: false, text: 'Anfang erfunden'}],
}, 'final export unit one matches the import schema plus the note');
assert(final.units.u_two.unit_note === 'Seite stark verblasst', 'unit remark is exported');
same(final.units.u_two.entity_labels, [{candidate_id: 'e_two', label: 'not_entity'}], 'an explicit not-a-name answer exports not_entity');
assert(elements.notice.textContent.includes('annotations-u_packet.json'), 'export names the file');

// --- autosave survives a reload ----------------------------------------------
assert(store.size === 1, 'autosave wrote one storage entry');
const two = boot();
assert(two.elements.notice.textContent.includes('ist wieder da'), 'restore is announced');
assert(two.elements.reviewer.value === 'reviewer-one', 'restore keeps the reviewer ID');
same(two.api.serialize(false).units, final.units, 'restored state exports identically');
const restoredCard = sectionsOf(two)[0].querySelector('.card.candidate-span');
assert(restoredCard.querySelectorAll('input.q1-choice').find((r) => r.value === 'ja').checked === true, 'restored answer is shown');
assert(restoredCard.querySelector('input.mixed-note').value === 'Anfang erfunden', 'restored remark is shown');
assert(sectionsOf(two)[1].querySelector('textarea.unit-note').value === 'Seite stark verblasst', 'restored unit remark is shown');
assert(sectionsOf(two)[0].querySelectorAll('.entity input.entity-choice').find((r) => r.value === 'nein').checked === true, 'restored name answer is shown');
assert(sectionsOf(two)[0].querySelectorAll('input.rest-choice').find((r) => r.value === 'found').checked === true, 'restored unit with entries shows found');
assert(sectionsOf(two)[1].querySelectorAll('input.rest-choice').find((r) => r.value === 'ok').checked === true, 'restored unit without entries shows ok');

// --- loading files -----------------------------------------------------------
function load(session, value) {
  session.elements['load-file'].dispatchEvent('change', {target: {files: [{text: JSON.stringify(value)}]}});
}
const badBinding = JSON.parse(JSON.stringify(final));
badBinding.units.u_two.binding_sha256 = 'wrong-binding';
load(two, badBinding);
assert(two.elements.error.textContent.includes('passt nicht zu diesem Formular'), 'invalid binding rejected');
same(two.api.serialize(false).units, final.units, 'failed load keeps the earlier state');

const legacy = {
  packet_id: packet.packet_id, packet_sha256: packet.packet_sha256, reviewer: 'reviewer-one',
  units: {u_one: {binding_sha256: 'binding-one', image_sha256: 'image-one', hypothesis_sha256: 'hyp-one',
    full_page_reviewed: false, candidate_labels: [{candidate_id: 's_one', label: 'perception_error'}],
    entity_labels: [], added_spans: [{start: '2', end: '4', label: ''}], manual_entities: []}},
};
load(two, legacy);
assert(!two.elements.error.textContent, 'legacy draft with string offsets loads');
const afterLegacy = two.api.serialize(true);
same(afterLegacy.units.u_one.added_spans, [{start: 2, end: 4, label: ''}], 'string offsets become numbers');
same(afterLegacy.units.u_one.candidate_labels, [{candidate_id: 's_one', label: 'perception_error'}], 'load replaces labels');
same(afterLegacy.units.u_one.entity_labels, [], 'names missing from the file stay unanswered');
assert(afterLegacy.units.u_two.full_page_reviewed === false && afterLegacy.units.u_two.candidate_labels.length === 0, 'units absent from the file are cleared');
const legacyCard = sectionsOf(two)[0].querySelector('.card.candidate-span');
assert(legacyCard.querySelectorAll('input.q1-choice').find((r) => r.value === 'nein').checked === true, 'loaded reason shows as Nein');
assert(legacyCard.querySelectorAll('input.q2-choice').find((r) => r.value === 'perception_error').checked === true, 'loaded reason is preselected');
assert(sectionsOf(two)[0].querySelectorAll('.card.manual').length === 1, 'loaded manual span is rendered');
assert(!sectionsOf(two)[0].querySelectorAll('input.rest-choice').some((r) => r.checked), 'unanswered rest question shows no choice');
assert(sectionsOf(two)[0].querySelector('.unit-status').textContent === 'offen', 'status recomputed after load');

// --- hosted mode: the server keeps the draft and takes the submission --------
(async () => {
  const hostedHtml = parse(fs.readFileSync(process.argv[3], 'utf8'));
  const calls = [];
  const submissions = [];
  let serverState = JSON.parse(JSON.stringify(final));
  let failPut = false;
  const reply = (status, value) => ({ok: status < 400, status, json: async () => value});
  async function fakeFetch(path, init = {}) {
    const method = (init.method || 'GET').toUpperCase();
    calls.push({path, method, body: init.body ? JSON.parse(init.body) : null});
    if (path === '/api/whoami' && method === 'GET') return reply(200, {email: 'reviewer@example.org', packet_id: packet.packet_id});
    if (path === '/api/state' && method === 'GET') return serverState ? reply(200, serverState) : reply(204, null);
    if (path === '/api/state' && method === 'PUT') {
      if (failPut) return reply(500, {});
      serverState = JSON.parse(init.body);
      return reply(200, {ok: true});
    }
    if (path === '/api/submit' && method === 'POST') { submissions.push(JSON.parse(init.body)); return reply(200, {ok: true, submitted_at: '2026-09-15T12:00:00Z'}); }
    return reply(404, {});
  }
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  // Page timers must not keep the test process alive after the checks.
  const pageTimeout = (fn, ms) => { const timer = setTimeout(fn, ms); timer.unref?.(); return timer; };
  const blobsBefore = blobs.length;
  const three = boot(hostedHtml, {fetch: fakeFetch, setTimeout: pageTimeout, clearTimeout});
  await sleep(20);
  assert(three.elements.export.textContent === 'Prüfung abgeben', 'hosted footer asks to submit, not to save a file');
  assert(three.elements.advanced.hidden === true, 'hosted mode hides the file transfer help');
  same(calls.map((call) => call.method + ' ' + call.path), ['GET /api/whoami', 'GET /api/state'], 'boot asks who is logged in, then for the draft');
  assert(three.elements['reviewer-row'].hidden === true && three.elements.reviewer.value === 'reviewer@example.org', 'the login replaces the Kürzel field');
  assert(three.elements.notice.textContent.includes('ist wieder da'), 'server draft is restored');
  assert(three.elements['save-status'].textContent === 'Gespeichert', 'restored state counts as saved');
  same(three.api.serialize(false).units, final.units, 'server draft restores the same state');
  const note = sectionsOf(three)[1].querySelector('textarea.unit-note');
  note.value = 'Neu vom Server';
  note.dispatchEvent('input');
  assert(!calls.some((call) => call.method === 'PUT'), 'autosave waits for a pause');
  await sleep(3300);
  const put = calls.find((call) => call.method === 'PUT');
  assert(put && put.path === '/api/state' && put.body.draft === true && put.body.packet_id === packet.packet_id, 'draft is PUT to /api/state');
  assert(put.body.units.u_two.unit_note === 'Neu vom Server', 'autosaved draft carries the change');
  assert(three.elements['save-status'].textContent.startsWith('Gespeichert ') && three.elements['save-status'].hidden === false, 'save status shows the time');
  failPut = true;
  note.value = 'Zweite Änderung';
  note.dispatchEvent('input');
  await sleep(3300);
  assert(three.elements['save-status'].textContent.includes('Nicht gespeichert') && three.elements['save-status'].className.includes('failed'), 'a failed autosave is visible');
  failPut = false;
  three.elements.export.click();
  await sleep(20);
  assert(submissions.length === 1 && !('draft' in submissions[0]) && submissions[0].reviewer === 'reviewer@example.org', 'submission posts the final export under the login identity');
  assert(submissions[0].units.u_two.unit_note === 'Zweite Änderung', 'submission carries the latest answers even after a failed autosave');
  assert(blobs.length === blobsBefore, 'hosted submission downloads nothing');
  assert(three.elements.notice.textContent.includes('abgegeben'), 'submission is confirmed on the page');
  console.log('pilot UI runtime checks passed');
})().catch((error) => { console.error(error); process.exit(1); });
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="UI runtime check needs Node.js")
def test_review_form_runtime(tmp_path: Path) -> None:
    html_path = tmp_path / "review.html"
    html_path.write_text(render_review_html(_packet()), encoding="utf-8")
    hosted_path = tmp_path / "hosted.html"
    hosted_path.write_text(render_review_html(_packet(), hosted=True), encoding="utf-8")
    harness_path = tmp_path / "pilot-ui-runtime.js"
    harness_path.write_text(_NODE_HARNESS, encoding="utf-8")
    result = subprocess.run(
        ["node", str(harness_path), str(html_path), str(hosted_path), str(FAKE_DOM)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "pilot UI runtime checks passed" in result.stdout
