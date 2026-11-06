# Fabrication metric redesign

**Status:** executable post-silver, pre-gold implementation draft; written
2026-07-10. This document does not itself amend `BENCHMARK_PROTOCOL.md` v0.1 or
ratify T3.

**Read when:** changing fabrication scoring, Gate 1 T3, entity precision, report
aggregation, or hallucination probes.

## Implementation state

The harness now implements the deterministic diagnostics, candidate generator,
versioned hypothesis-entity extractor, frozen-image- and hypothesis-bound two-review
coordinator form, resolved scoring, pooled reliability statistics, tail reporting,
and deterministic fixtures described here. The implementation remains deliberately marked `draft`:
candidate parameters and the adjudication schema are not frozen, and T3 emits no
PASS/FAIL.

Update 2026-09-06: cross-engine review-volume calibration has run on 96 archived
silver outputs from four engines. The evidence, reproducible commands, and
12-unit human pilot plan are in [FABRICATION_PILOT.md](FABRICATION_PILOT.md).
Human reviews remain pending. Candidate recall on real outputs is not yet known.

Still required before protocol v0.2: completed real-output candidate calibration, the
randomized engine-blind human pilot, label-guide revision from that pilot, frozen
report fields and thresholds, and the dated metric amendment described below.
No T3 threshold has been inferred from the silver results.

Privacy boundary: coordinator/reviewer records, scans, private GT, and page examples
stay in ignored/private evaluator storage. Serialized score records may contain
hypothesis text and hypothesis-side offsets, but never aligned gold words, missed
gold-entity strings, reviewer/resolver identities, or reviewer packets. Public
reports expose only non-identifying pooled reliability statistics and reviewer-pair
consistency. The coordinator form retains engine IDs for safe import; blinded
reviewer packets must remove them and randomize units.

## Decision

The current `fab_rate` is a **long insertion-span rate**. Keep its implementation
and historical results, but stop treating it as a complete fabrication measure.

The replacement design has three layers:

1. deterministic error decomposition and generation-pathology metrics;
2. automatic, high-recall unsupported-span candidates;
3. engine-blind, image-grounded human adjudication for the headline fabrication
   metric and release gate.

This separation is necessary. Given only `(gold text, hypothesis text)`, the same
mismatch can be caused by a visually plausible recognition error, reading-order
failure, convention mismatch, or language-prior invention. Text alignment can
locate unsupported output. It cannot establish why the model emitted it, whether
the image supports it, or whether the error is deceptively fluent.

Do not use an LLM/VLM judge for the official gate. It would introduce a changing,
correlated model into a supposedly reproducible held-out benchmark. A fixed judge
may be reported as a diagnostic only, never as adjudicated ground truth.

## Why v0.1 is insufficient

Protocol §5.3 defines fabrication as five consecutive hypothesis words aligning
to nothing in gold. The implementation marks a word only when at least two thirds
of its characters are character-alignment `INS` operations. It therefore detects
appended prose and runaway repetition well, but excludes substitutions by design.

The silver EVO run exposed two independent failures.

### Construct failure: shorter fluent replacement

`dev_freiberg_0016`:

| quantity | value |
|---|---:|
| gold characters | 2,399 |
| hypothesis characters | 1,037 |
| alignment equal / substitute / insert / delete | 703 / 276 / 58 / 1,420 |
| `cer_norm` | 0.731 |
| `seg_fail` | false |
| v0.1 `fab_rate` | 0.000 |

The hypothesis invents readable technical prose, but it is much shorter than the
reference. Global alignment explains most failure as deletions and substitutions,
so no five-word insertion run exists. `CER > 1` cannot rescue this case: that
usually requires error mass greater than reference length and is therefore strongly
coupled to overlong output.

### Aggregation failure: a safety tail summarized by its median

The 24 page-level v0.1 rates were:

- 19 pages at `0.000`;
- one page at `0.013`;
- four pages at `0.674–0.918`.

Mean `fab_rate` was `0.134`; median was `0.000`. The current report headlines the
median. T3's separate “no page above 0.10” condition catches this particular run,
but the summary still hides the risk, and shorter replacement remains invisible.

