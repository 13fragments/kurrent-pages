// Resolver core: consensus state, the checks harness.adjudication applies at
// import, and the resolution document.  No DOM here, so a plain Node test can
// drive it.
(() => {
  'use strict';
  const RESOLUTION_SCHEMA = 'fabrication-pilot-resolution-v01';

  function createResolverCore(bundle, ui) {
    const units = bundle.units || [];
    const unitById = {};
    units.forEach((unit) => { unitById[unit.unit_id] = unit; });
    const spanLabelIds = ui.spanLabels.map((item) => item.id);
    const entityLabelIds = ui.entityLabels.map((item) => item.id);
    const entityKindIds = ui.entityKinds.map((item) => item.id);

    // Python offsets count Unicode code points, not UTF-16 units.
    const chars = (unit) => Array.from(unit.hypothesis_normalized);
    const sliceText = (unit, start, end) => chars(unit).slice(start, end).join('');
    const overlaps = (a0, a1, b0, b1) => a0 < b1 && b0 < a1;
    const label = (review, field, id) => review[field][id];
    const disagreeing = (unit, field, items) => items
      .filter((item) => label(unit.reviews[0], field, item.id) !== label(unit.reviews[1], field, item.id))
      .map((item) => item.id);

    // One consensus claim per aligned pair of reviewer proposals, as the
    // scorer pairs them.  `labelLocked`: both reviewers gave the same label,
    // so the scorer requires it.  `boundaryLocked`: same label and boundary
    // (and kind), so the claim is already agreed.
    function pairs(unit, entity) {
      const field = entity ? 'manual_entities' : 'added_spans';
      return (entity ? unit.manual_entity_pairs : unit.manual_span_pairs).map(([left, right]) => {
        const a = left === null ? null : unit.reviews[0][field][left];
        const b = right === null ? null : unit.reviews[1][field][right];
        const sameBoundary = Boolean(a && b && a.start === b.start && a.end === b.end && (!entity || a.kind === b.kind));
        const labelLocked = Boolean(a && b && a.label === b.label);
        return {a, b, labelLocked, boundaryLocked: labelLocked && sameBoundary, sameBoundary};
      });
    }
    function initialClaim(pair, entity) {
      const source = pair.a && pair.b ? (pair.sameBoundary ? pair.a : null) : (pair.a || pair.b);
      const claim = {start: source ? source.start : null, end: source ? source.end : null, label: pair.labelLocked ? pair.a.label : ''};
      if (entity) claim.kind = source ? source.kind : (pair.a.kind === pair.b.kind ? pair.a.kind : '');
      return claim;
    }
    function emptyState(unit) {
      return {
        spans: {},
        entities: {},
        manualSpans: pairs(unit, false).map((pair) => initialClaim(pair, false)),
        manualEntities: pairs(unit, true).map((pair) => initialClaim(pair, true)),
      };
    }
    const state = {resolver: '', units: {}};
    units.forEach((unit) => { state.units[unit.unit_id] = emptyState(unit); });

    function unitProblems(unitId) {
      const unit = unitById[unitId];
      if (!unit.disagreement) return [];
      const us = state.units[unitId];
      const out = [];
      const openSpans = disagreeing(unit, 'candidate_labels', unit.candidate_spans).filter((id) => !us.spans[id]).length;
      if (openSpans) out.push(openSpans + ' highlighted span(s) without a consensus label');
      const openEntities = disagreeing(unit, 'entity_labels', unit.entity_candidates).filter((id) => !us.entities[id]).length;
      if (openEntities) out.push(openEntities + ' entity candidate(s) without a consensus label');
      const length = chars(unit).length;
      const check = (claims, pairList, automatic, entity) => {
        const noun = entity ? 'Added entity ' : 'Added span ';
        claims.forEach((claim, index) => {
          const name = noun + (index + 1) + ': ';
          if (!claim.label) out.push(name + 'choose a label');
          if (entity && !claim.kind) out.push(name + 'choose a kind');
          if (!Number.isInteger(claim.start) || !Number.isInteger(claim.end) || claim.start < 0 || claim.end > length || claim.start >= claim.end) {
            out.push(name + 'choose a boundary');
            return;
          }
          const pair = pairList[index];
          if ([pair.a, pair.b].some((ref) => ref && !overlaps(claim.start, claim.end, ref.start, ref.end))) out.push(name + 'the boundary must overlap every reviewer proposal');
          if (automatic.some((item) => overlaps(claim.start, claim.end, item.start, item.end))) out.push(name + 'the boundary overlaps an automatic candidate');
          if (claims.some((other, j) => j !== index && Number.isInteger(other.start) && overlaps(claim.start, claim.end, other.start, other.end))) out.push(name + 'the boundary overlaps another added claim');
        });
      };
      check(us.manualSpans, pairs(unit, false), unit.candidate_spans, false);
      check(us.manualEntities, pairs(unit, true), unit.entity_candidates, true);
      return out;
    }
    const status = (unitId) => (!unitById[unitId].disagreement ? 'agreed' : (unitProblems(unitId).length ? 'open' : 'resolved'));

    function unitResolution(unitId) {
      const unit = unitById[unitId];
      const us = state.units[unitId];
      return {
        resolver: state.resolver,
        candidate_labels: disagreeing(unit, 'candidate_labels', unit.candidate_spans).map((id) => ({candidate_id: id, label: us.spans[id]})),
        entity_labels: disagreeing(unit, 'entity_labels', unit.entity_candidates).map((id) => ({candidate_id: id, label: us.entities[id]})),
        manual_spans: us.manualSpans.map((c) => ({start: c.start, end: c.end, label: c.label})),
        manual_entities: us.manualEntities.map((c) => ({start: c.start, end: c.end, kind: c.kind, label: c.label})),
      };
    }
    // Only resolved disagreeing units: an agreeing unit must keep a null
    // resolver, so it never appears in the resolution document.
    function serialize(withState) {
      const out = {
        schema_version: RESOLUTION_SCHEMA,
        bundle_id: bundle.bundle_id,
        bundle_sha256: bundle.bundle_sha256,
        map_sha256: bundle.map_sha256,
        units: {},
      };
      units.forEach((unit) => { if (status(unit.unit_id) === 'resolved') out.units[unit.unit_id] = unitResolution(unit.unit_id); });
      // The state lets the page reopen the file; the importer ignores it.
      if (withState) {
        out.state = JSON.parse(JSON.stringify(state));
        out.saved_at = new Date().toISOString();
      }
      return out;
    }

    function validateSaved(saved) {
      if (!saved || typeof saved !== 'object' || saved.bundle_id !== bundle.bundle_id || saved.bundle_sha256 !== bundle.bundle_sha256) {
        throw new Error('The saved resolution belongs to a different resolver page.');
      }
      const source = saved.state;
      if (!source || typeof source !== 'object' || !source.units || typeof source.units !== 'object') throw new Error('The saved resolution has no state.');
      const result = {resolver: typeof source.resolver === 'string' ? source.resolver : '', units: {}};
      const offset = (value) => (value === null || Number.isInteger(value) ? value : (() => { throw new Error('A saved boundary is not a number.'); })());
      const pick = (value, allowed) => { if (value === '' || allowed.includes(value)) return value; throw new Error('A saved label is unknown.'); };
      units.forEach((unit) => {
        const saved_unit = source.units[unit.unit_id];
        const fresh = emptyState(unit);
        if (!saved_unit) { result.units[unit.unit_id] = fresh; return; }
        const labels = (value, ids, allowed) => {
          const out = {};
          Object.entries(value || {}).forEach(([id, item]) => { if (!ids.has(id)) throw new Error('A saved label belongs to another unit.'); out[id] = pick(item, allowed); });
          return out;
        };
        const claims = (value, initial, entity) => {
          if (!Array.isArray(value) || value.length !== initial.length) throw new Error('Saved added claims do not match the reviews.');
          return value.map((claim) => {
            const out = {start: offset(claim.start), end: offset(claim.end), label: pick(claim.label || '', entity ? entityLabelIds : spanLabelIds)};
            if (entity) out.kind = pick(claim.kind || '', entityKindIds);
            return out;
          });
        };
        result.units[unit.unit_id] = {
          spans: labels(saved_unit.spans, new Set(unit.candidate_spans.map((c) => c.id)), spanLabelIds),
          entities: labels(saved_unit.entities, new Set(unit.entity_candidates.map((c) => c.id)), entityLabelIds),
          manualSpans: claims(saved_unit.manualSpans, fresh.manualSpans, false),
          manualEntities: claims(saved_unit.manualEntities, fresh.manualEntities, true),
        };
      });
      return result;
    }
    function replaceState(validated) {
      state.resolver = validated.resolver;
      units.forEach((unit) => { state.units[unit.unit_id] = validated.units[unit.unit_id]; });
    }

    return {
      units, unitById, state, chars, sliceText, overlaps, pairs, disagreeing,
      spanLabelIds, entityLabelIds, entityKindIds,
      unitProblems, status, serialize, validateSaved, replaceState,
    };
  }

  globalThis.createResolverCore = createResolverCore;
})();
