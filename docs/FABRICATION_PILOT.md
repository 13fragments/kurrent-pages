---
read_when: Running silver fabrication calibration or preparing independent human review packets.
---

# Fabrication calibration and human pilot

**Date: 2026-09-06. Status: automatic calibration complete; human reviews pending.**

This work calibrates review aids on quarantined silver development data. It
does not establish model quality, ratify T3, or change the Gate 0 criterion.
See [the metric design](FABRICATION_METRIC.md) for the definitions and targets.

## Evidence and scope

The archived July 9 runs cover 24 silver pages for each of Tesseract, Kraken,
Calamari, and the Qwen2.5-VL stand-in: 96 page-output pairs. PyLaia and the
other configured VLMs have no usable outputs in this calibration. These four
engines cover the available OCR/CRNN and VLM families, not every registered
benchmark engine.

Some archived `run.json` files refer to the original gold freeze manifest.
Their paths also predate the repository split. The calibration therefore
verifies the silver images, reference text, and metadata against
`harness/dev_manifest.json`, then checks each original output's image hash.
It records the original run and output digests in a new diagnostic artifact.
It does not rewrite the archived metadata or claim a valid historical gold
freeze. Missing pages, changed payloads, and duplicate engine/page inputs fail.

## Cross-engine baseline

The following command scores the archived inputs with the current candidate
parameters. Run it from the benchmark root:

```sh
uv run python -m harness.silver_calibration \
  --run-dir evals/silver/20260709-111024_tess \
  --run-dir evals/silver/20260709-124230_kraken_fresh \
  --run-dir evals/silver/20260709-125244_calamari_fresh \
  --run-dir evals/silver/20260709-154516_evovlm2 \
  --workers 4 \
  --output evals/calibration/20260906/silver-current.json
```

Use a new output path for each run. The command preserves existing reports.
All scans, hypotheses, reviewer packets, and coordinator records stay under
ignored local storage. Only aggregate diagnostics belong in tracked reports.

The baseline below was recorded before changing the candidate parameters:
unsupported-word threshold 0.5, at least five candidate words in a window of
seven. The original report is `evals/calibration/20260906/silver-baseline.json`.
The current command does not recreate that historical configuration.

| Engine | Pages | Span candidates | Entity candidates | Maximum entities on one page |
|---|---:|---:|---:|---:|
| Tesseract Fraktur | 24 | 30 | 957 | 281 |
| Kraken Kurrent | 24 | 92 | 1,204 | 238 |
| Calamari Fraktur | 24 | 48 | 173 | 63 |
| Qwen2.5-VL stand-in | 24 | 75 | 1,428 | 294 |

The 245 spans and 3,762 entities measure review burden, not fabrication.
German capitalization and OCR noise can trigger entity candidates. Reviewers
must use `not_entity` for false entity extractions. Real-output recall and
false-positive rates remain unknown until humans inspect the complete outputs.

## Candidate calibration result

The broader fixture contains 172 cases: ordinary synthetic German reference
pages, injected passages of 3, 5, 10, and 25 words, replacement and insertion
positions, short high-risk entities, and benign/pathology controls. A recalled
span requires candidate coverage of at least 95% of its normalized characters;
merely overlapping the passage does not count. Three-word passages are measured
but excluded from the five-word-or-longer recall target.

| Configuration | Seed | Recalled eligible spans | Entity fixtures | Required benign controls |
|---|---:|---:|---:|---|
| Original: 0.5, 5-of-7 | 20260906 | 102/120 (85.0%) | 4/4 | Pass |
| Revised: 0.3, 4-of-7 | 20260906 | 115/120 (95.8%) | 4/4 | Pass |
| Revised: separate validation seed | 20260907 | 115/120 (95.8%) | 4/4 | Pass |

The small development sweep also tested `(4, 0.5)`, `(4, 0.4)`, and `(5, 0.4)`
for minimum words and unsupported-word threshold. Their recalls were 86.7%,
89.2%, and 87.5%. No further search followed the separate-seed result.
An exploratory cross-page silver check covered 27/27 replacements with the
revised settings, compared with 19/27 at the original settings.