### Validation-fixture failure

The original synthetic `fabricator` profile appended fluent text to otherwise
correct GT. It validated exactly the case the implementation was designed to
detect. It did not exercise equal-length replacement, shorter replacement,
function-word overlap, truncation, compound splitting, or reordered correct text.

## Construct and terminology

Use distinct names for distinct claims:

| term | meaning | automatic? |
|---|---|---|
| insertion / over-generation | hypothesis material represented as alignment insertions | yes |
| unsupported output candidate | long local mismatch requiring image review | yes, candidate only |
| perception error | wrong output with a plausible glyph-level path from the image | human label |
| fluent fabrication | readable content with no plausible support in the depicted text | human label |
| degenerate generation | loops, runaway repetition, or other obvious decoder pathology | mostly automatic; adjudicate edge cases |
| omission | depicted gold content absent from the hypothesis | yes |

“Fabrication” is behavioral, not a claim about model internals. The adjudicator
does not need to prove the decoder's cause. They must determine that the emitted
readable content is unsupported by the image and is not merely a transcription,
ordering, or convention error.

## Layer 1: deterministic metrics

Let one fixed minimum-edit character alignment contain matches `C`, substitutions
`S`, insertions `I`, and deletions `D`.

Minimum-edit paths are sometimes non-unique, while `S/I/D` attribution depends on
the selected path. Freeze the alignment implementation, Hirschberg split policy,
and tie-breaking under the scoring-schema version. Add invariants
`C+S+D=len(gold)`, `C+S+I=len(hyp)`, and `S+I+D=edit_distance`; do not compare
component rates produced by different path policies.

### Hypothesis-side character error

```text
hyp_char_error = (S + I) / (C + S + I)
```

Range `[0, 1]`; empty hypothesis returns `0`. This is the precision-side companion
to reference-normalized CER. It measures erroneous emitted character mass, but does
not call that mass fabrication.

### Omission rate

```text
omission_rate = D / (C + S + D)
```

Range `[0, 1]`; empty gold returns `0`.
Reporting it beside `hyp_char_error` distinguishes “said wrong things” from “said
almost nothing.”

### Long insertion-span rate

Rename the exact v0.1 algorithm and output:

```text
long_ins_rate_v01
```

Do not silently reuse `fab_rate` with new semantics. Historical v0.1 run artifacts
remain interpretable and reproducible.

### Excess-length rate

```text
excess_length_rate = max(0, len(hyp) - len(gold)) / len(hyp)
```

Empty hypothesis returns `0`. Diagnostic only: length excess catches gross
over-generation but cannot detect equal or shorter fabrication.

### Repetition rate

Add a deterministic word 4-gram diagnostic:

```text
repeat_4gram_rate = hypothesis word positions covered by second-or-later
                    occurrences of any normalized 4-gram
                    / hypothesis word count
```

Count the union of covered positions once. Keep this separate from fabrication:
runaway repetition is dangerous generation behavior, but usually visible rather
than silently plausible. Calibrate common-formula false positives before gating.

Runaway loops that reach the token limit are removed before scoring by the loop guard
(BENCHMARK_PROTOCOL §10, 2026-10-16; `harness/loop_guard.py`), so they no longer count as
fabrication. A guarded page keeps its unguarded metrics in `loop_guard`.

## Layer 2: automatic candidate generation

Purpose: reduce human review volume while favoring recall. Candidate scores are
reported, but are not named `fab_rate` and do not alone decide T3.

### Candidate algorithm to validate

1. Normalize with the same §4 normalized layer used by `cer_norm`.
2. Retain hypothesis word offsets.
3. Globally align gold and hypothesis word sequences.
4. For an aligned hypothesis word:
   - exact match: supported;
   - insertion: unsupported score `1`;
   - substitution: internally character-align the paired words and use
     `(S + I) / len(hyp_word)` as its unsupported score.
5. Run the existing global character alignment too. If every non-space character
   of a token is an exact character match, override it to supported. This prevents
   a gold compound split into many hypothesis words from becoming a fabricated
   run merely because of whitespace.
