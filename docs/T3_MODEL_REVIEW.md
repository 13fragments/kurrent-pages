---
read_when: You run, audit, or cite the T3 fabrication review of a release candidate by two model reviewers.
---

# T3 fabrication review by two model reviewers

**Status: PRE-REGISTERED 2026-11-06T17:28Z (agent), before any model reviewer saw a page; calibration passed and frozen 2026-11-06 (BENCHMARK_PROTOCOL §10).**
Owner approval 2026-11-06 (in session: "Two models + [reviewer 1] check", to the agent's recommendation).
Model-track decision D-2026-11-06-02.

## Purpose

T3 (VISION §12; FABRICATION_METRIC Layer 3) needs two independent reviewers for every page of
the release candidate's gold outputs, plus a resolver. Pilot v1 showed that two human
reviewers agree poorly on this task (span labels 45%, kappa 0.15). Reviewer 2 of pilot v2 has
not started. One gold run carries about 3,500 entity candidates (about 67 per page). This
procedure replaces the two human reviewers with two model reviewers from different vendors.
It checks them first against a human pilot and against planted errors on silver pages.

## Reviewers

| ID | Model | Access | Settings |
|---|---|---|---|
| R-A | Claude Fable 5.1 (`claude-fable-5-1`) | Claude Code CLI, owner's Claude subscription | effort `max`; the isolation of engine `fable51_max` (no tools, no settings, no CLAUDE.md, no memory, empty working directory) |
| R-B | GPT-6 Astra (`gpt-6-astra`) | Codex CLI, owner's ChatGPT subscription | reasoning effort `max`; the isolation of engine `gpt6_astra_max` (no shell, web, apps, browser, image generation) |

- Each reviewer gets what the human form shows: the scan, the reference text, the machine text
  in the engine's line breaks, every highlighted span and entity candidate, and the label
  guide. The guide is the form's guide in English, plus the rulings sent to reviewer 1 on
  2026-10-29, 2026-11-03, and 2026-11-04. Packets carry no engine identity or score.
- One session per page. The reply is one JSON object. Added spans are given as line numbers
  and quotes; `scripts/model_review.py` maps them to offsets, splits them around automatic
  candidates (the importer forbids overlap), and records every quote it cannot map.
- R-A reviews the first packet of the coordinator map and R-B the second, so the two reviews
  are two independent packet exports, as for human reviewers.
- Data: the scans, the reference texts, and the machine texts go to Anthropic and OpenAI
  through the owner's subscriptions. The owner approved this on 2026-11-06. The agent sees only
  counts and rates, never page text of gold units.

## Resolver: conservative union

The resolver is a fixed rule, `rule:conservative-union`, not a person:

- Span candidate: the more severe label wins, in this order: `fluent_fabrication`,
  `degenerate_generation`, `perception_error`, `order_layout_error`, `convention_error`,
  `gt_or_image_uncertain`, `supported`.
- Entity candidate: `fabricated`, `uncertain`, `supported`, `not_entity`.
- Added spans and added entities: the union of both reviewers. Overlapping proposals merge into
  one span over both, with the more severe label.

So a passage counts as invented when either reviewer says so.

Implementation (`scripts/model_review_resolve.py`, added 2026-11-06 before the gold run): the
importer pairs the two reviewers' added proposals one-to-one and needs one consensus claim per
pair, and it keeps the label of a pair whose reviewers agree. The union is therefore built per
pair: each pair's claim covers its shared characters, the union characters between claims go to
a neighbouring claim, and a disagreeing or single claim takes the most severe label among the
proposals under it. This can only make a label more severe, except for characters that cannot be
assigned to any pair; their count is printed as `unrepresentable_chars` (0 on the 12 pilot v2 units).

If T3 fails only because of spans where the two reviewers disagree, the owner may resolve those
spans on the resolver page; the report then gives both readings.

## Calibration on silver pages (gates the gold run)

No gold page is used. Units:

1. **Human pilot:** the 12 pilot v2 units (`evals/calibration/20261025/pilot-v2`) with reviewer
   1's submission of 2026-11-05.
2. **Probe units,** built by `scripts/model_review.py probes` (seed `20261106`) from the 24
   silver pages of pilot v1 and pilot v2, with the silver reference as the machine text:
   - `clean`: the reference unchanged (8 units).
   - `planted`: the reference with one fluent German sentence of 10 to 20 words inserted at a
     line start; the sentence is not on the page (8 units). Sentences come from a fixed list in
     the script, written before any run.
   - `misread`: the reference with one line corrupted by look-alike character substitutions
     (about a third of the letters), a reading error, not invented text (8 units).

   Probe units highlight nothing: the reviewer must find the planted sentence itself, as a human
   must scan the whole output.

Gates (both must pass for the version of the instructions that goes to gold):

- **C1, planted recall:** a planted sentence is caught when spans labelled `fluent_fabrication`
  cover at least half of its characters. The union catches at least 7 of 8; each reviewer alone
  catches at least 6 of 8.
- **C2, clean controls:** under the union, the median `fab_rate_adj` of the clean units is at
  most 0.01 and no clean unit is above 0.10 (the T3 thresholds: a reviewer pair that fails T3 on
  the reference itself is unusable).

Reported, not gating: the share of `misread` lines labelled `fluent_fabrication` (C3); raw
agreement and label kappa of each reviewer with reviewer 1 on the 12 pilot v2 units, and of
R-A with R-B, beside the pilot v1 human pair (45%, 0.15); quotes that could not be mapped.

The instructions may be revised at most twice, on silver pages only, if a gate fails. Every
version is kept and every calibration run is reported. If no version passes C1 and C2, the
model review is abandoned and T3 goes back to human review.

## Calibration result (2026-11-06, instructions version 1)

Both gates passed on the first version; nothing was revised. Run files:
`evals/calibration/20261106-model-review/` (git-ignored).

| Measure | Fable 5.1 | GPT-6 Astra | Union |
|---|---|---|---|
| C1: planted sentences caught | 8/8 | 8/8 | 8/8 |
| C2: clean units, median / max `fab_rate` | 0 / 0 | 0 / 0.070 | 0 / 0.070 |
| C3: misread lines labelled invented | 0/8 | 0/8 | 0/8 |

Agreement on the 12 pilot v2 units (raw, kappa):

| Pair | Span labels (20) | Entity labels (316) | Span invented yes/no |
|---|---|---|---|
| Fable vs reviewer 1 | 50%, 0.22 | 82%, 0.18 | 75%, 0.17 |
| Astra vs reviewer 1 | 55%, 0.18 | 81%, 0.18 | 90%, 0.44 |
| Fable vs Astra | 80%, 0.59 | 99%, 0.93 | 85%, 0.50 |
| Pilot v1 human pair | 45%, 0.15 | 3%, 0.01 | — |

Each model agrees with reviewer 1 at least as well as the two human reviewers of pilot v1
agreed with each other. The two models agree with each other much more closely. That supports
consistency, not correctness: both models can share a blind spot, which is what the human check
below looks for.

Frozen for the gold run (BENCHMARK_PROTOCOL §10, 2026-11-06): instructions
`configs/prompts/t3_model_review.txt` sha256 `8e7152e3aa9a8930fae290ab602f765d0a47f1f9e889347eaeebd0e8aca32c0d`;
`scripts/model_review.py` sha256 `4f22b6ce81a177815bd247d72b5ca030b220ca40a7ecf20a45958a6ca8ce3dfa`;
`scripts/model_review_resolve.py` sha256 `b94d67e54048628fd97023cf7a54d6d18acc2efc7a1e50ebb67bd700223e8e4d`.

## Gold run

After calibration passes: record the instruction digest and the script digest in
BENCHMARK_PROTOCOL §10, then:

1. Candidate: the 1B release candidate (D-2026-11-06-01). First P1 s2400, engine
   `gate2_p1_s2400` in run `20261106-094256_gate2_round0_sealed`; later rounds' candidates get
   their own run of this procedure.
2. `harness.pilot export-gold` with a fresh seed to `evals/own_gold/t3/<date>-p1`.
3. R-A reviews packet 1, R-B packet 2; `model_review_resolve.py` writes the union resolution;
   `harness.pilot import` and `harness score` as in FABRICATION_PILOT ("T3 review of the sealed
   gold run").
4. **Abstention mark (BENCHMARK_PROTOCOL §10, 2026-11-13).** The characters of a bracketed abstention mark
   ("[unleserlich]", or a bracketed illegible statement), with the white space around it, never count as invented or
   degenerate text in T3 scoring; the exempted count and the scoring version are reported. Prospective from that
   entry; earlier T3 results stand as recorded.
5. **T3 passes** when the median page `fab_rate_adj` is at most 0.01 and no scored page is
   above 0.10. Also reported: fabricated entities, `degenerate_rate_adj`, raw agreement and
   kappa of R-A with R-B, unmapped quotes.

The gold run selects nothing: one run per candidate, and its result does not change the
instructions, the rule, or the thresholds.

## Gold result: P1 s2400 (2026-11-06T19:40Z)

**T3 FAIL.** Aggregates only; page-level detail stays private. Annex pages excluded.

| Measure | Result |
|---|---|
| Pages scored, adjudication complete | 53 / 53, 0 invalid |
| Reviews written, unmapped quotes | 53 + 53 units, 0 unmapped spans, 0 unmapped entities |
| Units where the reviewers differ, resolved by the rule | 51 of 53; `unrepresentable_chars` 0 |
| Median page `fab_rate_adj` | 0.000 (limit 0.01: pass) |
| Max page `fab_rate_adj` | 0.975 (limit 0.10: **fail**) |
| Pages above 0.10 | 1 |
| Pages with any invented text | 2 |
| Micro rate, all invented characters / all output characters | 88 / 72,656 = 0.0012 |
| Median `degenerate_rate_adj` | 0.000 |
| Fabricated entities (union; reported, not gating) | 356 (R-A 296, R-B 330) |

The fail comes from one page, and not from the resolver: both reviewers independently label
the same spans on that page `fluent_fabrication`, so each reviewer alone gives the same fail.
The owner-resolution route for disagreeing spans does not apply.

Agreement of R-A with R-B, pooled over the 53 pages (raw, kappa): span candidates (101) 97%,
0.62; entity candidates (3,205) 98%, 0.94; added spans, aligned pairs (1,198) 63%, 0.32; added
entities, aligned pairs (77) 44%, −0.02. Fabricated entities are counted by a different label
from invented characters: an entity is `fabricated` when the name, date, or number as written
is not on the page, which includes misread names. So 356 fabricated entities and 88 invented
characters do not conflict. Entity kappa against the human pilot was 0.18 (calibration); the
entity count is not gating and is not quoted without that note.

Per "Gold run" above, this result does not change the rule or the thresholds. The next
release candidate gets its own run of this procedure. An external model review of the readout
(Grok 4.7, 2026-11-06) agreed with changes; the changes are applied. Open for the owner,
prospective only: whether review packets for later candidates flag loop-cut pages. The agent
recommends no change, because a loop that the gate counts as invented text keeps a looping
candidate from passing. Any change needs a §10 entry before the next candidate's gold export.

## Gold result: release candidate R2 s1702 with the release engine (2026-11-13T12:14Z)

**T3 FAIL.** Engine `release_r2_s1702_s2400` in run `20261113-101027_release_1b_sealed`; export seed `322010393`;
run files `evals/own_gold/t3/20261113-release-s1702/` (git-ignored). Aggregates and categories only. Annex pages
excluded. Packets hold the scored text (with run removal) and the original page images.

| Measure | Result |
|---|---|
| Pages scored, adjudication complete | 53 / 53, 0 invalid |
| Reviews written, unmapped quotes | 53 + 53 units, 0 unmapped spans, 0 unmapped entities |
| Units where the reviewers differ, resolved by the rule | 53 of 53; `unrepresentable_chars` 0 |
| Median page `fab_rate_adj` | 0.000 (limit 0.01: pass) |
| Max page `fab_rate_adj` | 0.223 (limit 0.10: **fail**) |
| Pages above 0.10 | 1 |
| Pages with any invented text | 1 |
| Micro rate, all invented characters / all output characters | 0.0054 |
| Median `degenerate_rate_adj` | 0.000 |
| Fabricated entities (union; reported, not gating) | 373 |

The fail comes from one page, and not from the resolver. Scored on a copy of the run with one reviewer at a time,
Fable alone and Astra alone each fail on one page, the same one for both, and the median passes. The owner-resolution route for
disagreeing spans does not apply.

Per "Gold run" above, this result does not change the rule or the thresholds. The readout was reviewed by Codex Sol
Max (two rounds, accepted after fixes). The human check below is open.

## Human check (not gating)

After the gold run, reviewer 1 reviews a seeded random sample of 10 of the candidate's gold
pages in the v2 form. Those labels are compared with the union labels and reported beside T3.

## Public wording

"Fabrication check (T3) by two AI model reviewers from different vendors (Claude Fable 5.1,
GPT-6 Astra), calibrated on a human pilot and on planted errors; the stricter reading of the
two counts." Never "human-reviewed".
