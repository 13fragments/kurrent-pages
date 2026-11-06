// Review-form core: state, validation, and the export document.  No DOM here,
// so the whole contract with harness.pilot_packets can run in a plain Node test.
(() => {
  'use strict';
  const SCHEMA = 'fabrication-pilot-review-v01';

  function createPilotCore(packet, ui, hooks) {
    const units = packet.units || [];
    const unitById = {};
    units.forEach((unit) => { unitById[unit.unit_id] = unit; });
    const spanLabelIds = ui.spanLabels.map((item) => item.id);
    const entityLabelIds = ui.entityLabels.map((item) => item.id);
    const entityKindIds = ui.entityKinds.map((item) => item.id);

    // Python scoring offsets count Unicode code points, not UTF-16 units.
    const chars = (unit) => Array.from(unit.hypothesis_normalized);
    const overlaps = (a0, a1, b0, b1) => a0 < b1 && b0 < a1;
    const sliceText = (unit, start, end) => chars(unit).slice(start, end).join('');
    const emptyReview = () => ({audit: false, candidateLabels: {}, entityLabels: {}, addedSpans: [], manualEntities: [], notes: {}, unitNote: ''});

    const state = {current: 0, units: {}};
    units.forEach((unit) => { state.units[unit.unit_id] = emptyReview(); });

    function checkOffsets(unit, start, end) {
      const length = chars(unit).length;
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end > length || start >= end) {
        throw new Error('Diese Stelle lässt sich nicht eintragen. Markieren Sie eine Stelle im Text bei Schritt 3.');
      }
    }
    function addManualSpan(unitId, start, end) {
      const unit = unitById[unitId];
      const us = state.units[unitId];
      checkOffsets(unit, start, end);
      if ((unit.candidate_spans || []).some((c) => overlaps(start, end, c.start, c.end))) {
        throw new Error('Ihre Markierung enthält Text aus einer gelben Stelle. Beantworten Sie die Frage dazu in Schritt 1. Wenn mehrere Gründe passen, klicken Sie auf „Weiß nicht“.');
      }
      if (us.addedSpans.some((s) => overlaps(start, end, s.start, s.end))) {
        throw new Error('Diese Stelle haben Sie schon eingetragen.');
      }
      const row = {start, end, label: ''};
      us.addedSpans.push(row);
      us.addedSpans.sort((a, b) => a.start - b.start);
      hooks.onManualSpans(unitId);
      hooks.onChange();
      return row;
    }
    function addManualEntity(unitId, start, end) {
      const unit = unitById[unitId];
      const us = state.units[unitId];
      checkOffsets(unit, start, end);
      if ((unit.entity_candidates || []).some((c) => overlaps(start, end, c.start, c.end))) {
        throw new Error('Ihre Markierung enthält Text aus der Liste in Schritt 2. Prüfen Sie die Angabe dort mit dem Scan links.');
      }
      if (us.manualEntities.some((s) => overlaps(start, end, s.start, s.end))) {
        throw new Error('Diese Angabe haben Sie schon eingetragen.');
      }
      const row = {start, end, kind: '', label: ''};
      us.manualEntities.push(row);
      us.manualEntities.sort((a, b) => a.start - b.start);
      hooks.onManualEntities(unitId);
      hooks.onChange();
      return row;
    }
    function removeManualSpan(unitId, row) {
      const us = state.units[unitId];
      us.addedSpans = us.addedSpans.filter((other) => other !== row);
      hooks.onManualSpans(unitId);
      hooks.onChange();
    }
    function removeManualEntity(unitId, row) {
      const us = state.units[unitId];
      us.manualEntities = us.manualEntities.filter((other) => other !== row);
      hooks.onManualEntities(unitId);
      hooks.onChange();
    }
    function plural(count, singular, pluralForm) { return count + ' ' + (count === 1 ? singular : pluralForm); }
    function unitProblems(unitId) {
      const unit = unitById[unitId];
      const us = state.units[unitId];
      const out = [];
      const openSpans = (unit.candidate_spans || []).filter((c) => !us.candidateLabels[c.id]).length;
      if (openSpans) out.push(plural(openSpans, 'gelbe Stelle ohne Antwort', 'gelbe Stellen ohne Antwort'));
      const openEntities = (unit.entity_candidates || []).filter((c) => !us.entityLabels[c.id]).length;
      if (openEntities) out.push(plural(openEntities, 'Wort in Schritt 2 ohne Antwort', 'Wörter in Schritt 2 ohne Antwort'));
      const openManual = us.addedSpans.filter((s) => !s.label).length;
      if (openManual) out.push(plural(openManual, 'eingetragene Stelle ohne Antwort', 'eingetragene Stellen ohne Antwort'));
      const openManualEntities = us.manualEntities.filter((s) => !s.label || !s.kind).length;
      if (openManualEntities) out.push(plural(openManualEntities, 'eingetragene Angabe: Beantworten Sie beide Fragen', 'eingetragene Angaben: Beantworten Sie jeweils beide Fragen'));
      if (!us.audit) out.push('Beantworten Sie die Frage in Schritt 3');
      return out;
    }

    function serialize(draft, reviewer) {
      const out = {schema_version: SCHEMA};
      if (draft) out.draft = true;
      out.packet_id = packet.packet_id;
      out.packet_sha256 = packet.packet_sha256;
      out.reviewer = reviewer;
      out.units = {};
      units.forEach((unit) => {
        const us = state.units[unit.unit_id];
        out.units[unit.unit_id] = {
          binding_sha256: unit.binding_sha256,
          image_sha256: unit.image_sha256,
          hypothesis_sha256: unit.hypothesis_sha256,
          full_page_reviewed: us.audit === true,
          candidate_labels: (unit.candidate_spans || []).filter((c) => us.candidateLabels[c.id]).map((c) => ({candidate_id: c.id, label: us.candidateLabels[c.id]})),
          added_spans: us.addedSpans.map((s) => ({start: s.start, end: s.end, label: s.label})),
          entity_labels: (unit.entity_candidates || []).filter((c) => us.entityLabels[c.id]).map((c) => ({candidate_id: c.id, label: us.entityLabels[c.id]})),
          manual_entities: us.manualEntities.map((s) => ({start: s.start, end: s.end, kind: s.kind, label: s.label})),
        };
        // Reviewer notes: extra keys the importer ignores; kept in the raw file
        // for the label-guide revision (mixed spans, free remarks).
        const notes = Object.entries(us.notes || {})
          .filter(([, note]) => note && (note.mixed === true || (note.text && note.text.trim())))
          .map(([id, note]) => ({candidate_id: id, mixed: note.mixed === true, text: note.text || ''}));
        if (notes.length) out.units[unit.unit_id].notes = notes;
        if (us.unitNote && us.unitNote.trim()) out.units[unit.unit_id].unit_note = us.unitNote;
      });
      if (draft) out.saved_at = new Date().toISOString();
      return out;
    }

    function intOffset(value, field) {
      const number = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
      if (!Number.isInteger(number) || number < 0) throw new Error('Eine gespeicherte Textstelle lässt sich nicht finden. Öffnen Sie einen anderen Zwischenstand.');
      return number;
    }
    function labelsFromSaved(value, expectedIds, labelIds, field) {
      const result = {};
      if (value === undefined) return result;
      if (!Array.isArray(value)) throw new Error('Die gespeicherten Antworten lassen sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
      value.forEach((item, index) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Eine gespeicherte Antwort lässt sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
        const id = item.candidate_id;
        if (typeof id !== 'string' || !expectedIds.has(id) || Object.prototype.hasOwnProperty.call(result, id) || !labelIds.includes(item.label)) {
          throw new Error('Eine gespeicherte Antwort passt nicht zu diesem Formular oder ist doppelt. Öffnen Sie einen anderen Zwischenstand.');
        }
        result[id] = item.label;
      });
      return result;
    }
    function rowsFromSaved(value, unit, field, withKind) {
      if (value === undefined) return [];
      if (!Array.isArray(value)) throw new Error('Die gespeicherten Textstellen lassen sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
      const length = chars(unit).length;
      const labelIds = withKind ? entityLabelIds : spanLabelIds;
      const rows = value.map((item, index) => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Eine gespeicherte Textstelle lässt sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
        const start = intOffset(item.start, field + '[' + index + '].start');
        const end = intOffset(item.end, field + '[' + index + '].end');
        if (start >= end || end > length) throw new Error('Eine gespeicherte Textstelle liegt außerhalb des Textes. Öffnen Sie einen anderen Zwischenstand.');
        const label = item.label === undefined || item.label === null ? '' : String(item.label);
        if (label && !labelIds.includes(label)) throw new Error('Eine gespeicherte Antwort passt nicht zu den Fragen. Öffnen Sie einen anderen Zwischenstand.');
        const row = {start, end, label};
        if (withKind) {
          const kind = item.kind === undefined || item.kind === null ? '' : String(item.kind);
          if (kind && !entityKindIds.includes(kind)) throw new Error('Eine gespeicherte Angabe passt zu keiner Auswahl unter „Was für eine Angabe ist das?“. Öffnen Sie einen anderen Zwischenstand.');
          row.kind = kind;
        }
        return row;
      });
      rows.sort((a, b) => a.start - b.start);
      for (let index = 1; index < rows.length; index += 1) {
        if (overlaps(rows[index - 1].start, rows[index - 1].end, rows[index].start, rows[index].end)) throw new Error('In der Datei wurde derselbe Text mehrfach markiert. Öffnen Sie einen anderen Zwischenstand.');
      }
      return rows;
    }
    function notesFromSaved(value, spanIds) {
      const result = {};
      if (value === undefined) return result;
      if (!Array.isArray(value)) throw new Error('Die gespeicherten Anmerkungen lassen sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
      value.forEach((item) => {
        if (!item || typeof item !== 'object' || Array.isArray(item) || typeof item.candidate_id !== 'string' || !spanIds.has(item.candidate_id)) {
          throw new Error('Eine gespeicherte Anmerkung passt nicht zu diesem Formular. Öffnen Sie einen anderen Zwischenstand.');
        }
        result[item.candidate_id] = {mixed: item.mixed === true, text: typeof item.text === 'string' ? item.text : ''};
      });
      return result;
    }
    function validateSaved(saved) {
      if (!saved || typeof saved !== 'object') throw new Error('Die Datei enthält keinen Zwischenstand. Wählen Sie die Datei für Ihren Zwischenstand.');
      if (saved.packet_id !== packet.packet_id || saved.packet_sha256 !== packet.packet_sha256) throw new Error('Der Zwischenstand gehört zu einem anderen Formular. Wählen Sie die Datei für dieses Formular.');
      if (saved.reviewer !== undefined && typeof saved.reviewer !== 'string') throw new Error('Ihr Kürzel lässt sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
      const supplied = saved.units === undefined ? {} : saved.units;
      if (!supplied || typeof supplied !== 'object' || Array.isArray(supplied)) throw new Error('Die Aufgaben im Zwischenstand lassen sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
      const result = {};
      for (const [unitId, review] of Object.entries(supplied)) {
        const unit = unitById[unitId];
        if (!unit) throw new Error('Der Zwischenstand enthält eine Aufgabe aus einem anderen Formular. Wählen Sie die Datei für dieses Formular.');
        if (!review || typeof review !== 'object' || Array.isArray(review)) throw new Error('Eine Aufgabe im Zwischenstand lässt sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
        if (review.binding_sha256 !== unit.binding_sha256 || review.image_sha256 !== unit.image_sha256 || review.hypothesis_sha256 !== unit.hypothesis_sha256) {
          throw new Error('Die gespeicherten Antworten gehören zu einem anderen Scan oder Text. Wählen Sie die Datei für dieses Formular.');
        }
        if (review.full_page_reviewed !== undefined && typeof review.full_page_reviewed !== 'boolean') throw new Error('Die gespeicherte Antwort zu Schritt 3 lässt sich nicht lesen. Öffnen Sie einen anderen Zwischenstand.');
        const spanIds = new Set((unit.candidate_spans || []).map((c) => c.id));
        const entityIds = new Set((unit.entity_candidates || []).map((c) => c.id));
        result[unitId] = {
          audit: review.full_page_reviewed === true,
          candidateLabels: labelsFromSaved(review.candidate_labels, spanIds, spanLabelIds, unitId + '.candidate_labels'),
          entityLabels: labelsFromSaved(review.entity_labels, entityIds, entityLabelIds, unitId + '.entity_labels'),
          addedSpans: rowsFromSaved(review.added_spans, unit, unitId + '.added_spans', false),
          manualEntities: rowsFromSaved(review.manual_entities, unit, unitId + '.manual_entities', true),
          notes: notesFromSaved(review.notes, spanIds),
          unitNote: typeof review.unit_note === 'string' ? review.unit_note : '',
        };
      }
      return result;
    }
    function replaceState(validated) {
      units.forEach((unit) => { state.units[unit.unit_id] = validated[unit.unit_id] || emptyReview(); });
    }

    return {
      units, unitById, state, chars, sliceText, overlaps, plural,
      spanLabelIds, entityLabelIds, entityKindIds,
      addManualSpan, addManualEntity, removeManualSpan, removeManualEntity,
      unitProblems, serialize, validateSaved, replaceState,
    };
  }

  globalThis.createPilotCore = createPilotCore;
})();