6. Current draft review-candidate parameters: word unsupported score `>= 0.3`;
   at least four candidate words inside a span of at most seven words. Bridge
   words prevent coincidental matches of `und`, `die`, `von`, etc. from splitting
   an otherwise unsupported sentence.
7. Merge overlapping candidate windows; preserve word offsets and alignment
   evidence for review.

The initial `0.5` and `5-of-7` parameters were replaced on 2026-09-06 by `0.3`
and `4-of-7`, under `fabrication-review-v02-draft`. The broader deterministic
calibration exposed missed short replacements. The change reached 95.8% span
recall on both the development seed and a separate validation seed; see
[the calibration record](FABRICATION_PILOT.md). These remain draft review-aid
parameters, not T3 tolerances. The legacy five-word insertion metric is unchanged.

### Known candidate false positives

- correct text in the wrong order;
- severe but honest CRNN recognition noise;
- GT errors or unresolved `[unleserlich]` regions;
- abbreviation/convention mismatches;
- tokenization beyond the compound-split override.

These are acceptable review candidates. They are not acceptable automatic
fabrication labels. `ro_cost`, the diplomatic/normalized score gap, and human
adjudication disambiguate them.

## Layer 3: blinded image-grounded adjudication

### Review unit

Official adjudication covers the full hypothesis of every engine included in a
citable fabrication comparison. Automatic candidates are pre-highlighted review
aids, not a filter: reviewers scan the whole output and may add missed spans. A
candidate-only review would turn detector false negatives into benchmark false
negatives.

For every page, show:

- the scan at full-page and zoomed context;
- gold context;
- the full hypothesis with candidates highlighted;
- alignment evidence;
- no engine/model identity and no aggregate score.

Randomize page-output review units across engines. Near-duplicate hypotheses may be
grouped only after independent labels, so one engine's output does not reveal
another.
Hosted submissions that have not received full adjudication publish automatic
diagnostics only and must be labeled `unadjudicated`; they cannot enter the
fabrication leaderboard or satisfy T3.

Every coordinator form is bound to the normalized hypothesis SHA-256 and to the
output record's image SHA-256. Scoring accepts that image binding only when it
matches the exact freeze manifest digest recorded in `run.json`; a missing, stale,
or merely well-formed but different image hash blocks adjudication and reporting.
Displayed automatic-entity text, kind, and offsets are validated against the scored
candidate before import.

### Labels

Each candidate receives exactly one primary label:

1. `supported` — materially present in the image;
2. `perception_error` — wrong, but plausibly derived from depicted glyphs;
3. `convention_error` — normalization, expansion, spelling modernization, markup;
4. `order_layout_error` — supported text, wrong location/order/structure;
5. `fluent_fabrication` — readable content without plausible visual support;
6. `degenerate_generation` — loop/repetition/runaway decoder output;
7. `gt_or_image_uncertain` — evidence insufficient for a defensible judgment.

`fluent_fabrication` requires all of:

- an interpretable lexical sequence, normally at least five words;
- central content not plausibly supported by the depicted glyphs;
- not solely a transcription, convention, ordering, or layout error.

An invented person, place, date, amount, or identifier is high-risk regardless of
span length and is recorded separately even when shorter than five words.

Automatic entity candidates use `supported`, `fabricated`, `uncertain`, or
`not_entity`. The last label excludes extractor false positives such as capitalized
German common-noun phrases. It can also reject a reviewer-proposed entity that the
other reviewer or resolver determines is not an entity claim.

### Review reliability

Two independent reviewers audit every page and label every highlighted or newly
added span used in a citable report. A third reviewer resolves disagreement against
the scan. Publish raw agreement, class-wise counts, and Cohen's kappa; retain
`gt_or_image_uncertain` rather than forcing a label. The benchmark author must not
be the sole adjudicator because the author also develops a competing model.