Adopted `fabrication-review-v02-draft`: four candidate words in at most seven,
unsupported-word threshold 0.3. The legacy five-word insertion metric and T3
are unchanged. Five fixture spans remain undercovered in each seed. The
separate seed changes injected passages within the same synthetic source
collection; it is not an independent-corpus validation. Four entity examples
also provide narrow coverage. These results justify a draft review-aid change,
not a claim of 95% recall on real handwriting.

```sh
uv run python -m harness.calibration --seed 20260906 \
  --output evals/calibration/20260906/synthetic-current.json
uv run python -m harness.calibration --seed 20260907 \
  --output evals/calibration/20260906/synthetic-validation.json
```

The updated cross-engine report is `evals/calibration/20260906/silver-current.json`.
Use the earlier silver command with a new output path to reproduce it.
Span candidates change to 36 (Tesseract), 69 (Kraken), 51 (Calamari), and 46
(Qwen stand-in). The total falls to 202 because nearby windows merge; the
highlighted character coverage increases. Entity counts remain 3,762.

## Pilot selection

Selection recorded before any human pilot labels. Include all four engines
on each of these three silver pages, for 12 units per reviewer:

1. `dev_freiberg_0016`: the previously documented shorter-replacement failure.
2. `dev_kch060_615`: the middle ID in the sorted degraded-Fraktur subset, a
   printed-text control.
3. `dev_giessen_0060`: a seeded choice from the sorted IDs in `ugly_kurrent`,
   `table_registry`, and `mixed_print_handwriting`. Use
   `random.Random(20260906).choice(...)`.

Use seed `20260906` for reproducible packet preparation. The coordinator
retains the mapping; reviewer packets conceal engine identities and scores.
Independent packet orders must not reveal the other reviewer's decisions.

This is a small, purposive calibration pilot. It includes a known failure;
it cannot estimate population fabrication prevalence, establish detector recall
across all strata, or demonstrate acceptable release thresholds.

At the initial candidate settings, each reviewer receives 9,243 normalized
hypothesis characters, 44 span candidates, and 315 entity candidates across
the 12 units. These counts exclude reviewer-added claims. They are workload
estimates, not an assurance that the review will be quick.

The generated packets use `fabrication-review-v02-draft`: 20 merged span
candidates and the same 315 entity candidates per reviewer. Every complete
output still requires inspection. Both packets currently have zero human reviews.

## Human review and decisions

Prepare the selected, hash-verified inputs and two blinded packets:

```sh
uv run python scripts/prepare_fabrication_pilot.py \
  --run-dir evals/silver/20260709-111024_tess \
  --run-dir evals/silver/20260709-124230_kraken_fresh \
  --run-dir evals/silver/20260709-125244_calamari_fresh \
  --run-dir evals/silver/20260709-154516_evovlm2 \
  --out evals/calibration/20260906/pilot --seed 20260906
```

Give each reviewer only one complete folder from `pilot/packets/`. For mail
delivery use `scripts/mail_packet.py`: Gmail rejects messages over 25 MB and each
packet holds four 5 MB scans, so the script zips a copy in which only images above
2.5 MB are downscaled (3600 px wide, JPEG quality 85, about 400 dpi equivalent on
these pages) and records original and shipped sha256 per image in a
`MAILCOPY.json` next to the zip. The packet in `pilot/packets/` and the
coordinator map stay untouched, and review exports bind to the original hashes
from `packet.json`; the record is the audit trail that a reviewer saw a
downscaled viewing copy of those four pages. Used 2026-09-14 for both packets. Each folder
contains `review.html`, packet data, and images with opaque names. Keep
`pilot/coordinator/` private; it contains the engine mapping. Reviewers open
`review.html` locally and return their exported annotation JSON independently.

Hosted delivery (used from 2026-09-15): the same form runs at
`https://<review-host>`, one Cloudflare Worker behind Cloudflare
Access (one-time code by e-mail). The authenticated address selects the
packet; the page autosaves the draft to the worker and a „Prüfung abgeben“
button submits the same `fabrication-pilot-review-v01` document. Build with
`scripts/pilot_site.py build`, read results back with `status` and `fetch`,
then import as before. See `hosting/pilot-review/README.md`. This replaced
the mailed zips after a reviewer opened `review.html` from inside the zip and
the scans did not load; it also removes the export-and-mail-back step.

