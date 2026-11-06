// Resolver DOM layer.  State and checks live in pilot_resolver_core.js.  The
// page asks one question at a time, in the words the reviewers saw: the scan
// stays put on the left, the two answers sit side by side on the right.
(() => {
  'use strict';
  const bundle = JSON.parse(document.getElementById('bundle-data').textContent);
  const ui = JSON.parse(document.getElementById('ui-config').textContent);
  const siteNode = document.getElementById('site-config');
  const hosted = Boolean((siteNode ? JSON.parse(siteNode.textContent) : {}).hosted);
  const core = globalThis.createResolverCore(bundle, ui);
  const {units, state, chars, sliceText} = core;
  const $ = (id) => document.getElementById(id);
  const root = $('unit');
  const resolverInput = $('resolver');
  const storageKey = 'pilot-resolver:' + bundle.bundle_id;
  const storage = (() => { try { return globalThis.localStorage || null; } catch (caught) { return null; } })();

  // Answers in the reviewers' own words.
  const SPAN_WORDS = {};
  ui.spanLabels.forEach((item) => {
    SPAN_WORDS[item.id] = item.answer === 'ja' ? 'Steht so im Scan' : item.answer === 'nein' ? 'Nein: ' + item.name : item.name;
  });
  const ENTITY_WORDS = {};
  ui.entityLabels.forEach((item) => { ENTITY_WORDS[item.id] = item.name; });
  const kindName = (id) => (ui.entityKinds.find((x) => x.id === id) || {name: id || ''}).name;
  const words = (entity, label) => (label ? (entity ? ENTITY_WORDS : SPAN_WORDS)[label] || label : 'keine Antwort');

  let unitIndex = 0;
  const cursor = {};
  let view = {};
  let zoom = 1;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function button(text, className, onClick) {
    const node = el('button', className, text);
    node.type = 'button';
    node.addEventListener('click', onClick);
    return node;
  }
  const setError = (text) => { $('error').textContent = text || ''; };
  const setNotice = (text) => { $('notice').textContent = text || ''; };

  // --- what needs deciding --------------------------------------------------
  function decisionsOf(unit) {
    const openSpans = new Set(core.disagreeing(unit, 'candidate_labels', unit.candidate_spans));
    const openEntities = new Set(core.disagreeing(unit, 'entity_labels', unit.entity_candidates));
    const ordered = unit.candidate_spans.slice().sort((x, y) => x.start - y.start);
    const spans = ordered.map((c, n) => ({type: 'span', candidate: c, number: n + 1, at: c.start})).filter((d) => openSpans.has(d.candidate.id));
    core.pairs(unit, false).forEach((pair, index) => { if (!pair.boundaryLocked) spans.push({type: 'added', entity: false, index, pair, at: (pair.a || pair.b).start}); });
    const entities = unit.entity_candidates.filter((c) => openEntities.has(c.id)).map((c) => ({type: 'entity', candidate: c, at: c.start}));
    core.pairs(unit, true).forEach((pair, index) => { if (!pair.boundaryLocked) entities.push({type: 'added', entity: true, index, pair, at: (pair.a || pair.b).start}); });
    const byPlace = (x, y) => x.at - y.at;
    return spans.sort(byPlace).concat(entities.sort(byPlace));
  }
  function claimOf(unit, d) { const us = state.units[unit.unit_id]; return (d.entity ? us.manualEntities : us.manualSpans)[d.index]; }
  function claimProblems(unit, d) {
    const prefix = (d.entity ? 'Added entity ' : 'Added span ') + (d.index + 1) + ': ';
    return core.unitProblems(unit.unit_id).filter((p) => p.startsWith(prefix)).map((p) => p.slice(prefix.length));
  }
  function isDone(unit, d) {
    const us = state.units[unit.unit_id];
    if (d.type === 'span') return Boolean(us.spans[d.candidate.id]);
    if (d.type === 'entity') return Boolean(us.entities[d.candidate.id]);
    return claimProblems(unit, d).length === 0;
  }

  // --- text -------------------------------------------------------------------
  // The engine's line breaks: a line-ending space becomes a newline (same
  // length), a dehyphenated join becomes a <br> (no text).
  function appendText(target, unit, from, to) {
    const cs = chars(unit);
    const breaks = new Set(unit.line_breaks || []);
    let text = '';
    for (let index = from; index < to; index += 1) {
      if (index > from && breaks.has(index) && cs[index - 1] !== ' ') { target.appendChild(document.createTextNode(text)); target.appendChild(el('br')); text = ''; }
      text += cs[index] === ' ' && breaks.has(index + 1) ? '\n' : cs[index];
    }
    target.appendChild(document.createTextNode(text));
    return target;
  }
  // A stretch of text with marked ranges; `marks` are {start, end, className}.
  function markedText(unit, from, to, marks) {
    const box = el('div', 'passage');
    const cuts = new Set([from, to]);
    marks.forEach((m) => { cuts.add(Math.max(from, Math.min(to, m.start))); cuts.add(Math.max(from, Math.min(to, m.end))); });
    const points = [...cuts].sort((x, y) => x - y);
    if (from > 0) box.appendChild(document.createTextNode('… '));
    for (let i = 0; i < points.length - 1; i += 1) {
      const [a, b] = [points[i], points[i + 1]];
      const classes = marks.filter((m) => m.start <= a && m.end >= b).map((m) => m.className);
      appendText(box.appendChild(classes.length ? el('mark', classes.join(' ')) : el('span')), unit, a, b);
    }
    if (to < chars(unit).length) box.appendChild(document.createTextNode(' …'));
    return box;
  }
  function around(unit, start, end, context) {
    const cs = chars(unit);
    let from = Math.max(0, start - context);
    while (from > 0 && cs[from - 1] !== ' ') from -= 1;
    let to = Math.min(cs.length, end + context);
    while (to < cs.length && cs[to] !== ' ') to += 1;
    return [from, to];
  }
  function selectionIn(box) {
    const win = typeof window === 'undefined' ? null : window;
    const selection = win && win.getSelection ? win.getSelection() : null;
    if (!box || !selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0);
    if (!box.contains(range.startContainer) || !box.contains(range.endContainer)) return null;
    const before = document.createRange();
    before.selectNodeContents(box);
    before.setEnd(range.startContainer, range.startOffset);
    const cp = (text) => Array.from(text).length;
    const text = range.toString();
    const lead = text.length - text.replace(/^\s+/, '').length;
    const trail = text.length - text.replace(/\s+$/, '').length;
    const start = cp(before.toString().replace(/^… /, '')) + cp(text.slice(0, lead)) + Number(box.dataset.from || 0);
    const end = start + cp(text.slice(lead, text.length - trail));
    return end > start ? {start, end} : null;
  }

  // --- the choice -------------------------------------------------------------
  // A and B as two large buttons with each reviewer's answer, then the full
  // answer set behind "Etwas anderes entscheiden".
  function verdict(entity, a, b, chosen, onPick, extra) {
    const box = el('div', 'verdict');
    const pair = box.appendChild(el('div', 'verdict-pair'));
    [['a', 'A', a], ['b', 'B', b]].forEach(([side, name, item]) => {
      if (!item) return;
      const node = button('', 'pick pick-' + side + (chosen && chosen === item.label ? ' chosen' : ''), () => onPick(item.label));
      node.dataset.side = side;
      node.appendChild(el('span', 'pick-who', 'Prüfer ' + name + ' sagt'));
      node.appendChild(el('span', 'pick-what', words(entity, item.label)));
      if (item.note) node.appendChild(el('span', 'pick-note', item.note));
      pair.appendChild(node);
    });
    (extra || []).forEach((item) => {
      const node = button('', 'pick pick-other' + (chosen === item.label ? ' chosen' : ''), () => onPick(item.label));
      node.appendChild(el('span', 'pick-who', item.who));
      node.appendChild(el('span', 'pick-what', words(entity, item.label)));
      pair.appendChild(node);
    });
    const shown = [a, b, ...(extra || [])].filter(Boolean).map((item) => item.label);
    const other = box.appendChild(el('details', 'other'));
    other.open = Boolean(chosen) && !shown.includes(chosen);
    other.appendChild(el('summary', '', 'Etwas anderes entscheiden'));
    const options = entity ? ui.entityLabels : ui.spanLabels;
    const groups = entity ? [['', options]] : [
      ['Steht so im Scan?', options.filter((o) => o.answer !== 'nein')],
      ['Nein, weil …', options.filter((o) => o.answer === 'nein')],
    ];
    groups.forEach(([title, list]) => {
      if (title) other.appendChild(el('p', 'other-title', title));
      const chips = other.appendChild(el('div', 'chips'));
      list.forEach((option) => {
        const chip = button('', 'chip' + (chosen === option.id ? ' chosen' : ''), () => onPick(option.id));
        chip.dataset.label = option.id;
        chip.appendChild(el('span', 'chip-name', option.answer === 'ja' && !entity ? 'Ja, steht so im Scan' : option.name));
        if (option.help) chip.appendChild(el('span', 'chip-help', option.help));
        chips.appendChild(chip);
      });
    });
    if (chosen) box.appendChild(el('p', 'decided', 'Entschieden: ' + words(entity, chosen)));
    return box;
  }
  function noteOf(review, id) {
    const note = (review.notes || []).find((item) => item.candidate_id === id);
    if (!note) return '';
    return (note.mixed ? 'Hat „Teils“ geantwortet' : '') + (note.text ? (note.mixed ? ': ' : 'Anmerkung: ') + note.text : '');
  }

  function renderSimple(unit, d, card) {
    const us = state.units[unit.unit_id];
    const entity = d.type === 'entity';
    const c = d.candidate;
    const store = entity ? us.entities : us.spans;
    const field = entity ? 'entity_labels' : 'candidate_labels';
    card.appendChild(el('h3', 'card-title', entity ? '„' + c.text + '“ (' + kindName(c.kind) + ')' : 'Gelbe Stelle ' + d.number));
    const [from, to] = around(unit, c.start, c.end, entity ? 40 : 80);
    card.appendChild(markedText(unit, from, to, [{start: c.start, end: c.end, className: 'here'}]));
    card.appendChild(el('p', 'question', entity ? 'Steht dieser Name, Ort, dieses Datum oder dieser Betrag an dieser Stelle im Scan?' : 'Steht das so im Scan?'));
    const [ra, rb] = unit.reviews;
    card.appendChild(verdict(entity,
      {label: ra[field][c.id], note: entity ? '' : noteOf(ra, c.id)},
      {label: rb[field][c.id], note: entity ? '' : noteOf(rb, c.id)},
      store[c.id], (label) => { store[c.id] = label; changed(true); }));
  }

  function renderAdded(unit, d, card) {
    const {pair, entity} = d;
    const claim = claimOf(unit, d);
    card.appendChild(el('h3', 'card-title', entity ? 'Von Prüfern eingetragene Angabe' : 'Von Prüfern eingetragene Stelle'));
    card.appendChild(el('p', 'lead', pair.a && pair.b
      ? 'Beide haben hier etwas eingetragen, aber nicht gleich.'
      : 'Nur Prüfer ' + (pair.a ? 'A' : 'B') + ' hat hier etwas eingetragen. Prüfen Sie, ob es stimmt.'));
    const refs = [pair.a, pair.b].filter(Boolean);
    const lo = Math.min(...refs.map((r) => r.start));
    const hi = Math.max(...refs.map((r) => r.end));
    const [from, to] = around(unit, lo, hi, 50);
    const marks = [];
    if (pair.a) marks.push({start: pair.a.start, end: pair.a.end, className: 'range-a'});
    if (pair.b) marks.push({start: pair.b.start, end: pair.b.end, className: 'range-b'});
    const valid = Number.isInteger(claim.start) && Number.isInteger(claim.end) && claim.start < claim.end;
    if (valid) marks.push({start: claim.start, end: claim.end, className: 'range-chosen'});
    const passage = card.appendChild(markedText(unit, from, to, marks));
    passage.dataset.from = String(from);

    const step1 = card.appendChild(el('div', 'step'));
    step1.appendChild(el('p', 'question', '1. Welche Textstelle ist gemeint?'));
    const bounds = step1.appendChild(el('div', 'verdict-pair'));
    const useRange = (item) => { claim.start = item.start; claim.end = item.end; if (entity && item.kind && !claim.kind) claim.kind = item.kind; changed(false); };
    [['a', 'A', pair.a], ['b', 'B', pair.b]].forEach(([side, name, item]) => {
      if (!item) return;
      const same = valid && claim.start === item.start && claim.end === item.end;
      const node = button('', 'pick pick-' + side + ' use-' + side + (same ? ' chosen' : ''), () => useRange(item));
      node.appendChild(el('span', 'pick-who', 'Markierung von ' + name));
      node.appendChild(el('span', 'pick-what', '„' + sliceText(unit, item.start, item.end) + '“'));
      bounds.appendChild(node);
    });
    const own = step1.appendChild(el('p', 'own'));
    own.appendChild(document.createTextNode('Andere Grenze: Markieren Sie den Text oben mit der Maus. '));
    own.appendChild(button('Markierten Text übernehmen', 'quiet use-selection', () => {
      const offsets = selectionIn(passage);
      if (!offsets) { setError('Markieren Sie zuerst Text im Ausschnitt dieser Frage.'); return; }
      setError('');
      useRange(offsets);
    }));
    step1.appendChild(el('p', 'decided', valid ? 'Gewählt: „' + sliceText(unit, claim.start, claim.end) + '“' : 'Noch keine Grenze gewählt.'));

    if (entity) {
      const step = card.appendChild(el('div', 'step'));
      step.appendChild(el('p', 'question', '2. Was für eine Angabe ist das?'));
      const chips = step.appendChild(el('div', 'chips'));
      ui.entityKinds.forEach((kind) => {
        const chip = button(kind.name, 'chip kind' + (claim.kind === kind.id ? ' chosen' : ''), () => { claim.kind = kind.id; changed(false); });
        chip.dataset.kind = kind.id;
        chips.appendChild(chip);
      });
    }

    const step3 = card.appendChild(el('div', 'step'));
    step3.appendChild(el('p', 'question', (entity ? '3. Steht die Angabe so im Scan?' : '2. Steht das so im Scan?')));
    if (pair.labelLocked) {
      step3.appendChild(el('p', 'locked', 'Beide sagen: ' + words(entity, pair.a.label) + '. Das bleibt so.'));
    } else {
      // A one-sided claim can be rejected: the span is supported, the entity
      // is no entity.  The scorer keeps the claim either way.
      const reject = pair.a && pair.b ? [] : [{who: 'Stimmt nicht', label: entity ? 'not_entity' : 'supported'}];
      step3.appendChild(verdict(entity, pair.a && {label: pair.a.label}, pair.b && {label: pair.b.label}, claim.label,
        (label) => { claim.label = label; changed(false); }, reject));
    }
    const plain = {
      'the boundary must overlap every reviewer proposal': 'Die Grenze muss beide Markierungen berühren.',
      'the boundary overlaps an automatic candidate': 'Die Grenze überschneidet eine gelbe Stelle. Wählen Sie eine kürzere Grenze.',
      'the boundary overlaps another added claim': 'Die Grenze überschneidet eine andere eingetragene Stelle.',
    };
    claimProblems(unit, d).filter((p) => plain[p]).forEach((p) => card.appendChild(el('p', 'problem', plain[p])));
  }

  // --- layout -----------------------------------------------------------------
  function renderStrip() {
    const strip = $('unit-strip');
    strip.textContent = '';
    units.forEach((unit, index) => {
      const value = core.status(unit.unit_id);
      const node = button(String(index + 1), 'tick unit-tick ' + value + (index === unitIndex ? ' current' : ''), () => goUnit(index));
      node.title = 'Seite ' + (index + 1) + ': ' + {agreed: 'einig', open: 'offen', resolved: 'entschieden'}[value];
      strip.appendChild(node);
    });
  }
  function renderScan(unit) {
    const col = el('div', 'scan-col');
    const tools = col.appendChild(el('div', 'scan-tools'));
    const image = el('img', 'scan');
    image.src = unit.image_file;
    image.alt = 'Scan der Seite';
    const apply = () => { image.style.width = Math.round(zoom * 100) + '%'; };
    tools.appendChild(button('Kleiner', 'quiet', () => { zoom = Math.max(1, zoom / 1.5); apply(); }));
    tools.appendChild(button('Größer', 'quiet', () => { zoom = Math.min(6, zoom * 1.5); apply(); }));
    tools.appendChild(button('Ganze Seite', 'quiet', () => { zoom = 1; apply(); }));
    const open = el('a', '', 'Scan in neuem Tab');
    open.href = unit.image_file; open.target = '_blank'; open.rel = 'noopener';
    tools.appendChild(open);
    col.appendChild(el('div', 'scan-box')).appendChild(image);
    apply();
    return col;
  }
  function renderUnit() {
    root.textContent = '';
    const unit = units[unitIndex];
    const section = root.appendChild(el('section', 'unit'));
    section.dataset.unitId = unit.unit_id;
    const cols = section.appendChild(el('div', 'cols'));
    cols.appendChild(renderScan(unit));
    const work = cols.appendChild(el('div', 'work'));
    view = {work, head: work.appendChild(el('div', 'unit-head'))};
    view.text = work.appendChild(el('div', 'fulltext'));
    unit.reviews.forEach((review, i) => { if (review.unit_note) work.appendChild(el('p', 'unit-note', 'Anmerkung von Prüfer ' + 'AB'[i] + ': ' + review.unit_note)); });
    view.ticks = work.appendChild(el('nav', 'decision-strip'));
    view.card = work.appendChild(el('article', 'card'));
    view.nav = work.appendChild(el('div', 'card-nav'));
    const reference = work.appendChild(el('details', 'reference'));
    reference.appendChild(el('summary', '', (bundle.reference_source === 'gold' ? 'Abschrift eines Menschen' : 'Text eines anderen Programms') + ' ansehen. Nur zur Orientierung: Der Scan entscheidet.'));
    reference.appendChild(el('div', 'reference-text', unit.reference));
    renderDecision();
  }
  function renderDecision() {
    const unit = units[unitIndex];
    const list = decisionsOf(unit);
    const done = list.filter((d) => isDone(unit, d)).length;
    const index = Math.min(cursor[unit.unit_id] || 0, Math.max(0, list.length - 1));
    cursor[unit.unit_id] = index;
    const d = list[index];

    view.head.textContent = '';
    view.head.appendChild(el('h2', '', 'Seite ' + (unitIndex + 1) + ' von ' + units.length));
    view.head.appendChild(el('p', 'unit-state', !list.length
      ? 'Beide Prüfer sind sich hier einig. Es gibt nichts zu entscheiden.'
      : done + ' von ' + list.length + ' Fragen entschieden'));

    view.text.textContent = '';
    view.text.appendChild(el('p', 'fulltext-title', 'Ganzer Text des Programms'));
    const marks = [];
    if (d && d.candidate) marks.push({start: d.candidate.start, end: d.candidate.end, className: 'here'});
    if (d && d.type === 'added') [d.pair.a, d.pair.b].filter(Boolean).forEach((r) => marks.push({start: r.start, end: r.end, className: 'here'}));
    const full = view.text.appendChild(markedText(unit, 0, chars(unit).length, marks));
    full.className = 'passage full';
    // Scroll only the text box to the passage, never the page.
    const here = full.querySelector('mark.here');
    if (here && typeof here.offsetTop === 'number') full.scrollTop = Math.max(0, here.offsetTop - 48);

    view.ticks.textContent = '';
    list.forEach((item, i) => {
      const tick = button('', 'tick decision-tick' + (isDone(unit, item) ? ' resolved' : ' open') + (i === index ? ' current' : ''), () => { cursor[unit.unit_id] = i; renderDecision(); });
      tick.title = 'Frage ' + (i + 1) + (isDone(unit, item) ? ': entschieden' : ': offen');
      view.ticks.appendChild(tick);
    });

    view.card.textContent = '';
    if (!d) {
      view.card.className = 'card empty';
      view.card.appendChild(el('p', 'lead', 'Auf dieser Seite sind sich beide Prüfer in allem einig.'));
    } else {
      view.card.className = 'card' + (isDone(unit, d) ? ' is-done' : '');
      view.card.appendChild(el('p', 'card-count', 'Frage ' + (index + 1) + ' von ' + list.length));
      if (d.type === 'added') renderAdded(unit, d, view.card); else renderSimple(unit, d, view.card);
    }

    view.nav.textContent = '';
    const prev = view.nav.appendChild(button('‹ Vorherige Frage', 'quiet nav-prev', () => step(-1)));
    prev.disabled = index <= 0;
    if (list.length && done === list.length || !list.length) {
      const nextOpen = units.findIndex((u, i) => i !== unitIndex && core.status(u.unit_id) === 'open');
      view.nav.appendChild(nextOpen < 0
        ? el('span', 'all-done', 'Alle Seiten sind entschieden. Laden Sie unten die Auflösung herunter.')
        : button('Nächste offene Seite ›', 'primary next-unit', () => goUnit(nextOpen)));
    } else {
      const next = view.nav.appendChild(button('Nächste Frage ›', 'quiet nav-next', () => step(1)));
      next.disabled = index >= list.length - 1;
    }
    renderStrip();
    updateSummary();
  }
  function updateSummary() {
    const open = units.filter((u) => u.disagreement);
    const resolved = open.filter((u) => core.status(u.unit_id) === 'resolved').length;
    const agreed = units.length - open.length;
    $('summary').textContent = resolved + ' von ' + open.length + ' Seiten mit Uneinigkeit sind entschieden.' +
      (agreed ? ' ' + agreed + ' Seiten sind ohne Uneinigkeit und brauchen keine Entscheidung.' : '');
  }
  function step(delta) {
    const unit = units[unitIndex];
    const list = decisionsOf(unit);
    const next = (cursor[unit.unit_id] || 0) + delta;
    if (next < 0 || next >= list.length) return;
    cursor[unit.unit_id] = next;
    renderDecision();
  }
  function goUnit(index) {
    unitIndex = index;
    renderUnit();
    if (typeof window !== 'undefined' && window.scrollTo) window.scrollTo(0, 0);
  }
  // After a one-click answer, move on to the next open question.
  function changed(advance) {
    persist();
    const unit = units[unitIndex];
    if (advance) {
      const list = decisionsOf(unit);
      const from = cursor[unit.unit_id] || 0;
      const next = list.findIndex((d, i) => i > from && !isDone(unit, d));
      const any = next >= 0 ? next : list.findIndex((d) => !isDone(unit, d));
      if (any >= 0) cursor[unit.unit_id] = any;
    }
    renderDecision();
  }

  // --- saving -----------------------------------------------------------------
  let remoteTimer = null;
  function setSaveStatus(text, failed) {
    const node = $('save-status');
    node.textContent = text || '';
    node.className = 'bar-save' + (failed ? ' failed' : '');
  }
  async function request(path, method, doc) {
    const init = {method, credentials: 'same-origin', headers: {accept: 'application/json'}};
    if (doc !== undefined) { init.headers['content-type'] = 'application/json'; init.body = JSON.stringify(doc); }
    const response = await fetch(path, init);
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response;
  }
  function persist() {
    state.resolver = resolverInput.value.trim();
    if (storage) { try { storage.setItem(storageKey, JSON.stringify(core.serialize(true))); } catch (caught) { /* storage unavailable */ } }
    if (!hosted) return;
    if (remoteTimer) clearTimeout(remoteTimer);
    setSaveStatus('Wird gespeichert …');
    remoteTimer = setTimeout(async () => {
      remoteTimer = null;
      try {
        await request('/api/resolution', 'PUT', core.serialize(true));
        setSaveStatus('Gespeichert ' + new Date().toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}) + ' Uhr');
      } catch (caught) { setSaveStatus('Nicht gespeichert. Prüfen Sie die Verbindung.', true); }
    }, 1500);
  }
  function applySaved(saved) {
    core.replaceState(core.validateSaved(saved));
    if (state.resolver && !resolverInput.readOnly) resolverInput.value = state.resolver;
    // Returning resolvers know the page; first-time ones see the help open.
    if ($('howto')) $('howto').open = false;
    renderUnit();
  }
  function restoreLocal() {
    if (!storage) return;
    let raw = null;
    try { raw = storage.getItem(storageKey); } catch (caught) { return; }
    if (!raw) return;
    try { applySaved(JSON.parse(raw)); setNotice('Ihr letzter Stand ist wieder da.'); } catch (caught) { setError(caught.message || String(caught)); }
  }
  async function restoreHosted() {
    try {
      const who = await (await request('/api/whoami', 'GET')).json();
      if (who && typeof who.email === 'string' && who.email) {
        resolverInput.value = who.email;
        resolverInput.readOnly = true;
        $('resolver-row').hidden = true;
      }
    } catch (caught) { /* keep the visible field */ }
    try {
      const response = await request('/api/resolution', 'GET');
      if (response.status === 204) restoreLocal();
      else { applySaved(await response.json()); setNotice('Ihr letzter Stand ist wieder da.'); setSaveStatus('Gespeichert'); }
    } catch (caught) {
      restoreLocal();
      setSaveStatus('Nicht gespeichert. Prüfen Sie die Verbindung.', true);
    }
    state.resolver = resolverInput.value.trim();
  }
  function download() {
    setError('');
    state.resolver = resolverInput.value.trim();
    if (!state.resolver) { setError('Tragen Sie zuerst Ihr Kürzel als Schiedsperson ein.'); resolverInput.focus?.(); return false; }
    const doc = core.serialize(true);
    const blob = new Blob([JSON.stringify(doc, null, 2) + '\n'], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'resolution-' + bundle.bundle_id + '.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    const open = units.filter((u) => core.status(u.unit_id) === 'open').length;
    setNotice('Gespeichert als ' + link.download + ' im Ordner „Downloads“: ' + Object.keys(doc.units).length + ' entschiedene Seiten' +
      (open ? '. ' + open + ' Seiten sind noch offen und fehlen in der Datei.' : '.'));
    return true;
  }

  resolverInput.addEventListener('input', () => persist());
  $('export').addEventListener('click', download);
  $('load').addEventListener('click', () => $('load-file').click());
  $('load-file').addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try { applySaved(JSON.parse(reader.result)); persist(); setError(''); setNotice('Die gespeicherte Auflösung ist geöffnet.'); } catch (caught) { setError(caught.message || String(caught)); }
    };
    reader.readAsText(file);
  });
  if (document.addEventListener) {
    document.addEventListener('keydown', (event) => {
      const tag = String((event.target && event.target.tagName) || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === 'ArrowRight') step(1);
      else if (event.key === 'ArrowLeft') step(-1);
      else if (event.key === 'a' || event.key === 'b') {
        const pick = view.card && view.card.querySelector('.verdict .pick-' + event.key);
        if (pick) pick.click();
      } else return;
      if (event.preventDefault) event.preventDefault();
    });
  }
  const firstOpen = units.findIndex((u) => u.disagreement);
  unitIndex = firstOpen < 0 ? 0 : firstOpen;
  renderUnit();
  if (hosted) { $('load').hidden = true; restoreHosted(); } else { restoreLocal(); }

  globalThis.pilotResolver = {core, state, renderUnit, step, goUnit, download, persist, applySaved};
})();
