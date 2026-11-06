// Review-form DOM layer.  All state, validation, and the export document live in
// pilot_review_core.js; this file only renders and wires the page.  Every
// decision is asked as a plain question; the schema labels stay behind it.
(() => {
  'use strict';
  const packet = JSON.parse(document.getElementById('packet-data').textContent);
  const ui = JSON.parse(document.getElementById('ui-config').textContent);
  const siteNode = document.getElementById('site-config');
  const site = siteNode ? JSON.parse(siteNode.textContent) : {};
  // Hosted: the site worker keeps the draft and takes the submission, so
  // nothing depends on the Downloads folder or on one computer.
  const hosted = Boolean(site.hosted);
  const saveStatus = document.getElementById('save-status');
  const root = document.getElementById('units');
  const errorBox = document.getElementById('error');
  const noticeBox = document.getElementById('notice');
  const reviewerInput = document.getElementById('reviewer');
  const progressBox = document.getElementById('progress');
  const navPrev = document.getElementById('nav-prev');
  const navNext = document.getElementById('nav-next');
  const storageKey = 'pilot-review:' + packet.packet_id + ':' + packet.packet_sha256;
  const storage = (() => { try { return globalThis.localStorage || null; } catch (caught) { return null; } })();
  const kindName = (id) => (ui.entityKinds.find((item) => item.id === id) || {name: id}).name;
  const CONTEXT = 70;
  const YES_NO = [{id: 'ja', name: 'Ja'}, {id: 'nein', name: 'Nein'}, {id: 'unsicher', name: 'Weiß nicht'}];
  // Every candidate word gets one of these answers, "Kein Name, nur ein Wort"
  // included.  A word without an answer stays open (pilot v2).
  const ENTITY_CHOICES = ui.entityLabels.map((item) => ({id: item.answer, name: item.name}));
  const YES_NO_MIXED = [{id: 'ja', name: 'Ja'}, {id: 'nein', name: 'Nein'}, {id: 'teils', name: 'Teils'}, {id: 'unsicher', name: 'Weiß nicht'}];
  const spanAnswer = {};
  const spanByAnswer = {};
  ui.spanLabels.forEach((item) => { spanAnswer[item.id] = item.answer; if (item.answer !== 'nein') spanByAnswer[item.answer] = item.id; });
  const reasons = ui.spanLabels.filter((item) => item.answer === 'nein');
  const entityAnswer = {};
  const entityByAnswer = {};
  ui.entityLabels.forEach((item) => { entityAnswer[item.id] = item.answer; entityByAnswer[item.answer] = item.id; });
  const views = {};
  const restSaidYes = {};
  let radioSeq = 0;

  const core = globalThis.createPilotCore(packet, ui, {
    onManualSpans: (unitId) => renderManual(unitId),
    onManualEntities: (unitId) => renderManual(unitId),
    onChange: () => persist(),
  });
  const {units, unitById, state, chars, sliceText} = core;
  const review = (unitId) => state.units[unitId];
  const added = (unitId) => review(unitId).addedSpans.length + review(unitId).manualEntities.length;
  function problems(unitId) {
    const list = core.unitProblems(unitId);
    if (restSaidYes[unitId] && review(unitId).audit && !added(unitId)) list.push('Markieren Sie die Stelle in Schritt 3. Klicken Sie auf „Markierte Stelle eintragen“. Falls Sie nichts mehr melden möchten, wählen Sie dort „Ja“');
    return list;
  }

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
  function setError(message) { errorBox.textContent = message || ''; }
  function setNotice(message) { noticeBox.textContent = message || ''; }
  function radioGroup(options, className, current, onPick) {
    const box = el('span', 'choices');
    const name = 'r' + (radioSeq += 1);
    options.forEach((option) => {
      const label = el('label');
      const input = el('input', className);
      input.type = 'radio';
      input.name = name;
      input.value = option.id;
      input.checked = current === option.id;
      input.addEventListener('change', () => { if (input.checked) onPick(option.id); });
      label.appendChild(input);
      label.appendChild(document.createTextNode(option.name));
      if (option.help) { label.appendChild(document.createTextNode(' ')); label.appendChild(el('span', 'help', option.help)); }
      box.appendChild(label);
      if (option.example) {
        const example = el('details', 'example');
        example.appendChild(el('summary', '', 'Beispiel'));
        example.appendChild(el('p', '', option.example));
        box.appendChild(example);
      }
    });
    return box;
  }

  // Judge the whole highlighted passage.  A mixed passage (part on the page,
  // part not) is answered "Teils": the schema label stays uncertain, and the
  // mixed flag plus an optional remark travel as a note in the export.
  function spanQuestions(card, getLabel, setLabel, note) {
    const current = getLabel();
    let reason = spanAnswer[current] === 'nein' ? current : '';
    const answerOf = () => {
      const label = getLabel();
      if (!label) return '';
      return spanAnswer[label] === 'unsicher' && note && note.get().mixed ? 'teils' : spanAnswer[label];
    };
    const q1 = el('div', 'q');
    q1.appendChild(el('span', 'question', 'Steht das so im Scan links?'));
    const q2 = el('div', 'q2');
    q2.hidden = answerOf() !== 'nein';
    q2.appendChild(el('span', 'question', 'Was ist falsch? Wählen Sie einen Grund.'));
    const mixedBox = el('div', 'q2 mixed');
    mixedBox.hidden = answerOf() !== 'teils';
    if (note) {
      mixedBox.appendChild(el('span', 'question', 'Welcher Teil steht nicht im Scan links? (freiwillig)'));
      const input = el('input', 'mixed-note');
      input.type = 'text';
      input.value = note.get().text || '';
      input.addEventListener('input', () => { note.set({mixed: true, text: input.value}); persist(); });
      mixedBox.appendChild(input);
      mixedBox.appendChild(el('p', 'muted', 'Solche Stellen sehen wir uns selbst an.'));
    }
    const refresh = () => { card.className = card.className.replace(/\s*\bdone\b/, '') + (getLabel() ? ' done' : ''); persist(); };
    q2.appendChild(radioGroup(reasons, 'q2-choice', reason, (id) => { reason = id; setLabel(id); refresh(); }));
    q1.appendChild(radioGroup(note ? YES_NO_MIXED : YES_NO, 'q1-choice', answerOf(), (id) => {
      const text = note ? note.get().text : '';
      if (id === 'nein') { setLabel(reason); }
      else if (id === 'teils') { setLabel(spanByAnswer.unsicher); }
      else { setLabel(spanByAnswer[id]); }
      if (note) note.set({mixed: id === 'teils', text});
      q2.hidden = id !== 'nein';
      mixedBox.hidden = id !== 'teils';
      refresh();
    }));
    card.appendChild(q1);
    card.appendChild(q2);
    if (note) card.appendChild(mixedBox);
    card.appendChild(el('p', 'muted', note
      ? '„Teils“: Ein Teil steht so im Scan links, ein anderer Teil nicht. „Weiß nicht“: unleserlich oder unsicher.'
      : 'Unleserlich oder unsicher? Dann „Weiß nicht“.'));
  }
  function entityQuestion(target, getLabel, setLabel) {
    const q = el('div', 'q entity-q');
    q.appendChild(el('span', 'question', 'Steht das so im Scan links?'));
    const current = getLabel();
    q.appendChild(radioGroup(YES_NO, 'entity-choice', current ? entityAnswer[current] : '', (id) => { setLabel(entityByAnswer[id]); persist(); }));
    target.appendChild(q);
    return q;
  }

  // The engine's own line breaks (pilot v2), so reviewers can count lines in
  // the scan.  A space that ended a line is shown as a newline: same length,
  // so selection offsets stay exact.  A line joined by dehyphenation has no
  // character to spare and gets a <br>, which adds no text.
  const lineBreaks = {};
  units.forEach((unit) => { lineBreaks[unit.unit_id] = new Set(unit.line_breaks || []); });
  function appendText(target, unit, from, to, prefix, suffix) {
    const cs = chars(unit);
    const breaks = lineBreaks[unit.unit_id];
    let text = prefix || '';
    for (let index = from; index < to; index += 1) {
      if (index > from && breaks.has(index) && cs[index - 1] !== ' ') {
        target.appendChild(document.createTextNode(text));
        target.appendChild(el('br'));
        text = '';
      }
      text += cs[index] === ' ' && breaks.has(index + 1) ? '\n' : cs[index];
    }
    target.appendChild(document.createTextNode(text + (suffix || '')));
    return target;
  }
  function textBox(tag, className, unit, from, to, prefix, suffix) {
    return appendText(el(tag, className), unit, from, to, prefix, suffix);
  }
  // A dehyphenated line break that falls exactly on a segment edge.
  function edgeBreak(target, unit, at) {
    const cs = chars(unit);
    if (at > 0 && lineBreaks[unit.unit_id].has(at) && cs[at - 1] !== ' ') target.appendChild(el('br'));
  }

  // The passage with a little grey context on either side, cut at word edges.
  function renderContext(unit, start, end, target) {
    const cs = chars(unit);
    let from = Math.max(0, start - CONTEXT);
    while (from > 0 && cs[from - 1] !== ' ') from -= 1;
    let to = Math.min(cs.length, end + CONTEXT);
    while (to < cs.length && cs[to] !== ' ') to += 1;
    if (from > 0) target.appendChild(textBox('span', 'ctx', unit, from, start, '… '));
    else if (start > 0) target.appendChild(textBox('span', 'ctx', unit, 0, start));
    edgeBreak(target, unit, start);
    target.appendChild(textBox('mark', '', unit, start, end));
    edgeBreak(target, unit, end);
    if (to < cs.length) target.appendChild(textBox('span', 'ctx', unit, end, to, '', ' …'));
    else if (end < cs.length) target.appendChild(textBox('span', 'ctx', unit, end, cs.length));
  }
  function renderHypothesis(unit, target) {
    const cs = chars(unit);
    const marks = (unit.candidate_spans || []).slice().sort((a, b) => a.start - b.start);
    let cursor = 0;
    let edged = -1;
    const edge = (at) => { if (at !== edged) edgeBreak(target, unit, at); edged = at; };
    marks.forEach((candidate, index) => {
      if (candidate.start < cursor || candidate.end > cs.length) return;
      appendText(target, unit, cursor, candidate.start);
      edge(candidate.start);
      const mark = textBox('mark', '', unit, candidate.start, candidate.end);
      mark.dataset.candidateId = candidate.id;
      // The number is drawn by CSS (::before) so it never enters the text
      // that selection offsets are computed from.
      mark.dataset.no = String(index + 1);
      mark.title = 'Gelbe Stelle ' + (index + 1) + ': Beantworten Sie die Frage in Schritt 1.';
      target.appendChild(mark);
      edge(candidate.end);
      cursor = candidate.end;
    });
    appendText(target, unit, cursor, cs.length);
  }
  function selectionOffsets(view) {
    const win = typeof window === 'undefined' ? null : window;
    const selection = win && win.getSelection ? win.getSelection() : null;
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0);
    const box = view.hyp;
    if (!box.contains(range.startContainer) || !box.contains(range.endContainer)) return null;
    const before = document.createRange();
    before.selectNodeContents(box);
    before.setEnd(range.startContainer, range.startOffset);
    const cpLen = (text) => Array.from(text).length;
    const text = range.toString();
    const lead = text.length - text.replace(/^\s+/, '').length;
    const trail = text.length - text.replace(/\s+$/, '').length;
    const start = cpLen(before.toString()) + cpLen(text.slice(0, lead));
    const end = start + cpLen(text.slice(lead, text.length - trail));
    return end > start ? {start, end} : null;
  }
  function startReport(unitId) {
    setError('');
    const view = views[unitId];
    const offsets = selectionOffsets(view);
    if (!offsets) {
      setError('Markieren Sie zuerst die Stelle im Text bei Schritt 3 mit der Maus. Klicken Sie dann auf „Markierte Stelle eintragen“.');
      return;
    }
    view.chooser.textContent = '';
    view.chooser.hidden = false;
    view.chooser.appendChild(el('span', '', 'Sie haben „' + sliceText(unitById[unitId], offsets.start, offsets.end) + '“ markiert. Was möchten Sie eintragen? '));
    const finish = (asEntity) => {
      try {
        if (asEntity) core.addManualEntity(unitId, offsets.start, offsets.end); else core.addManualSpan(unitId, offsets.start, offsets.end);
        setNotice('Die Stelle ist eingetragen. Beantworten Sie unten die Fragen dazu.');
        view.chooser.hidden = true;
      } catch (caught) { setError(caught.message || String(caught)); }
    };
    if (!view.noRest) view.chooser.appendChild(button('Eine Textstelle', 'choose-span', () => finish(false)));
    view.chooser.appendChild(button('Eine Angabe: Name, Ort, Datum, Betrag, Nummer oder Kennzeichen', 'choose-entity', () => finish(true)));
    view.chooser.appendChild(button('Abbrechen', 'small', () => { view.chooser.hidden = true; }));
  }

  function renderManual(unitId) {
    const unit = unitById[unitId];
    const box = views[unitId].manualBox;
    box.textContent = '';
    review(unitId).addedSpans.forEach((item) => {
      const card = el('div', 'card manual manual-span');
      card.appendChild(el('div', 'card-title', 'Von Ihnen eingetragen'));
      const quote = el('div', 'quote');
      renderContext(unit, item.start, item.end, quote);
      card.appendChild(quote);
      spanQuestions(card, () => item.label, (label) => { item.label = label; });
      const actions = el('div', 'actions');
      actions.appendChild(button('Entfernen', 'small', () => core.removeManualSpan(unitId, item)));
      card.appendChild(actions);
      box.appendChild(card);
    });
    review(unitId).manualEntities.forEach((item) => {
      const card = el('div', 'card manual manual-entity');
      card.appendChild(el('div', 'card-title', 'Von Ihnen eingetragen'));
      card.appendChild(textBox('div', 'quote', unit, item.start, item.end));
      const kind = el('div', 'q');
      kind.appendChild(el('span', 'question', 'Was für eine Angabe ist das?'));
      kind.appendChild(radioGroup(ui.entityKinds, 'kind-choice', item.kind, (id) => { item.kind = id; persist(); }));
      card.appendChild(kind);
      entityQuestion(card, () => item.label, (label) => { item.label = label; });
      const actions = el('div', 'actions');
      actions.appendChild(button('Entfernen', 'small', () => core.removeManualEntity(unitId, item)));
      card.appendChild(actions);
      box.appendChild(card);
    });
  }
  // One row of answers per candidate word.  Every word needs an answer;
  // "Kein Name, nur ein Wort" (not_entity) is one of them, never a default.
  function entityItem(unitId, candidate) {
    const labels = () => review(unitId).entityLabels;
    const item = el('div', 'entity');
    const head = el('div', 'entity-word');
    head.appendChild(el('strong', '', candidate.text));
    head.appendChild(document.createTextNode(' '));
    head.appendChild(el('span', 'kind', '(' + kindName(candidate.kind) + ')'));
    item.appendChild(head);
    const q = el('div', 'q entity-q');
    q.appendChild(el('span', 'question', 'Steht das an dieser Stelle im Scan links?'));
    const refresh = () => { item.className = labels()[candidate.id] ? 'entity checked' : 'entity'; };
    const current = labels()[candidate.id];
    q.appendChild(radioGroup(ENTITY_CHOICES, 'entity-choice', current ? entityAnswer[current] : '', (id) => {
      labels()[candidate.id] = entityByAnswer[id];
      refresh();
      persist();
    }));
    item.appendChild(q);
    const context = el('details', 'entity-context');
    context.appendChild(el('summary', '', 'Text davor und danach ansehen'));
    const quote = el('div', 'quote');
    renderContext(unitById[unitId], candidate.start, candidate.end, quote);
    context.appendChild(quote);
    item.appendChild(context);
    refresh();
    return item;
  }

  function updateUnitStatus(unitId) {
    const view = views[unitId];
    view.hyp.querySelectorAll('mark').forEach((mark) => {
      const answered = Boolean(review(unitId).candidateLabels[mark.dataset.candidateId]);
      mark.className = answered ? 'answered' : '';
      mark.title = 'Gelbe Stelle ' + mark.dataset.no + (answered ? ': in Schritt 1 beantwortet.' : ': in Schritt 1 noch offen.');
    });
    const list = problems(unitId);
    view.status.textContent = list.length ? 'offen' : 'fertig';
    view.status.className = list.length ? 'unit-status' : 'unit-status done';
    view.statusLine.textContent = '';
    view.statusLine.appendChild(list.length
      ? el('span', 'problems', 'Noch offen: ' + list.join('; ') + '.')
      : el('span', 'ok', 'Diese Aufgabe ist fertig.'));
  }
  function updateProgress() {
    const done = units.filter((unit) => problems(unit.unit_id).length === 0).length;
    progressBox.textContent = 'Aufgabe ' + (state.current + 1) + ' von ' + units.length + ' · fertig: ' + done + ' von ' + units.length;
    navPrev.disabled = state.current <= 0;
    navNext.textContent = state.current >= units.length - 1 ? 'Zur Abgabe ↓' : 'Nächste Aufgabe ›';
  }
  function showUnit(index) {
    if (index < 0 || index >= units.length) return;
    state.current = index;
    units.forEach((unit, position) => { views[unit.unit_id].section.hidden = position !== index; });
    updateProgress();
    if (typeof window !== 'undefined' && window.scrollTo) window.scrollTo(0, 0);
  }

  function renderScanColumn(unit) {
    const scanCol = el('div', 'scan-col');
    scanCol.appendChild(el('h3', 'column-title', 'Scan: Schauen Sie hier nach.'));
    const tools = el('div', 'scan-tools');
    const image = el('img', 'scan');
    image.src = unit.image_file;
    image.alt = 'Scan der Seite';
    let zoom = 1;
    const applyZoom = () => { if (image.style) image.style.width = Math.round(zoom * 100) + '%'; };
    tools.appendChild(button('Kleiner', 'small', () => { zoom = Math.max(1, zoom / 1.5); applyZoom(); }));
    tools.appendChild(button('Größer', 'small', () => { zoom = Math.min(6, zoom * 1.5); applyZoom(); }));
    tools.appendChild(button('Ganze Seite', 'small', () => { zoom = 1; applyZoom(); }));
    if (!String(unit.image_file).startsWith('data:')) {
      // Single-file packets embed the scan; browsers refuse to open data: URLs in a tab.
      const open = el('a', '', 'Scan einzeln öffnen');
      open.href = unit.image_file; open.target = '_blank'; open.rel = 'noopener';
      tools.appendChild(open);
    }
    scanCol.appendChild(tools);
    const box = el('div', 'scan-box');
    box.appendChild(image);
    scanCol.appendChild(box);
    return scanCol;
  }
  function step(parent, title, lead) {
    const box = el('div', 'step');
    box.appendChild(el('h3', '', title));
    if (lead) box.appendChild(el('p', 'lead', lead));
    parent.appendChild(box);
    return box;
  }

  function renderUnit(unit, index) {
    const unitId = unit.unit_id;
    const section = el('section', 'unit');
    section.dataset.unitId = unitId;
    const view = {section};
    views[unitId] = view;

    const head = el('div', 'unit-head');
    head.appendChild(el('h2', '', 'Aufgabe ' + (index + 1) + ' von ' + units.length));
    view.status = el('span', 'unit-status', 'offen');
    head.appendChild(view.status);
    section.appendChild(head);

    const cols = el('div', 'cols');
    section.appendChild(cols);
    cols.appendChild(renderScanColumn(unit));
    const work = el('div', 'work-col');
    cols.appendChild(work);
    work.appendChild(el('h3', 'column-title', 'Text des Programms: Prüfen Sie hier.'));

    const spans = (unit.candidate_spans || []).slice().sort((a, b) => a.start - b.start);
    const step1 = step(work, 'Schritt 1: Gelbe Stellen (' + spans.length + ')', spans.length
      ? 'Vergleichen Sie jede gelbe Stelle mit dem Scan links. Klicken Sie eine Antwort an. Bei „Nein“ wählen Sie einen Grund. Gelb bedeutet nicht, dass die Stelle falsch ist. Der graue Text davor und danach hilft Ihnen, die Stelle im Scan links zu finden. Auch eigene Sätze des Programms wie „Hier ist die Abschrift …“ gehören zum Text, den Sie prüfen.'
      : 'Hier gibt es keine gelben Stellen. Gehen Sie zu Schritt 2.');
    spans.forEach((candidate, number) => {
      const card = el('div', 'card candidate-span');
      card.dataset.candidateId = candidate.id;
      card.appendChild(el('div', 'card-title', 'Gelbe Stelle ' + (number + 1)));
      const quote = el('div', 'quote');
      renderContext(unit, candidate.start, candidate.end, quote);
      card.appendChild(quote);
      spanQuestions(card, () => review(unitId).candidateLabels[candidate.id] || '', (label) => {
        if (label) review(unitId).candidateLabels[candidate.id] = label; else delete review(unitId).candidateLabels[candidate.id];
      }, {
        get: () => review(unitId).notes[candidate.id] || {mixed: false, text: ''},
        set: (value) => { review(unitId).notes[candidate.id] = value; },
      });
      step1.appendChild(card);
    });

    const entities = unit.entity_candidates || [];
    const step2 = step(work, 'Schritt 2: Namen, Orte, Daten, Beträge (' + entities.length + ')', entities.length
      ? 'Das Programm hält diese Wörter für Namen, Orte, Daten oder Beträge. Oft ist es nur ein gewöhnliches Wort. Jedes Wort bekommt eine Antwort. Ist das Wort kein Name, Ort, Datum, Betrag, keine Nummer und kein Kennzeichen, wie „Haus“? Dann „Kein Name, nur ein Wort“. Das gilt auch für ein Bruchstück eines gewöhnlichen Wortes und für zusammengezogene gewöhnliche Wörter, selbst wenn die Buchstaben stimmen. Sonst prüfen Sie: Steht der Name, der Ort, das Datum oder der Betrag genau so an dieser Stelle im Scan links, Buchstabe für Buchstabe? Dann „Steht so im Scan“. Weicht er ab, auch nur um einen Buchstaben? Oder steht dort gar keiner? Dann „Steht nicht im Scan“.'
      : 'Hier gibt es keine Liste. Gehen Sie zu Schritt 3.');
    const list = el('div', 'entity-list');
    entities.forEach((candidate) => list.appendChild(entityItem(unitId, candidate)));
    step2.appendChild(list);

    const covered = spans.reduce((sum, c) => sum + (c.end - c.start), 0);
    view.noRest = covered >= chars(unit).length;
    const step3 = step(work, 'Schritt 3: Der Rest des Textes', view.noRest
      ? 'Hier steht der ganze Text des Programms. Alle Textstellen stehen schon in Schritt 1. Für gelbe Stellen fehlt dort noch eine Antwort. Graue Stellen haben Sie dort schon beantwortet. Prüfen Sie noch, ob in der Liste in Schritt 2 eine Angabe fehlt. Vergleichen Sie dazu den Text mit dem Scan links. Hier können Sie nur eine fehlende Angabe eintragen. Antworten Sie erst unten, wenn Sie alles geprüft haben.'
      : 'Hier steht der ganze Text des Programms. Graue Stellen haben Sie in Schritt 1 schon beantwortet. Für gelbe Stellen fehlt dort noch eine Antwort. Vergleichen Sie den Text ohne Farbe mit dem Scan links. Auch falsch gelesener Text zählt, nicht nur fehlende oder zusätzliche Zeilen. Steht etwas nicht so im Scan? Dann antworten Sie unten mit „Nein“ und markieren die Stelle. Ein langer falscher Abschnitt kann eine einzige Stelle sein. Prüfen Sie auch, ob in der Liste in Schritt 2 eine Angabe fehlt. Sie müssen keine fehlenden Zeilen abschreiben.');
    view.hyp = el('div', 'text hypothesis');
    renderHypothesis(unit, view.hyp);
    step3.appendChild(view.hyp);
    const restQ = el('div', 'q rest');
    restQ.appendChild(el('span', 'question', 'Steht der Rest so im Scan links?'));
    view.restChoices = el('div', 'rest-choices');
    restQ.appendChild(view.restChoices);
    step3.appendChild(restQ);
    view.reportBox = el('div', 'missing');
    view.reportBox.hidden = true;
    view.reportBox.appendChild(el('p', 'lead', 'Ziehen Sie mit gedrückter Maustaste über die Stelle im Text direkt über dieser Frage. Klicken Sie dann auf „Markierte Stelle eintragen“.'));
    view.reportBox.appendChild(button('Markierte Stelle eintragen', 'report', () => startReport(unitId)));
    view.chooser = el('div', 'chooser');
    view.chooser.hidden = true;
    view.reportBox.appendChild(view.chooser);
    step3.appendChild(view.reportBox);
    view.manualBox = el('div', 'manual');
    step3.appendChild(view.manualBox);
    renderRestChoices(unitId);
    const noteBox = el('div', 'q note');
    noteBox.appendChild(el('span', 'question', 'Möchten Sie uns zu dieser Aufgabe etwas sagen? (freiwillig)'));
    const remark = el('textarea', 'unit-note');
    remark.value = review(unitId).unitNote || '';
    remark.addEventListener('input', () => { review(unitId).unitNote = remark.value; persist(); });
    noteBox.appendChild(remark);
    step3.appendChild(noteBox);
    const reference = el('details', 'reference');
    reference.appendChild(el('summary', '', packet.reference_source === 'gold'
      ? 'Abschrift eines Menschen ansehen. Auch sie kann Fehler haben. Vergleichen Sie immer mit dem Scan links.'
      : 'Text eines anderen Programms ansehen. Er kann auch falsch sein. Vergleichen Sie immer mit dem Scan links.'));
    reference.appendChild(el('div', 'text', unit.silver_reference));
    step3.appendChild(reference);

    const finish = el('div', 'finish-unit');
    view.statusLine = el('div', 'status-line');
    finish.appendChild(view.statusLine);
    const nav = el('div', 'unit-nav');
    const previous = button('‹ Vorherige Aufgabe', 'unit-prev', () => showUnit(index - 1));
    previous.disabled = index === 0;
    nav.appendChild(previous);
    nav.appendChild(button(index === units.length - 1 ? 'Zur Abgabe ↓' : 'Nächste Aufgabe ›', 'unit-next', () => advance(index)));
    finish.appendChild(nav);
    work.appendChild(finish);

    root.appendChild(section);
    renderManual(unitId);
  }
  function renderRestChoices(unitId) {
    const view = views[unitId];
    const us = review(unitId);
    const current = !us.audit ? '' : (added(unitId) || restSaidYes[unitId] ? 'found' : 'ok');
    restSaidYes[unitId] = current === 'found';
    view.reportBox.hidden = current !== 'found';
    view.restChoices.textContent = '';
    view.restChoices.appendChild(radioGroup(view.noRest ? [
      {id: 'ok', name: 'Ja. Es fehlt auch keine Angabe in Schritt 2.'},
      {id: 'found', name: 'Es fehlt eine Angabe. Ich trage sie ein.'},
    ] : [
      {id: 'ok', name: 'Ja, der Rest steht so im Scan links. Es fehlt auch keine Angabe in Schritt 2.'},
      {id: 'found', name: 'Nein, oder es fehlt eine Angabe. Ich trage die Stelle ein.'},
    ], 'rest-choice', current, (id) => {
      us.audit = true;
      restSaidYes[unitId] = id === 'found';
      view.reportBox.hidden = id !== 'found';
      persist();
    }));
  }
  function renderAll() {
    root.textContent = '';
    Object.keys(views).forEach((key) => { delete views[key]; });
    units.forEach(renderUnit);
    units.forEach((unit) => updateUnitStatus(unit.unit_id));
    showUnit(Math.min(state.current, units.length - 1));
  }

  function serialize(draft) { return core.serialize(draft, reviewerInput.value.trim()); }
  function advance(index) {
    if (index < units.length - 1) showUnit(index + 1);
    else document.getElementById('export').scrollIntoView?.({block: 'center'});
  }
  function applySaved(saved) {
    const validated = core.validateSaved(saved);
    if (typeof saved.reviewer === 'string') reviewerInput.value = saved.reviewer;
    core.replaceState(validated);
    units.forEach((unit) => { delete restSaidYes[unit.unit_id]; });
    renderAll();
  }
  function persist() {
    units.forEach((unit) => { if (views[unit.unit_id]) updateUnitStatus(unit.unit_id); });
    updateProgress();
    queueRemote();
    if (!storage) return;
    try { storage.setItem(storageKey, JSON.stringify(serialize(true))); } catch (caught) { /* storage unavailable */ }
  }

  // --- hosted mode: server-side draft and submission -----------------------
  const REMOTE_DELAY = 3000;
  const REMOTE_RETRY = 5000;
  const OFFLINE = 'Nicht gespeichert. Prüfen Sie Ihre Internetverbindung.';
  let remoteTimer = null;
  let lastRemote = '';
  const remoteKey = (doc) => { const copy = Object.assign({}, doc); delete copy.saved_at; return JSON.stringify(copy); };
  const clock = (when) => when.toLocaleTimeString('de-DE', {hour: '2-digit', minute: '2-digit'}) + ' Uhr';
  function setSaveStatus(text, failed) {
    if (!saveStatus) return;
    saveStatus.textContent = text || '';
    saveStatus.className = 'topbar-save' + (failed ? ' failed' : '');
    saveStatus.hidden = !hosted || !text;
  }
  async function request(path, method, doc) {
    const init = {method, credentials: 'same-origin', headers: {'accept': 'application/json'}};
    if (doc !== undefined) { init.headers['content-type'] = 'application/json'; init.body = JSON.stringify(doc); }
    const response = await fetch(path, init);
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response;
  }
  async function pushRemote() {
    remoteTimer = null;
    const doc = serialize(true);
    const key = remoteKey(doc);
    if (key === lastRemote) return;
    try {
      await request('/api/state', 'PUT', doc);
      lastRemote = key;
      setSaveStatus('Gespeichert ' + clock(new Date()));
    } catch (caught) {
      setSaveStatus(OFFLINE, true);
      queueRemote(REMOTE_RETRY);
    }
  }
  function queueRemote(delay) {
    if (!hosted) return;
    if (remoteTimer) clearTimeout(remoteTimer);
    remoteTimer = setTimeout(pushRemote, delay === undefined ? REMOTE_DELAY : delay);
  }
  // The login is the identity: the worker knows the address and stamps it
  // into every saved document, so the reviewer types no Kürzel.
  async function adoptIdentity() {
    try {
      const who = await (await request('/api/whoami', 'GET')).json();
      if (who && typeof who.email === 'string' && who.email) {
        reviewerInput.value = who.email;
        const row = document.getElementById('reviewer-row');
        if (row) row.hidden = true;
        return who.email;
      }
    } catch (caught) { /* fall back to the visible field */ }
    return '';
  }
  async function restoreFromServer() {
    const identity = await adoptIdentity();
    try {
      const response = await request('/api/state', 'GET');
      if (response.status === 204) { restoreFromStorage(); if (identity) reviewerInput.value = identity; return; }
      const saved = await response.json();
      lastRemote = remoteKey(saved);
      applySaved(saved);
      if (identity) reviewerInput.value = identity;
      const when = saved.saved_at ? new Date(saved.saved_at) : null;
      setNotice('Ihr Zwischenstand' + (when && !Number.isNaN(when.getTime()) ? ' vom ' + when.toLocaleString('de-DE') : '') + ' ist wieder da. Sie können weiterarbeiten.');
      setSaveStatus('Gespeichert');
    } catch (caught) {
      restoreFromStorage();
      setSaveStatus(OFFLINE, true);
    }
  }
  async function submitRemote() {
    const button = document.getElementById('export');
    button.disabled = true;
    setNotice('Ihre Prüfung wird abgegeben …');
    try {
      const result = await (await request('/api/submit', 'POST', serialize(false))).json();
      const when = result.submitted_at ? new Date(result.submitted_at) : new Date();
      setNotice('Vielen Dank! Ihre Prüfung ist abgegeben (' + when.toLocaleString('de-DE') + '). Sie können die Seite jetzt schließen.');
      noticeBox.scrollIntoView?.({block: 'center'});
    } catch (caught) {
      setError('Die Abgabe hat nicht geklappt. Prüfen Sie Ihre Internetverbindung. Klicken Sie dann noch einmal auf „Prüfung abgeben“.');
    } finally {
      button.disabled = false;
    }
  }
  function restoreFromStorage() {
    if (!storage) return;
    let raw = null;
    try { raw = storage.getItem(storageKey); } catch (caught) { return; }
    if (!raw) return;
    try {
      const saved = JSON.parse(raw);
      applySaved(saved);
      const when = saved.saved_at ? new Date(saved.saved_at) : null;
      setNotice('Ihr Zwischenstand' + (when && !Number.isNaN(when.getTime()) ? ' vom ' + when.toLocaleString('de-DE') : '') + ' ist wieder da. Sie können weiterarbeiten.');
    } catch (caught) {
      setError('Ihr Zwischenstand lässt sich nicht öffnen. Öffnen Sie eine gespeicherte Datei über „Gespeicherten Zwischenstand öffnen“. Wenn das nicht hilft, melden Sie sich bitte bei uns.');
    }
  }
  function download(name, value) {
    const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }
  function saveDraftFile() {
    setError('');
    download('zwischenstand-' + packet.packet_id + '.json', serialize(true));
    setNotice('Ihr Zwischenstand liegt als Datei im Ordner „Downloads“. Am anderen Computer klicken Sie auf „Gespeicherten Zwischenstand öffnen“. Wählen Sie dort diese Datei.');
  }
  function loadDraftFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        applySaved(JSON.parse(reader.result));
        persist();
        setError('');
        setNotice('Ihr Zwischenstand ist geöffnet. Sie können weiterarbeiten.');
      } catch (caught) {
        setError('Die Datei passt nicht zu diesem Formular oder ist beschädigt. Wählen Sie die Datei für Ihren Zwischenstand. Wenn das nicht hilft, melden Sie sich bitte bei uns.');
      }
    };
    reader.readAsText(file);
  }
  function exportFinal() {
    setError('');
    setNotice('');
    if (!reviewerInput.value.trim()) {
      setError('Tragen Sie oben Ihr Kürzel ein.');
      reviewerInput.scrollIntoView?.({block: 'center'});
      reviewerInput.focus?.({preventScroll: true});
      return false;
    }
    const open = [];
    let firstOpen = -1;
    units.forEach((unit, index) => {
      const list = problems(unit.unit_id);
      if (!list.length) return;
      if (firstOpen < 0) firstOpen = index;
      open.push('Aufgabe ' + (index + 1) + ': ' + list.join('; '));
    });
    if (open.length) {
      setError('Es fehlen noch Antworten. Gehen Sie zu den genannten Aufgaben.\n' + open.join('\n'));
      showUnit(firstOpen);
      errorBox.scrollIntoView?.({block: 'start'});
      return false;
    }
    if (hosted) { submitRemote(); return true; }
    const name = 'annotations-' + packet.packet_id + '.json';
    download(name, serialize(false));
    setNotice('Die Datei für die Abgabe heißt: ' + name + '. Sie liegt im Ordner „Downloads“. Schicken Sie uns die Datei per E-Mail.');
    return true;
  }

  renderAll();
  reviewerInput.addEventListener('input', () => persist());
  reviewerInput.addEventListener('change', () => persist());
  document.getElementById('save-draft').addEventListener('click', saveDraftFile);
  document.getElementById('load').addEventListener('click', () => document.getElementById('load-file').click());
  document.getElementById('load-file').addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) loadDraftFile(file);
  });
  document.getElementById('export').addEventListener('click', exportFinal);
  navPrev.addEventListener('click', () => showUnit(state.current - 1));
  navNext.addEventListener('click', () => advance(state.current));
  if (hosted) {
    document.getElementById('export').textContent = 'Prüfung abgeben';
    const help = document.getElementById('finish-help');
    if (help) help.textContent = 'Ihre Antworten werden laufend gespeichert. Sie können die Seite jederzeit schließen und später weitermachen. Wenn alle Aufgaben fertig sind, klicken Sie auf „Prüfung abgeben“.';
    const advanced = document.getElementById('advanced');
    if (advanced) advanced.hidden = true;
    restoreFromServer();
  } else {
    restoreFromStorage();
  }

  globalThis.pilotReview = {
    state, views, unitProblems: problems, serialize, applySaved, showUnit, exportFinal, saveDraftFile, persist,
    addManualSpan: core.addManualSpan, addManualEntity: core.addManualEntity,
  };
})();