The form is German and written for transcribers, not programmers
(`harness/pilot_review.{html,css,js}` plus `pilot_review_core.js`, rendered by
`harness/pilot_html.py`). All reviewer-facing copy was rewritten for plain
language on 2026-09-12 (GPT-6 Astra pass, reviewed by hand): short sentences,
one action per sentence, the scan named as the reference in every question
("Steht das so im Scan links?"), no technical vocabulary. It shows one unit at
a time ("Aufgabe 3 von 12") with the scan beside three steps, plus a short
intro with a purpose sentence and optional examples.

Step 1 lists every highlighted span as a card with a little grey context and
asks **Steht das so im Scan links?** with **Ja / Nein / Teils / Weiß nicht**;
after **Nein** the five reasons appear with a one-line explanation each
(Lesefehler, Nur die Schreibweise, Steht woanders, Erfunden, Wiederholung).
**Teils** is for mixed spans (part on the page, part not, the typical case
being a VLM preamble glued to real transcription): the schema label stays
`gt_or_image_uncertain`, and the form adds `{"candidate_id", "mixed": true,
"text"}` to a `notes` list with an optional free remark. The importer ignores
`notes` and the per-unit `unit_note`; the coordinator reads them from the raw
returned JSON for the label-guide revision. Reviewers are told explicitly not
to answer **Erfunden** for a whole span because one part is unsupported. Yellow
is explained as a review aid, not a verdict. The mapping to the schema labels
lives in `SPAN_LABEL_UI`; reviewers never see the identifiers.