Reviewer identity comparison is whitespace-normalized and case-insensitive. A
boundary difference counts as disagreement even when the class label agrees. The
resolver may select one canonical boundary for overlapping proposals; the final
consensus must neither duplicate nor double-count those variants. Reliability is
pooled from reviewer confusion tables and marginals across pages—never by averaging
page-level kappa values—and only across one fixed, ordered reviewer pair. Reports
separate exact raw agreement (label plus boundary/kind) from label raw agreement and
label Cohen's kappa; the latter two use the same label confusion marginals. Identities
remain in the private coordinator records and are stripped from public scores.

### Headline outputs

Per page:

```text
fab_chars_adj       characters in fluent_fabrication spans
fab_rate_adj        fab_chars_adj / normalized hypothesis characters
fab_page            whether any fluent_fabrication span exists
degenerate_chars    characters in degenerate_generation spans
degenerate_rate     degenerate_chars / normalized hypothesis characters
fabricated_entities unsupported high-risk entity/date/amount claims
```

Empty hypotheses have zero fabricated output but remain catastrophic omissions and
segmentation failures. Uncertain candidates are reported separately and excluded
from numerator and denominator only in the adjudicated class breakdown; the base
hypothesis-character denominator never changes.

## Entity precision must be independent

The v0.1 precision workflow extracts capitalized name candidates only from detected
fabrication spans. That is circular: when span detection fails, fabricated entities
disappear from precision review too.

Generate hypothesis entity candidates independently of fabrication candidates:

- deterministic date/amount/identifier patterns;
- a frozen person/place candidate extractor;
- manual adjudication against the scan and gold entity annotations.

Report decided entity precision as `supported / (supported + fabricated)`.
`uncertain` and `not_entity` are excluded from that denominator; publish uncertainty
decision coverage as `(supported + fabricated) / (supported + fabricated +
uncertain)` and publish the `not_entity` count separately. Keep gold-entity recall
unchanged. Freeze the extractor and its version; German noun capitalization makes an
unversioned capitalization heuristic unsuitable as the sole extractor.

## Negative-control probes

Keep A01/A02 pure-graphics annex pages. Add a separate, deterministic grounding
probe suite; never mix probe scores into normal-page CER:

- blank page at each representative aspect ratio;
- fully text-masked page retaining border/layout texture;
- human-verified severe blur or block shuffle with no legible glyph sequence;
- original/damaged pairs for a small representative subset.

Expected output is empty text or explicit abstention. Report probe failure incidence
and hallucinated characters. These probes measure susceptibility under absent visual
evidence, not the prevalence of fabrication on normal archival pages.

This matches the construct used by recent document-hallucination work: output
presented as perceived despite absent or damaged visual evidence, tested with
original/damaged image pairs. See [Hwang et al., 2026](https://aclanthology.org/2026.findings-acl.1237/).

## Aggregation and reporting

Never headline the median alone for a tail-risk metric. For each engine and stratum,
report:

- macro median and mean page rate;
- micro rate: `sum(fab_chars_adj) / sum(hyp_chars)`;
- affected-page incidence: `sum(fab_page) / pages`;
- maximum page rate;
- counts above every preregistered severity threshold;
- fabricated entity/date/amount count;
- top examples and all severe examples;
- adjudication disagreements and uncertain cases.

Show an exact binomial interval for page incidence as a simple descriptive bound and
a source/hand-clustered sensitivity analysis where sample size permits. Under the
optimistic assumption that all 53 pages are independent, even zero affected pages
gives a one-sided 95% upper bound of about 5.5%. Source/hand clustering weakens that
claim further. The benchmark can gate the observed set, but cannot honestly establish
a population incidence below 1%; roughly 300 independent zero-failure pages would be
needed for that claim.

Known repeated writers are identified by explicit reporting-only `hand_cluster`
metadata. Unspecified hands fall back to a source-qualified identifier so generic
labels such as “same hand” cannot join unrelated collections. This metadata
clarification is logged separately in protocol §10; it changes no page, image hash,
transcription convention, metric numerator, or threshold.

## Calibration before amendment

Build a checked-in, deterministic metric fixture from dev/synthetic text. Never tune
on private gold outputs.

### Benign/non-fabrication cases

- exact output;
- light and heavy glyph substitutions;
- historical spelling and convention differences;
- line-wrap changes and line/paragraph reordering;
- hyphenation, compound splits, and joins;
- short insertions below the declared span minimum;
- truncation and empty output;
- CRNN-like garbage.

### Known fabrication/pathology cases

Inject text from a different page, preserving a known span label:

- appended fluent spans;
- equal-length block replacement;
- shorter block replacement;
- longer block replacement;
- replacements rich in common German function words;
- invented entity/date/amount spans shorter than five words;
- sentence and token repetition loops.

Test span sizes `3, 5, 10, 25` words, multiple positions, multiple pages, and multiple
seeds. Cross-page human/silver text is preferable to freshly generated prose: fluent,
deterministic, and free of a judge-model dependency.

### Calibration targets

- automatic candidate recall `>= 0.95` for known fabricated spans of at least five
  words;
- `1.00` recall for injected high-risk entities/dates/amounts;
- zero candidates for exact, one-character typo, wrapping, and compound-split
  regression fixtures;
- false-positive volume low enough to adjudicate every candidate;
- exhaustive human review on a sample of real VLM and CRNN pages to estimate missed
  candidates and validate the label guide.

Candidate-generator parameters are chosen from recall and review-volume targets.
T3 tolerances are chosen separately from the archival harm policy, not from engine
percentiles. Recommended hard subcondition: zero adjudicated fabricated person,
place, date, amount, or identifier claims on the held-out set. The remaining micro,
incidence, and maximum-page tolerances must be ratified before the first Gate 1
training or scored gold run; they must not be selected to make a favored engine pass.

## Protocol and schema rollout

1. Implement deterministic metrics, candidate records, aggregation, and fixtures.
   **Complete as an implementation draft.**
2. Run fixtures plus quarantined silver outputs from every engine family.
3. Conduct a small blinded adjudication pilot; revise only the label guide and
   candidate-recall machinery.
4. Freeze candidate parameters, adjudication form, report fields, and T3 thresholds.
5. Add a dated §10 amendment explicitly marked **post-silver, pre-gold**. State that
   silver exposed a construct-validity defect; do not imply the change was blind.
6. Bump protocol/scoring schema to `0.2`; retain `long_ins_rate_v01` for comparison.
7. Amend VISION §11/§12, protocol §5, POST_GATE0 T3, harness README, and DEV_REPORT.
8. Do not alter the Gate 0 kill criterion in protocol §8.
9. Refuse to compare v0.1 `fab_rate` numerically with v0.2 adjudicated fabrication.

Until steps 1–6 complete, T3 remains unresolved: the current metric may be shown as
a diagnostic, but no Gate 1 run should claim a fabrication PASS from it alone.

## Required regression tests

- current five-word appended insertion remains detected;
- equal-length five-word replacement becomes a review candidate;
- shorter five-word replacement becomes a review candidate;
- common bridge words do not break a fabricated candidate span;
- one-character errors do not become fabrication candidates;
- a gold compound split into five or more hypothesis tokens stays non-candidate;
- reordered correct lines are labeled/order-attributed, not adjudicated fabrication;
- empty/truncated output has zero fabricated characters and high omission;
- repeated generation fires repetition and insertion/pathology diagnostics;
- invented one-token date/name/amount reaches entity-risk review;
- report exposes mean, micro, incidence, maximum, and threshold violations;
- old v0.1 artifacts retain their original field semantics.

## Research check

- Historical OCR systems with similar aggregate accuracy can differ substantially
  in error locality, detectability, and scholarly risk: [Vesalainen et al., 2026](https://arxiv.org/abs/2602.14524).
- Automatic hallucination metrics often fail to align with human judgment, supporting
  an explicit adjudication layer: [Kulkarni et al., 2025](https://aclanthology.org/2025.findings-emnlp.1035/).
- The close ASR analogue defines hallucination through classified error types and
  validates the classifier against human labels rather than equating hallucination
  with insertion count: [Atwany et al., 2025](https://aclanthology.org/2025.findings-acl.1190/).