Step 2 is the entity list. Each candidate word shows one row of answers,
**Steht so im Scan / Steht nicht im Scan / Weiß nicht**, plus a fold-out with
its surrounding text. A word with no answer is exported as `not_entity`; an
invented name gets **Steht nicht im Scan** (`fabricated`). A small **Doch kein
Name** button undoes an answer. An earlier version used a checkbox ("this is a
name") followed by the question; test readers asked what the checkbox was for.

Step 3 ("Der Rest des Textes") shows the complete hypothesis. Spans that have
been answered in step 1 turn grey and keep their number; unanswered ones stay
yellow. The question is **Steht der Rest so im Scan links?** with a **Ja**
answer that also covers "no entity missing in step 2" and a **Nein** answer
that opens the report control: drag over the text, click **Markierte Stelle
eintragen**, say whether it is a passage or an entity. Answering sets
`full_page_reviewed`; a unit that answered **Nein** stays open until an entry
exists. When automatic spans cover the whole output, only entities can be
added and the answers say so. Selections that overlap an automatic candidate
are refused, which the importer would reject anyway. There is no separate
"read everything first" step; a version that opened with the raw text and an
abstract comparison instruction confused test readers.

The state autosaves in the browser (localStorage, keyed by packet digest); the
file save/load pair sits behind an "An einem anderen Computer weiterarbeiten"
toggle. A live status line per unit lists what is still open, the last unit's
next button reads **Zur Abgabe**, and submission errors scroll to the missing
field or the open-task list. Only **Datei für die Abgabe speichern** writes the
final `annotations-<packet>.json`; it refuses until every unit is complete, and
drafts are rejected at import. The machine-made silver reference is hidden
behind a toggle so it is not mistaken for ground truth.

**Open label-guide question surfaced while preparing the packets.** One VLM
output begins with conversational wrapper text ("Hier ist die transkribierte
Version des historischen deutschen Dokuments: ```") before any transcription.
Neither the metric design nor the normalizer treats such program-added text
specially, so it is scored like any other hypothesis text and the candidate
generator highlights it (in that unit the whole output is one unsupported span).
The label guide has no category for it. For the pilot the form tells reviewers
that program-added sentences are not on the page and count as `fluent_fabrication`
("Erfunden"); whether wrapper text deserves its own label or an ingest-time strip
is a question for the label-guide revision after the pilot, not a change to make
during it.

Check progress and import returned annotations:

```sh
uv run python -m harness.pilot status \
  --pilot-dir evals/calibration/20260906/pilot
uv run python -m harness.pilot import \
  --pilot-dir evals/calibration/20260906/pilot \
  --annotations /private/path/reviewer-one.json \
  --annotations /private/path/reviewer-two.json
```

Import verifies packet, image, hypothesis, and candidate bindings. Missing
reviews stay pending. Disagreements require a separate resolver record; pass
it with `--resolutions`. Existing completed forms are preserved. An exit code
of zero means the command completed; inspect its reported status before
calling the pilot complete.

Status checks validate completed forms in `pilot/coordinator/adjudications/`.
If you import to a custom `--out` directory, that directory is outside this
default progress check.

Two independent humans review every complete output, including outputs with
no highlighted span. Highlights are aids, not a filter. Add missed spans and
entities. Use the scan as the authority: the displayed silver reference is
machine-generated and can be wrong. Retain uncertainty when the image cannot
support a defensible decision. A third human resolves disagreements.

Model-generated labels may exercise software tests but cannot count as pilot
observations or official adjudication. The benchmark author cannot be the
sole reviewer. Record full-output completion explicitly for each unit.

The existing draft schema assigns one primary label to each automatic span.
It cannot split a highlighted span into smaller, differently labeled parts.
If a mixed span cannot receive one defensible label, retain uncertainty and
record separate feedback for the label-guide/schema revision. Do not label
an entire mixed block fabricated merely because one part is unsupported.

After the reviews, report missed candidates, candidate review volume, class
counts, exact and label agreement, pooled kappa, and uncertainty. Revise only
the label guide and candidate-recall machinery from this pilot. Record changes
and rerun deterministic calibration before freezing the candidate version.

T3 tolerances require a separate archival-harm decision. Do not choose them
from engine percentiles or to make a preferred engine pass. The protocol
amendment remains pending until calibration, human review, and ratification
are complete.

## Pilot v1 result (2026-10-09)

Both reviewers submitted all 12 units, each marked fully reviewed (reviewer 2 on
2026-09-15, reviewer 1 on 2026-10-01). The importer marks all 12 units as needing
a third resolver; no adjudication was written.

| Measure | Reviewer agreement | Cohen's kappa |
|---|---|---|
| Span labels (20 highlighted spans) | 9/20 (45%) | 0.15 |
| Entity labels (315 highlighted words) | 10/315 (3%) | 0.01 |
| Entity, collapsed to "in the scan" vs not | 75% | 0.05 |

Added spans: reviewer 1 added 5, reviewer 2 added none. Neither added entities.

**Entity finding: the question, not the data.** The form told reviewers to
answer only for a real name, place, date, amount, number, or identifier, and to
leave other words blank ("Ohne Antwort heißt: kein Name"); an invented name was
to be answered "Steht nicht im Scan". Reviewer 1 left 311 of 315 words blank and
confirmed on 2026-10-09 that these words were not names or places. Reviewer
2 answered most of them: 219 "not in the scan", 83 "in the scan". The two
reviewers therefore disagree on whether a name-like word in the machine output is
"a name" at all, before any question of whether it is on the page. Both
behaviors follow the instruction. The blank answers are deliberate judgments,
not skipped items.

**Span finding.** Reviewer 1 labels more spans as invented text (15 vs 8) and
fewer as reading errors (1 vs 9). The line between a badly misread passage and
invented text is not clear enough in the label guide.

Revisions for pilot v2 (label guide and form only):

1. Ask about every highlighted word without the "is it a name" gate: does this
   name, place, date, or amount appear at this position in the scan? Offer
   "Kein Name, nur ein Wort" as an explicit answer, never as the blank default.
2. Store a blank as unanswered, not as `not_entity`.
3. Give one worked example each for "Lesefehler" (the page has a word there,
   the program misread it) and "Erfunden" (nothing on the page supports it).
4. Keep the machine text in the scan's line breaks so reviewers can count
   lines (reviewer 2 feedback, 2026-09-16).

Open: the third-resolver pass over the 12 units. Two independent humans have
reviewed, so the author resolving them is not a sole-reviewer decision.

## How to run pilot v2 and the T3 review (2026-10-25)

Form v2 implements the four revisions above:

- Step 2 asks about every highlighted word: **Steht so im Scan / Steht nicht
  im Scan / Kein Name, nur ein Wort / Weiß nicht**. No answer is a default.
- A word without an answer stays unanswered and blocks submission. It is never
  exported as `not_entity`.
- "Lesefehler" and "Erfunden" each have one worked example under the reason
  and in the intro, plus a rule to tell them apart.
- The machine text keeps the engine's line breaks. Packets carry display-only
  `line_breaks` offsets; v1 packets without them still load.

The same reviewer pages serve gold packets. Gold packets set
`reference_source: gold`, and the form then labels the reference as a human
transcription.

### Pilot v2

1. Export the 12 silver units with a fresh seed, so the order differs from v1:

   ```sh
   uv run python scripts/prepare_fabrication_pilot.py \
     --run-dir evals/silver/20260709-111024_tess \
     --run-dir evals/silver/20260709-124230_kraken_fresh \
     --run-dir evals/silver/20260709-125244_calamari_fresh \
     --run-dir evals/silver/20260709-154516_evovlm2 \
     --out evals/calibration/20261025/pilot-v2 --seed 20261025
   ```

   Done on 2026-10-25: 12 units, 20 span candidates, and 316 entity
   candidates per packet (v1 packets: 315). Every unit keeps all of its
   output lines.
2. Build the hosted site from the new pilot directory, set `REVIEWERS` to the
   two new packet IDs, and deploy (see `hosting/pilot-review/README.md`).
   Drafts from v1 do not carry over, because the packet digests changed.
3. Read the submissions back with `scripts/pilot_site.py fetch` and run
   `harness.pilot import` with both files. Keep the order of the two files
   fixed from here on: reliability is pooled over one ordered reviewer pair.

Built on 2026-10-26: reviewer 1 has packet `u_4e0df499c1e99541b80f3799`,
reviewer 2 has packet `u_9ebea67b57c2adf8b45b2eaa`; import in that order. The
owner's address maps to reviewer 1's packet for a login test only. Reviewer 2
reviewed v1 under the same address, so the v1 draft and submission of that
address are still in KV. The worker no
longer serves a draft whose packet differs from the mapped one, but
`fetch` reads `submission:<email>:latest`: check that the printed packet is
the v2 packet before importing. Reviewer 1's start is ready now; reviewer 2
starts on 2026-11-07.

Wording fix on 2026-10-29: the "Lesefehler" example said that each word in the
machine text matches one word in the scan. Reviewer 1 asked whether a misreading
with split or merged words still counts as "Lesefehler". The example now says
that the reviewer must recognize the place in the scan, and that the word
count does not need to match. Reviewer 1 got the same answer by e-mail. The
site was rebuilt from the same pilot directory. `packet.json`, the images, and the
packet hashes did not change, so autosaved drafts still load.

Wording fix on 2026-11-03: Reviewer 1 asked how to answer step 2 when an entity
candidate is a fragment of a common word, or two common words merged into one.
The answer is "Kein Name, nur ein Wort" (`not_entity`), even when the letters
match the scan. The reviewer records the misreading in step 1 or step 3. If the
scan has a real name at that place, the reviewer judges that name. The step 2
instruction now asks first whether the word is a name at all, and the examples
name fragments and merged words. Reviewer 1 got the same answer by e-mail. The
site was rebuilt and deployed the same way as on 2026-10-29; drafts still load.

Wording fix on 2026-11-04: Reviewer 1 read "the letters do not matter" as a rule
for names too, and asked whether step 3 checks only for missing or extra lines.
Step 2 now says that a name must match the scan letter for letter; otherwise
the answer is "Steht nicht im Scan". The examples add a one-letter case.
Step 3 now says that misread text counts, not only missing or extra lines, and
that one long wrong passage can be one marked place. Reviewer 1 got the same
answer by e-mail. The site was rebuilt and deployed; drafts still load.

### Resolver pass

The resolver page shows one unit at a time: the scan, the machine text, and
reviews A and B side by side with disagreements marked. Agreed labels are
locked. Each pair of reviewer-added claims gets one consensus boundary that
overlaps every proposal. The page writes only resolved disagreeing units, so
agreeing units keep a null resolver.

1. Build the page, either locally or for the hosted site. Pass the review
   files in the import order:

   ```sh
   uv run python -m harness.pilot resolver --pilot-dir <pilot> \
     --annotations <review-1.json> --annotations <review-2.json>
   uv run python scripts/pilot_site.py build-resolver --pilot-dir <pilot> \
     --annotations <review-1.json> --annotations <review-2.json>
   ```

   The local page goes to `<pilot>/coordinator/resolver/<bundle_id>/`. The
   hosted page is served at `/resolve/` to the address in the `RESOLVERS`
   secret.
2. Resolve every disagreement against the scan. Enter a resolver ID that
   differs from both reviewers. Click **Download resolution file**, or read
   the hosted autosave with `scripts/pilot_site.py fetch-resolution`.
3. Import with the resolution. Pass `--allow-existing`, because the first
   import already wrote the agreeing units:

   ```sh
   uv run python -m harness.pilot import --pilot-dir <pilot> \
     --annotations <review-1.json> --annotations <review-2.json> \
     --resolutions <resolution.json> --allow-existing
   ```

   The importer refuses a resolution built for another coordinator map. It
   leaves a unit pending when the resolver matches a reviewer.

The pilot v1 resolver pass uses the same commands on
`evals/calibration/20260906/pilot`; all 12 v1 units disagree. Deployed on
2026-10-25 as bundle `r_60564cbfc45f63d838eca92b` at
`https://<review-host>/resolve/`, mapped to the owner's
address. The reviewer packets on the site did not change.

The page is German and asks one question at a time, in the reviewers' own
words. Reviewers A and B appear as two answer buttons. Other answers sit
behind „Etwas anderes entscheiden“. Keys: `A`, `B`, and the arrow keys.

### T3 review of the sealed gold run

Do not export or deploy gold packets until pilot v2 shows that the revised
form works.

1. Check the run without writing anything. The dry run validates the recorded
   selection, the freeze manifest digest, every frozen image hash, and every
   stored score, and prints counts only:

   ```sh
   uv run python -m harness.pilot export-gold \
     --run-dir evals/own_gold/runs/20261025-065703_gate1_run11_sealed \
     --engine gate1_run11_s800 --dry-run
   ```

   Result on 2026-10-25: 53 units, 76,856 normalized hypothesis characters,
   162 span candidates, 3,567 entity candidates, one loop-guarded page, no
   failed outputs.
2. Export with a fresh seed to a git-ignored path. The command refuses any
   other path. Pass `--engine` once per engine to mix engines in one random
   order.

   ```sh
   uv run python -m harness.pilot export-gold \
     --run-dir evals/own_gold/runs/20261025-065703_gate1_run11_sealed \
     --engine gate1_run11_s800 --seed <fresh-seed> \
     --out evals/own_gold/t3/<date>
   ```

3. Host the two packets as for the pilot. `pilot_site.py build` replaces the
   pilot packets in the asset tree. Two independent reviewers review all 53
   pages; the owner resolves and is not a sole adjudicator.
4. Import into the run, so that scoring reads the forms:

   ```sh
   uv run python -m harness.pilot import --pilot-dir evals/own_gold/t3/<date> \
     --annotations <review-1.json> --annotations <review-2.json> \
     --resolutions <resolution.json> --allow-existing \
     --out evals/own_gold/runs/20261025-065703_gate1_run11_sealed/adjudications
   uv run python -m harness score \
     --run-dir evals/own_gold/runs/20261025-065703_gate1_run11_sealed
   ```

   `harness.pilot status` checks only the default coordinator directory, so
   read the scorer's `invalid_adjudications` after a custom `--out`.

Gold packets, the coordinator map, and the resolver page contain gold text,
scans, and page identity. Keep them under `evals/` and behind Access. Remove
the site assets, the KV namespace, and the Access application when the review
is over.

**Risk.** With no default answer, each reviewer must answer every entity
candidate: 3,567 on the gold run, about 67 per page. Decide before the gold
export whether that workload is acceptable or whether the entity extractor
needs a precision pass first.
