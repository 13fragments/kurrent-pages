# BENCHMARK_PROTOCOL.md

**Version: 0.1-freeze (2026-07-05). Written and versioned BEFORE any ground truth
existed and BEFORE any engine was run (VISION §11 hygiene, §18 Step 4). Amendments
after this point are logged in §10 with date + reason; amendments after the first
engine run are marked as such and cannot change the kill criterion (§8).**

The author competes in this benchmark (VISION §6). Every judgment-bearing choice —
transcription conventions, normalization, thresholds, prompts — is therefore fixed
here, in advance, in writing.

---

## 1. Scope and assets

* **Gold v1 set:** 53 scored pages + 2 unscored fabrication-probe annex pages,
  defined page-by-page in `gold/selection.yml` (IDs G01–G52b, A01–A02). Selection
  provenance, constraint audit, and alternates live there; sourcing decisions in
  `gold/candidates.yml`.
* **Images under test:** private evaluator path
  `<evaluation root>/data/benchmark_gold/v1_pages/{GID}.jpg` — processed single pages
  (spreads split to a designated scored side, facing-page slivers cropped, native
  resolution). Frozen by SHA-256 in `gold/v1_pages.sha256`. Engines receive exactly
  these images; no other preprocessing is permitted per engine.
* **Strata (7 + contrast):** degraded_fraktur, tidy_kurrent, ugly_kurrent,
  suetterlin, table_registry, marginalia, mixed_print_handwriting, plus
  twentieth_century_kurrent / nineteenth_c_civilian / latin_cursive_1940s as
  reporting cuts. clean_fraktur ships EMPTY in v1 (§9 note 1).
* **Task:** end-to-end page → text. Raw page image in, transcription out.
  Segmentation failures count against the pipeline, not the page (VISION §6).

## 2. Ground truth production

1. **Transcriber:** the author, **or vetted external transcribers under the
   double-keying model below** (amended 2026-07-09). Tooling: side-by-side image +
   text editor; the full-resolution source (not a downscale) must be displayed.
2. **Two passes → independent double-keying (amended 2026-07-09).** Original plan:
   the author transcribes, then self-reviews ≥7 days later. Superseded for the 38
   non-early-modern Kurrent/Sütterlin pages by **two independent external keyings**
   (the primary keyer and the second keyer, each keying all 38 from scans +
   Regelblatt, neither aware of the other) followed by **author adjudication of every
   disagreement against the scan** — a stronger form of the two-pass check (true
   independence). The author still keys the 5 Fraktur + 2 Latin-cursive pages
   directly (two self-passes ≥7 days apart); the 8 early-modern pages await a
   specialist. **Hard ordering still holds: all GT
   completed before any engine output is viewed.** External transcribers are bound by
   a confidentiality/no-tools agreement retained in the private evaluation repository;
   this preserves the §7 contamination controls (no upload to OCR/HTR/AI/cloud).
3. **Per-page metadata recorded at transcription time:** final folio label (if on
   the scan), license string, hand attribution notes (Hainspach: verify member
   hands per §9 note 3), any new caveat discovered.
4. **Uncertainty is explicit:** characters the transcriber cannot resolve are
   marked (§3.4); passages nobody could read are abstention-marked, and those
   regions are scored as abstention targets (§5.6).
5. **Entity annotation:** after the text passes, each page gets a gold entity list
   (`<evaluation root>/data/benchmark_gold/entities/{GID}.yml`): persons, places,
   dates, each with the diplomatic
   surface form and a normalized form (§5.5).

## 3. Transcription conventions — diplomatic layer

The diplomatic layer records what is on the page, one deterministic reading per
mark. Conventions differ for print vs handwriting where the script demands it.

### 3.1 Characters

| Phenomenon | Print (Fraktur/Antiqua) | Handwriting (Kurrent/Suetterlin/Latin) |
|---|---|---|
| Long s | keep `ſ` | all s-forms → `s` (positional variants, not orthographic) |
| ß | keep `ß` | keep `ß` |
| Umlauts incl. superscript-e forms | as printed (`ä ö ü`) | modern `ä ö ü` regardless of diacritic shape |
| Ligatures (ch, ck, tz, ff…) | dissolve to component letters; keep `ß` | n/a (cursive joins are not ligatures) |
| Round r, letter variants | normalize to `r` etc. | normalize to modern letter identity (e.g. `ÿ` → `y`; descender I/i is a variant of `I`/`i`, not `J`/`j` — a hand's genuine I-vs-J distinction is kept) |
| Abbreviations | keep unexpanded, as printed | keep unexpanded; nasal bar → macron on carrier (`ē`); other suspension marks → `'` (non-standard marks only — loops/hooks/flourishes; a period, colon, or other written punctuation glyph used as an abbreviation mark is kept as written — `.`, `:`) |
| Superscript / underlined abbreviation letters (`Dr`, `No`, `Hrn`) | baseline, plain (super/underline not encoded) | same — baseline, plain; abbreviation unexpanded |
| Numbers, currency | as written (`RM`, `K`, `Fr`, `Cts`, `fs`; florin/Gulden → `f'`) | same |
| Virgel `/` and historical punctuation | as written | as written |
| Capitalization, spelling, dialect | exactly as written (incl. Platt, Bergisch verse, historical/erratic spelling) | same |

Two separate items on one physical line with a lateral gap (e.g. sender left /
place-date right in a letterhead) are transcribed on a single line in reading order,
separated by one space; the ` | ` cell separator is reserved for tables/registers
(§3.2.2). Word spacing normalizes to single spaces. Line breaks are preserved as `\n`;
end-of-line hyphenation marks are kept as written (`-`, `=`); no dehyphenation in
the diplomatic layer.

Struck-through but readable text is transcribed at its position wrapped `⟪D: …⟫`
(deletion marker; content scored, glyphs stripped per §3.3); deletions that cannot
be read → `[unleserlich]`. Leading indentation and other outer text shape are not
encoded: every line starts at column 0. (Added 2026-07-14, §10.)

Punctuation attaches as in the original: a mark written on the word attaches
without a space; a free-standing mark (Virgel `/`, a free-standing period) takes a
space on both sides. Where comma vs Virgel cannot be decided safely: stroke form,
then the hand's dominant practice on the page, else Virgel. Vertical gaps between
text blocks are not encoded — no blank lines; the next block simply starts on the
next line. (Added 2026-07-16, §10.)

Closing/section marks without letter or punctuation value (end-of-recipe flourishes,
compound signs such as `~:·`, `°/.`) are not drawn in glyphs; they are encoded as the
uniform placeholder `⟪Z⟫` at their position, free-standing (space before), also where
the mark is only probably a closing sign; `[unleserlich]` stays reserved for unread
text, and a serious letter/abbreviation reading goes in `⟦ ⟧` instead. A full
superscript `o` over `u` → `uͦ` (U+0366; fallback `u` + superscript o, unified at
ingest like U+0364); the bare u-bow (the u/n distinguishing hook) is not encoded, and
a ring that is not clearly closed counts as a u-bow → plain `u`. Line-end strokes
that are not hyphenation (filler/continuation `=`, `-`) are kept as written and
attach like punctuation (on the word: no space; free-standing: space before); a
merely doubtful stroke with no letter value is not encoded. (Added 2026-09-03, §10.)

Word boundaries follow the word, not the gap: a pen lift inside a word is not a
space. Punctuation is encoded only where visible: a missing or cropped period is
not supplied (no `⟦ ⟧`); a clearly written period stays even mid-sentence or as an
evident slip; a doubtful speck is not encoded. Diacritics with letter value stay
(`š` in Czech names; fallback `s^`, unified at ingest). Ditto marks as written
(`-"-` or `"`, straight U+0022, space before). Meaningful signs are not `⟪Z⟫`: the
death cross → `†` on its own line at its position (§3.2.7). Spaced dot runs as
printed or written (`. . .`), never U+2026. Keyer files: UTF-8 without BOM,
consistent line ends; a scan holding two pages is keyed left page, then right page,
no page-break marker. (Added 2026-09-28, §10.)

The doubling stroke over m/n is an overline on its carrier like the nasal bar
(`m̄`, `n̄`; never expanded to `mm`/`nn`; fallback `m^`, unified to U+0304 at ingest).
A word-final loop standing for a missing ending is a suspension mark `'`. A
continuous strike over several words takes one `⟪D: …⟫`; unstruck punctuation stays
outside. A struck letter inside a word is marked in place without spaces
(`Garten⟪D: e⟫`); an overwritten letter is keyed as its final form only. Number
separators as written (raised stroke → `'`). (Added 2026-10-09, §10.)

### 3.2 Regions and linearization (defines gold reading order)

GT is a single text sequence per page, linearized deterministically:

1. **Main text** in reading order: columns left→right, top→bottom within column.
2. **Tables** (table_registry pages): row-major — header row first, then data rows
   top→bottom; cells left→right separated by ` | `; one row per line. Empty cells
   → `|` with nothing between separators. Carry-forward rows (`Transport`)
   transcribed like any row. Every row carries all cells (n−1 separators); a cell
   spanning several rows goes in the first row of the group, empty below; stacked
   entries in one cell → one line each; a split amount column (francs | centimes,
   Mark | Pfennig) puts the separator dot in the left cell (`31. | 75`). (Details
   added 2026-09-28, §10.) Lines of running text with an amount at the right edge
   are text, not a table (one line, one space). Text left of a table row is its
   own line before the row, text starting right of it its own line after
   (§3.2.7 placement). Calendar/diary layouts with year and weekday columns are
   not tables: year and weekday start the entry's first line; a narrow note column
   is unkeyed marginalia (as the Petri index column). (Added 2026-10-09, §10.)
3. **Marginalia:** keyed notes (insertion caret / matching mark) are transcribed
   at their anchor point inline as `⟪M: …⟫`; unkeyed margin notes/columns follow
   the main block they accompany, each line prefixed `⟪M⟫ `. The Merian/Hainspach
   amount columns and Petri index column are unkeyed marginalia. A margin note
   never moves to another page: if its paragraph continues overleaf, the note
   follows the paragraph's last line on the note's own page. (Added 2026-09-28.)
   Keyed text that stands elsewhere in the text block (not in the margin) also
   moves to its anchor as `⟪M: …⟫`; the reference marks themselves (e.g. `+`) are
   not encoded. A date or sign inside an unkeyed note belongs to that note: its
   own `⟪M⟫` line after the note line it stands beside. (Added 2026-10-09.)
4. **Stamps and printed form labels** (Wanderbuch, Feldpost cards): transcribed in
   reading-order position, prefixed `⟪S⟫ ` for stamps. Printed + handwritten fills
   are transcribed in visual sequence (label then fill).
5. **Unscored regions:** photographs, drawings, pasted pictures, decorative
   vignettes → `⟪G⟫` (graphic placeholder, unscored, VISION §12 / graphics
   protocol), on its own line at the image position; text beside an image follows
   it (image left) or precedes it (image right), line by line (added 2026-09-28). Pasted PRINT on a handwritten scored page (G40's typed Programm was
   split away; if residual print fragments appear) → `⟪P: unscored⟫`. Closing/section
   flourishes without letter or punctuation value → `⟪Z⟫` (unscored placeholder;
   §3.1, added 2026-09-03).
6. **Facing-page or neighbor-leaf fragments** surviving crops: NOT transcribed;
   they are outside the page.
7. **Later-added foliation/pagination** (archival hands) and **marginal
   section/enumeration marks** (single letters or numerals labelling sections):
   transcribed at their reading-order position as their own unmarked line — left
   of a text line: before it; right of it: after it; between two lines: after the
   upper. The page is scored as it stands, regardless of hand, writing tool, and
   date of the addition (e.g. a pencil `X` in a corner → own line `X`).
   (Added 2026-07-14; section marks and placement rule 2026-09-03; other-hand
   marks 2026-09-28, §10.)
8. **Tie-break:** a mark whose row or column cannot be decided belongs to the upper
   line and the left column (a ditto mark between two lines → upper line; a mark
   between two columns → left column). (Added 2026-09-28, §10.)

### 3.3 What is scored

Everything in the linearized sequence except `⟪G⟫`/`⟪P⟫`/`⟪Z⟫` placeholders and region
marker glyphs themselves. Region markers exist for alignment bookkeeping and are
stripped symmetrically from gold and hypothesis before metric computation.
`⟪D: …⟫` deletion markers behave like keyed `⟪M: …⟫`: the struck content is
scored, the marker glyphs are stripped.

### 3.4 Uncertainty and abstention in GT

* Uncertain reading, best guess recorded: `⟦word⟧` (scored normally; flagged for
  the correction-time analysis).
* Illegible to the transcriber: `[unleserlich]` covering the illegible span
  (abstention target, §5.6). Used sparingly; the set was selected to be
  hard-but-humanly-readable.
* Letters physically missing (paper damage, holes) are never reconstructed, even
  when the reconstruction is unambiguous: partially preserved but clearly
  identifiable letters count as readable; fully missing spans → `[unleserlich]`,
  including word-internally. The reference contains exactly what is visible on
  the page. (Added 2026-07-15, §10.)

## 4. Normalization layer (derived, never hand-edited)

Mechanical, scripted, reproducible (`harness/normalization/`); applied identically
to gold and hypothesis:

1. `ſ` → `s`; unpack any residual ligature codepoints.
2. Dehyphenate line ends: a `-`, `=`, or `⸗` directly before a line break never counts.
   Directly after a letter it is a hyphen and joins the two halves of the word; after
   anything else (a filler or continuation stroke, §3.1) it is dropped and the words stay
   apart (§10 2026-10-17). Then `\n` → space.
3. Strip region markers `⟪…⟫` wrappers (keep contained marginalia text; drop `⟪G⟫`, `⟪Z⟫`).
4. Unicode NFC; collapse whitespace.
5. Lowercase — **only** in the additional `cer_norm_lc` variant; the primary
   normalized metric is case-sensitive.
6. No abbreviation expansion, no spelling modernization in v1 (kept for a possible
   future "modernized" layer; would require its own rules file).

CER/WER are reported on BOTH layers (VISION §11): `cer_dipl` / `cer_norm` (+ WER,
NLS on normalized).

## 5. Metrics (all pre-registered)

Per page, then aggregated per stratum (median and mean) and overall. All code in
`harness/scoring/`, public.

1. **cer_dipl, cer_norm, wer_norm, nls_norm** — character/word error rate via
   global alignment (Levenshtein) of full linearized page text; NLS for CHURRO
   comparability.
2. **Reading-order cost:** `cer_norm` minus order-insensitive CER, where the
   order-insensitive variant optimally assigns hypothesis lines to gold lines
   (Hungarian matching on line-level Levenshtein, unmatched lines counted whole).
   Reported as `ro_cost` (≥ ~0); isolates ordering vs recognition errors.
3. **Fabrication rate (headline):** from the character alignment, insertion runs
   ≥ 5 consecutive words that align to nothing in gold = fabricated spans.
   `fab_rate` = fabricated characters / hypothesis characters. Reported with
   examples; release-gating per VISION §12.
4. **Segmentation-failure rate** (pipeline engines): fraction of pages with
   `cer_norm` > 0.75 or empty output — the "visibly collapsed" operationalization.
5. **Entity recall / precision (headline):** gold entities (person, place, date)
   matched against hypothesis text: an entity counts as recalled if its normalized
   form (or any recorded variant) appears in normalized hypothesis within
   Levenshtein distance ≤ 1 per token (dates: exact after digit normalization).
   Precision counterpart: capitalized-token n-grams in fabricated spans that look
   like person/place names, manually adjudicated for the report (count published
   with the adjudication list).
6. **Abstention behavior:** over gold `[unleserlich]` spans and the 2 annex pages:
   correct behavior = abstention marker / empty output / explicit "illegible"
   statement; failure = fluent invented text. `abstention_ok` fraction +
   hallucinated-character count on annex pages.
7. **Correction-time proxy:** normalized CER bucketed (<5%, 5–15%, 15–30%, >30%)
   as a stand-in; actual timed correction only if a later gate needs it.

## 6. Engines and settings (v0)

Per VISION §6 table: Kraken (+ community Kurrent/German models), PyLaia,
Calamari/OCR-D Fraktur, Tesseract Fraktur, Qwen3-VL-4B (8B if practical), CHURRO
(reference), Transkribus (capped budget), optional frontier VLM on unrestricted
pages. For every engine: exact version/model-id/checkpoint, config file, and
runtime logged in `evals/own_gold/runs/`. Each engine runs once per page with the
fixed config; no per-page retries, no prompt tuning after the first scored run.
Token-limited VLM outputs are scored without their trailing loop (§10, 2026-10-16).

**Fixed VLM prompt (pre-registered, used verbatim for all VLM engines):**

> Transcribe this historical German document page exactly as written, line by
> line, preserving original spelling and punctuation. Transcribe tables row by
> row with cells separated by " | ". Include marginal notes where they are
> anchored. If a passage is illegible, write [unleserlich] instead of guessing.
> Do not translate, modernize, or add any text that is not on the page. Output
> only the transcription.

A second fixed prompt variant (adding a one-line script hint, e.g. "The page is in
German Kurrent handwriting.") is also pre-registered; both are reported, neither
may be edited after the first run.

## 7. Contamination controls

* Per-page zero-public-text audit trail: `gold/selection.yml` + candidates.yml
  decisions log. One documented-caveat page: **G32** (national brochure title; no
  digitization/edition exists; evidence trail in selection.yml).
* **Distribution policy:** page manifest, source links, SHA-256 hashes, protocol,
  harness, and per-engine scores are public. **Gold transcriptions and entity
  annotations are never published in training-usable form** (no image+text pairs).
  Third parties can reproduce GT from the public source scans if they invest the
  transcription effort — that keeps the benchmark auditable without feeding
  crawlers (VISION §11).
* Freeze integrity: `gold/v1_pages.sha256` covers all 55 images; any page swap
  after this version is a logged amendment (§10) and only from the pre-verified
  alternates list.

## 8. Gate 0 kill criterion (operationalized; frozen)

VISION §6 verbatim: *"If the open CRNN pipelines (Kraken/PyLaia end-to-end,
including their segmentation) handle the ugly-Kurrent and mixed-layout gold pages
at a usable level — defined before the run as gist-readable output plus majority
entity recall — then the model track is killed."*

Operationalization, fixed now:

* **Hard-strata page set:** all pages whose primary stratum is ugly_kurrent,
  suetterlin, table_registry, marginalia, or mixed_print_handwriting (per
  selection.yml `primary` tags).
* **KILL the model track if** any single open CRNN end-to-end configuration
  (one engine + one published model + one config, applied uniformly) achieves,
  on the hard-strata set: **median `cer_norm` ≤ 0.25 AND median entity recall
  ≥ 0.50**, with **segmentation-failure rate ≤ 20%** on that set.
* **Explicitly NOT a kill signal:** Qwen3-VL zero-shot Kurrent near-uselessness
  (expected; VISION §7); CRNN success on print-only strata (conceded territory,
  VISION §5).
* Results are published either way (pass or kill), with per-stratum breakdowns
  and all configs.

Rationale for thresholds: CER ≤ 25% (normalized) is the boundary where output
stops being gist-readable for archival search in practice; entity recall ≥ 50% is
the literal "majority"; the segmentation cap prevents a kill verdict built on a
lucky subset while most pages collapsed.

## 9. Recorded pre-results notes (carried from selection phase)

1. **clean_fraktur SHIPS EMPTY in v1** (decisions_log.clean_fraktur_downgrade
   2026-07-03; contamination check 2026-07-05). The only token candidate
   ("Spione, Verräter, Sabateure", KCH-059) failed certification: a Kindle e-book
   edition of the title existed (public machine-readable text), plus an
   unverifiable digitization at CLADE.net. v1 ships 7 strata; clean-Fraktur
   comparability is delegated to the public GT4HistOCR / Reichsanzeiger-GT sets.
   Clean print is a solved problem (<1% CER territory) and carries no headline
   claim.

2. **Suetterlin-cohort precision.** The named-female-hand page G12 (Sr. M. Natalia
   letter, 1924) is an ADULT nun's Kurrent — name-attributed female hand, NOT a
   member of the strict 1905–33 school-Suetterlin cohort. Cohort-level claims
   about school-Suetterlin rest on G08/G09 (Daut, b. 1926) and the 1930s–40s
   Hainspach and Feldpost hands; G12 supports the women's-hand demographic claim
   only.

3. **Hainspach writer attribution** (pre-checked 2026-07-05, preliminary): all
   picked chronicle pages show member/female-hand evidence (all-female officer
   slates incl. Schriftführerin Marie Dittrich 1936; clergy consistently in
   deferential 3rd person; 1st-person passages in female insider voice). No
   priest-hand suspected. Residual: some hands may be the female Leiterin/Schwester
   rather than a lay member — still women's hands; confirm proper-name readings at
   transcription.

4. **Graphics protocol** (decisions_log.graphics_protocol): pure-graphics pages
   are excluded from scoring; embedded graphics (pasted photos/postcards/sketches
   on G40, G52a, G52b and stamps on Wanderbuch pages) are unscored `⟪G⟫`/`⟪S⟫`
   regions; 2 pure-graphics pages (A01, A02) form the UNSCORED fabrication-probe
   annex where correct output ≈ abstention.

5. **Spread splitting provenance.** Sources scanned as double-page openings
   (Hainspach, Nimlau, Petri, Daut, Merian) were split into halves with a 4%
   gutter overlap; exactly ONE designated side per gold ID is scored (mapping in
   `gold/selection.yml` processed_pages). Scoring uses the designated single page;
   the other half is context only.

6. **Resolution provenance.** Picked pages from gda.bayern.de (Hainspach, Nimlau),
   e-manuscripta (Merian), and SLUB App.3395 were re-downloaded at native
   resolution (up to 5000px wide) into `<source>/fullres/`; the original bulk
   downloads of those sources are lower-resolution derivatives and must not be
   used for GT.

7. **Dialect content.** Several Feldpost picks (G02, G03) contain Solingen
   Platt/dialect German; KCH-060 newsletters contain Bergisch dialect verse.
   These are in-scope difficulty, not errors; transcription follows §3 exactly as
   written.

8. **zero_public_text applied to national print** (2026-07-05). Mass-printed
   national titles get a stricter reading than local one-offs: OKW
   "Kriegsgefangene" was swapped out of the set even though no public TEXT exists —
   the exact page is a free 300-dpi image download at WLB Stuttgart, and "no OCR
   today" is not a defensible freeze claim (same logic as the SBB Feldzeitung
   exclusion). The one retained national-title page, G32 "Was tue ich im
   Ernstfall?" S.24, is documented with its evidence trail: no digitization of the
   booklet exists anywhere found; the only public content is slogan-level
   quotation in the exile press (Sozialistische Warte, 02.05.1940, pp. 282–283 —
   press-version wording, verified non-identical to the page body); page-level
   phrase probes against the 34.8M-page DDB Zeitungsportal OCR returned zero hits.
   This is the set's single documented-caveat page; all 52 others are
   one-off/local/private items.

## 10. Amendment log

* **2026-07-08 — explicit primary-stratum metadata.** Added `primary` fields to
  multi-tag `gold/selection.yml` entries and corrected the primary-count table so
  the §8 hard-strata set is deterministic. No page IDs, images, hashes,
  transcription conventions, metrics, or thresholds changed.
* **2026-07-09 — GT production: independent double-keying (§2).** The 38
  non-early-modern Kurrent/Sütterlin pages are transcribed independently by two vetted
  external transcribers (a primary keyer and a second keyer; both key all 38) and
  adjudicated by the author against the scan, replacing the author's self-two-pass for those pages.
  Author still self-keys Fraktur (5) + Latin cursive (2); early-modern (8) pending a
  specialist. Rationale: independent double-keying is a stronger error check than one
  keyer twice; the trials showed real cross-keyer disagreements (Bolsche/Bolche/Bolehe,
  mir/ihr, gr/pr) a single key would have baked in. Contamination controls preserved via
  the signed no-tools/confidentiality agreement. No page IDs, images, hashes, metrics, or
  thresholds changed; hard GT-before-engine ordering unchanged. Release/versioning
  decided 2026-07-09 — see §11.
* **2026-07-09 — release policy + versioning decided (§11).** GT stays **private**
  (held-out evaluation, no public GT) to preserve the §7 contamination controls.
  Versioning: a provisional single-key build (the second keyer's, ready first) may be
  produced but is labeled **v0.9 provisional**, never v1.0; **v1.0 = the adjudicated double-keyed GT**;
  scores are comparable only within a version.
* **2026-07-09 — two convention clarifications (§3.1/§3.2), no rule reversals.**
  Surfaced by a trial transcriber's questions on G05/G50. (a) Superscript/underlined
  abbreviation letters (`Dr`, `No`) → baseline plain, abbreviation unexpanded.
  (b) Two laterally-separated items on one line (letterhead sender/date) → one line,
  reading order, single space; `|` stays table-only. Both fill gaps in the spec
  rather than change an existing ruling; existing trial pages already conform
  (Dr/No were rendered plain by both transcribers). Mirrored into the provider
  private provider Regelblatt. No page IDs, images,
  hashes, metrics, or thresholds changed. GT not yet produced.
* **2026-07-10 — source/hand-cluster reporting metadata.** Added explicit
  `hand_cluster` identifiers to `gold/selection.yml` for already documented repeated
  writers and a source-qualified fallback for all other hands. Rationale: raw labels
  such as “same hand” could merge unrelated collections, while variant descriptions
  of Raimund Daut, Hermann Petri, and other repeated writers could split one writer.
  This changes only the descriptive hand-cluster sensitivity analysis introduced by
  the fabrication implementation draft; no page IDs, images, image hashes, GT,
  transcription conventions, metric numerators, kill criteria, or T3 thresholds
  changed. Logged after silver validation and before gold scoring. The separate
  fabrication metric/T3 amendment remains pending its blinded pilot.
* **2026-07-14 — three convention clarifications (§3.1/§3.2/§3.3), no rule
  reversals.** Surfaced by the early-modern specialist's pre-work questions on the
  1565–1641 pages. (a) Struck-through readable text → transcribed in place, wrapped
  `⟪D: …⟫` (new deletion marker; content scored, glyphs stripped like `⟪M⟫`/`⟪S⟫`;
  transcriber fallback `((D: …))`); illegible deletions → `[unleserlich]`.
  (b) Indentation/outer text shape not encoded — lines start at column 0.
  (c) Later-added foliation/pagination transcribed at reading-order position as its
  own line. All three fill spec gaps rather than change existing rulings; no
  delivered transcription conflicts (no D-case pages keyed yet). Harness updated in
  the same change: `⟪D⟫` added to the §3.3 marker-strip regexes. Mirrored into the
  provider Regelblatt (rules, fallback note, worked example). No page IDs, images,
  hashes, metric definitions, or thresholds changed.
* **2026-07-15 — four convention clarifications (§3.1/§3.4), no rule reversals.**
  Second round of the early-modern specialist's questions. (a) A period written in
  the original always stays `.`, even when functioning as abbreviation mark; `'` is
  reserved for non-standard suspension marks. (b) Descender I/i → `I`/`i` per the
  letter-variant rule (not `J`/`j`); a hand's genuine I-vs-J distinction is kept.
  (c) Letters physically missing through paper damage are never reconstructed —
  partially preserved unambiguous letters count as readable, fully missing spans →
  `[unleserlich]` even word-internally (consistent with the §5.6 abstention design:
  engines are not rewarded for hallucinating invisible letters). (d) `ÿ` → `y`
  (variant rule). (a), (b), (d) apply existing §3.1 rules to concrete cases; (c)
  fills a spec gap. Mirrored into the provider Regelblatt. No harness change
  needed. No page IDs, images, hashes, metric definitions, or thresholds changed.
* **2026-07-16 — punctuation spacing + comma/Virgel tiebreak (§3.1), no rule
  reversals.** Third round of the early-modern specialist's mid-trial questions.
  (a) Punctuation attaches as in the original — attached marks glue to the word,
  free-standing marks (Virgel, free-standing period functioning as comma/Virgel)
  take a space on both sides. (b) Comma vs Virgel undecidable → stroke form, then
  the hand's dominant practice on the page, final fallback Virgel; no special
  marking. (c) Vertical gaps between text blocks → no blank lines (extends the
  2026-07-14 outer-text-shape ruling; the §4 normalizer already drops empty
  lines). Mirrored into the provider Regelblatt. No harness change needed. No page
  IDs, images, hashes, metric definitions, or thresholds changed.
* **2026-07-18 — capitalization tiebreak + overline encoding (§3.1), no rule
  reversals.** Confirmed the early-modern transcriber's provisional rule for
  letterform-undecidable initial capitals: letter form decides first; if it does
  not, uppercase after a free-standing period and for proper names (family/field
  names), else lowercase; word-level uncertainty still → `⟦ ⟧`. Overline encoding:
  transcriber-delivered U+0305 combining overlines are accepted and unified to the
  §3.1 macron form at GT ingest; for a stroke spanning several letters one overline
  on the main carrier suffices. Mirrored into the Regelblatt. No harness change
  (ingest-time normalization). No page IDs, images, hashes, metric definitions, or
  thresholds changed.
* **2026-07-22 — punctuation-glyph retention, florin sign, capitalization exceptions
  (§3.1), no rule reversals.** Fourth round of the early-modern trial questions.
  (a) A colon (and any written punctuation glyph) used as an abbreviation mark is
  reproduced as written (`:`), like the period; only non-glyph suspension strokes →
  `'`. (b) The florin/Gulden sign is rendered uniformly as `f'` (its slanted
  suspension stroke → apostrophe, no separate point). (c) The letterform-undecidable
  capitalization fallback (2026-07-18) also uppercases in headings; generic
  appellative terms (land-type categories such as "kappes garden", "kirch bodem") are
  common nouns, not proper names → lowercase. (d) Cross-shaped insertion marks are not
  transcribed as glyphs; the referenced insertion is placed at its anchor (marginal →
  `⟪M: …⟫`). All apply existing rules to concrete cases. Mirrored into the Regelblatt.
  No harness change. No page IDs, images, hashes, metric definitions, or thresholds
  changed.
* **2026-07-23/24 — abbreviation-sign taxonomy, text-frame lines, superscript-e
  umlauts (§3.1/§3.2), no rule reversals (logged 2026-07-28).** Fifth and sixth
  rounds of the early-modern specialist's questions (trial acceptance + recipe-book
  pre-work). (a) The `'` suspension rule keys on glyph status, not appearance:
  letter-LIKE suspension signs that are not letters of the word (the common 'us'
  abbreviation) → `'`; a real alphabet letter written in the line functioning as an
  abbreviation ("dz" for das/daß) stays a letter; where a suspension stroke sits on
  a written base letter, the letter stays and only the stroke becomes `'` (the 'que'
  abbreviation — regular q with a stroked descender → `q'`; florin-sign precedent).
  (b) Single/double ruled lines bounding the text field are outer text shape → not
  encoded (extends the 2026-07-14/16 outer-shape rulings; written glyphs such as the
  `=` line-break hyphen unaffected). (c) An umlaut indicated by a full superscript
  letter e (not a reduced häkchen) → base letter + U+0364 combining Latin small
  letter e (`uͤ oͤ aͤ`), transcriber fallback plain superscript e, unified at GT
  ingest like U+0305; reduced häkchen/dots remain modern `ä ö ü` per §3.1. Also
  clarified: `⟪M: …⟫` encodes marginal *location* only and `⟪D: …⟫` the deletion;
  the lateness of a correction is not separately encoded (an in-line replacement
  after a strike, with its hyphenated continuation outdented at the next line
  start, is plain text at its position). All fill spec gaps or apply existing
  rules to concrete cases. Mirrored into the provider Regelblatt. No harness
  change (ingest-time normalization). No page IDs, images, hashes, metric
  definitions, or thresholds changed.
* **2026-07-28 — Fraktur (5) + Latin cursive (2) outsourced to an external keyer
  (§2 GT production).** The §2 pre-registered default keyed the 5 degraded-Fraktur
  (G28–G32) and 2 Latin-cursive (G52a/b) pages by the author; the author attempted
  the Fraktur first-key and judged their own paleographic reliability on the degraded,
  name-dense wartime prints insufficient for reference GT. These 7 pages are therefore
  reassigned to the vetted external keyer already engaged for the September bulk
  (the primary keyer — the strongest trial performer on convention fit and the only
  one to mark uncertainty, and a Fraktur/type specialist). Keying regime: **single
  external key + author adjudication against the scan** (the author can verify a
  proposed reading against the image even where producing the first draft from blank
  is beyond their reliability). This is a weaker check than the §2 double-key applied
  to the 38 Kurrent/Sütterlin pages, and is recorded as such: these 7 stay
  **single-key + adjudication**, not double-keyed; a second key remains optional
  (e.g. the same keyer's Zweitkorrektur, originally budgeted for these pages).
  Contamination controls unchanged — the outsourcing is gated on the same signed
  no-tools/confidentiality agreement as every other external keyer. Budget delta
  small (author-time + ~€31 Zweitkorrektur → ~€60–85 first-key). No page IDs, images,
  hashes, metric definitions, or thresholds changed; GT-before-engine ordering
  unchanged; GT for these pages not yet produced.

* **2026-09-01 — capitalization: form decides only where the writer had a choice
  (§10; seventh question round).** Refines the 2026-07-18/22 letterform-first rule
  for hands whose letterforms vary without encoding case. (a) Two forms of a letter
  distributed freely over word-initial AND word-internal position (h/H on the
  recipe-book pages) carry no case information — free allographs of one letter →
  the undecidable-fallback applies (lowercase except proper names, sentence start
  after a free-standing period, headings). (b) A distinct form appearing at
  practically every word start regardless of word class (z/Z) is positionally
  FORCED — an allograph like long ſ or descender-I/i, not a chosen capital →
  same fallback; a capital is transcribed only where the hand has an additional,
  genuinely distinct capital form used selectively (a third form contrasting with
  the ordinary initial form). Principle now explicit: letterform decides case only
  where the form choice was free; positional variants are not capitalization.
  Applies the existing fallback to new concrete cases; no rule reversal. Mirrored
  into the provider Regelblatt. No harness change. No page IDs, images, hashes,
  metric definitions, or thresholds changed.

* **2026-09-01 — sentence-start uppercase keys on the free-standing period only
  (§10; eighth question round).** The capitalization fallback's sentence-start
  exception applies only after a free-standing period — never after a Virgel,
  even where the following passage reads like an independent sentence (16th-c.
  pages have no true sentence punctuation; the Virgel carries comma AND period
  function, and judging sentence-hood would be interpretation the convention
  excludes). Ambiguous initials after a Virgel → lowercase; a clearly chosen
  capital form wins as always. Applies the existing fallback wording to a
  concrete case; no rule reversal. Mirrored into the provider Regelblatt. No
  harness change. No page IDs, images, hashes, metric definitions, or
  thresholds changed.

* **2026-09-03 — closing-mark placeholder `⟪Z⟫`, superscript-o over u, line-end
  continuation strokes, marginal section marks (§3.1/§3.2/§3.3/§4; ninth question
  round).** Early-modern specialist's Zwischenstand for Seite_01/02/07 + 05/06
  (36 footnotes). (a) End-of-recipe/section flourishes without letter or
  punctuation value (`~:·`, `°/.`, six spots) had been rendered ad hoc
  (`[unleserlich]` or glyph approximations) → new uniform unscored placeholder
  `⟪Z⟫`, free-standing, also for probable closing signs; `[unleserlich]` reserved
  for unread text. Harness: `strip_markers` drops `⟪Z⟫` like `⟪G⟫`;
  `strip_hyp_markers` drops a bare `⟪Z⟫` inline (no body, nothing to hide);
  regression tests added. (b) Full superscript o over u → `uͦ` U+0366 (fallback u
  + superscript o, unified at ingest like U+0364); a not clearly closed ring is a
  u-bow → plain `u`, no `⟦ ⟧`. (c) Line-end filler/continuation strokes (`=`, `-`,
  not hyphenation) kept as written, attach like punctuation; a merely doubtful
  stroke without letter value is not encoded (the §4 dehyphenation already joins
  `=`/`-` at line end either way). (d) Marginal section/enumeration letters (`a`
  between frame lines) treated like foliation: own unmarked line at the
  reading-order position; placement made explicit (left of a line → before it,
  right → after it, between lines → after the upper), matching the transcriber's
  foliation placements on Seite_01/05/06. All fill spec gaps; no rule reversal.
  Mirrored into the provider Regelblatt. No page IDs, images, hashes, metric
  definitions, or thresholds changed; GT for these pages not yet ingested.

* **2026-09-24 — VLM repetition penalty (§6).** On the Stage-A dev pages the
  pre-registered greedy decoding (temperature 0, no penalty) sent Qwen3-VL-4B into
  repetition loops (dev baseline: 5 of 8 pages, output up to 1,022 lines with 3
  distinct), which makes its scores meaningless rather than low. Amendment: every
  locally served VLM engine (Qwen3-VL-4B both prompts, CHURRO, the Qwen2.5 stand-ins)
  sends `repetition_penalty: 1.1` with temperature 0. Chosen on dev pages only, before
  any gold run: probe of none / 1.05 / 1.1 on D1, D2, D3, D7, D8 — none looped on D3
  and D8 (cer_norm 8.71, 6.55), 1.05 still looped on D7 (3.64), 1.1 looped on none
  (0.51–0.92). Prompts, max_tokens, and all other §6 settings unchanged; frontier APIs
  that do not accept the parameter are unaffected. No page IDs, images, hashes, metric
  definitions, or thresholds changed.
* **2026-09-24 — sealed engine runs before GT completion (§2).** The §2 hard ordering
  (all GT completed before any engine output is viewed) is kept; what changes is that
  engines may *run* on gold before GT is complete, provided the outputs are sealed:
  written by the harness (`run --allow-incomplete-gt`) or exported from Transkribus into
  the run area, and not opened, displayed, scored, diffed, or summarized beyond page
  counts and error states until the adjudicated GT v1.0 is frozen. Nobody opens gold
  pages in a vendor editor after recognition. Reason: time-limited Transkribus credits
  and engine availability, without letting engine output bias transcription or
  adjudication. Owner decision 2026-09-24. No page IDs, images, hashes, metric
  definitions, or thresholds changed.

* **2026-09-24 — engine additions and released-precision rule (§6).** Two open engines
  added before any gold output is viewed or scored (the sealed run of §2 keeps engine
  choice blind to results): **Qwen3.5-4B** (`Qwen/Qwen3.5-4B`, Apache-2.0, successor of the
  Qwen3-VL-4B base-model floor; both pre-registered prompts; run in the vendor's documented
  non-thinking/instruct mode, `enable_thinking: false`, because thinking output is not a
  transcription) and **olmOCR-2-7B**
  (`allenai/olmOCR-2-7B-1025`, Apache-2.0, open OCR specialist on a Qwen2.5-VL-7B base;
  default prompt, like CHURRO). Both use the fixed §6 prompt verbatim, not their vendors'
  recommended prompts, so specialist models may be disadvantaged; that is accepted for
  comparability. Qwen3.8-27B was considered as an open ceiling and dropped (released BF16
  weights do not fit the available storage). **Released-precision rule:** every benchmark
  engine runs the official checkpoint at its released precision (here BF16); a quantized
  build may only appear as a separately named engine, never as a substitute. The Qwen2.5-VL
  AWQ entries remain silver stand-ins and are never scored on gold. No page IDs, images,
  hashes, metric definitions, or thresholds changed.

* **2026-09-28 — primary keyer's question rounds on the dev pages and Blatt package
  (§3.1/§3.2).** Sixteen rulings from the primary keyer's questions of 2026-09-17 to
  2026-09-28, answered by mail and applied in her dev-page delivery (Stage-A dev set,
  reviewed 2026-09-23): word boundaries by word not gap; punctuation only where visible
  (missing/cropped period not supplied, clear slip period kept, doubtful speck dropped);
  letter-value diacritics kept (`š`); ditto marks as written with straight `"`; death
  cross `†` as own line, not `⟪Z⟫`; spaced dot runs as `. . .`; table details (all
  cells per row, row-spanning cells in the first row, stacked entries one per line,
  split amount columns with the dot in the left cell); margin notes stay on their
  page; `⟪G⟫` own line with beside-text before/after by side; other-hand/pencil marks
  as own lines (§3.2.7); tie-break upper/left (§3.2.8); file format (UTF-8 without BOM,
  consistent line ends; two-page scans left then right, no marker). All apply or
  extend existing rules to concrete cases; no rule reversal. Mirrored into the provider
  Regelblatt (Stand 2026-09-28). The second keyer's 34-page delivery (August) predates
  these rulings; any differences are resolved at adjudication against the scan, not by
  re-keying. No harness change (`"`, `†`, spaced dots are ordinary scored characters).
  No page IDs, images, hashes, metric definitions, or thresholds changed.

* **2026-10-04 — Gate 1 training before the Gate 0 branch (model track; POST_GATE0
  §1/§7).** Owner decision D-2026-10-04-01 (model-track DECISIONS.md). The preregistered
  Stage-A pair on Qwen3.5-4B may train before the Gate 0 branch is recorded, because the
  branch needs scored gold and gold outputs stay sealed until GT v1.0 (2026-09-24 entry).
  Pre-Gate-0 spend capped at €120; checkpoint selection on the frozen dev pages only;
  adapter gold runs only as sealed runs. The POST_GATE0 CALIBRATE anchors are ratified at
  unsealing, after the Gate 0 engines are scored and before any adapter gold output is
  scored (previously: before the first training run). FROZEN-NOW thresholds T1–T4 and the
  verdict rule unchanged. The Gate 0 branch still governs continuation (B: the pre-Gate-0
  runs are the feasibility probe; C: the model track stops). No page IDs, images, hashes,
  metric definitions, or benchmark thresholds changed.

* **2026-10-09 — primary keyer's questions of 2026-10-02 and 2026-10-07 (§3.1/§3.2).**
  Seven rulings, answered by mail and mirrored into the provider Regelblatt (Stand
  2026-10-09): doubling stroke over m/n as overline, not expanded; word-final loop for a
  missing ending → `'` (existing rule, example added); one `⟪D: …⟫` per continuous
  strike, struck letters inside a word marked in place without spaces, overwritten
  letters keyed as final form; keyed text elsewhere in the text block moves to its
  anchor as `⟪M: …⟫`, reference marks not encoded (extends §3.2.3 from the margin to
  the text block); a date inside an unkeyed note is its own `⟪M⟫` line by §3.2.7
  placement; amount lines are text, number separators as written; text beside an
  inline table row placed before/after it; calendar/diary layouts are text, with the
  note column as unkeyed marginalia (consistent with the existing Petri index-column
  rule). All apply or extend existing rules to concrete cases; no rule reversal. The
  second keyer's August delivery predates these rulings; differences are resolved at
  adjudication. No harness change. No page IDs, images, hashes, metric definitions, or
  thresholds changed.

* **2026-10-10 — scope of pre-Gate-0 training (model track).** Owner amendment to
  D-2026-10-04-01: the three preregistered Stage-A runs on Qwen3.5-4B (LLM-only and
  LLM+ViT LoRA with Stage A, then the winner without Stage A) may train before the
  Gate 0 branch, inside the unchanged €120 cap; the 2026-10-04 entry's "Stage-A pair"
  is superseded. No page IDs, images, hashes, metric definitions, or thresholds changed.
* **2026-10-16 — loop guard for token-limited VLM outputs (§5, §6).** On the dev pages,
  every VLM output that stopped at the engine's token limit was a repetition loop, and
  every loop page stopped there: 29 of 29 in the 21 scored Gate 1 models of the model track
  EXP-20261011-gate1-runs. The repeated text counted as character errors and as
  fabrication, although runaway repetition is visible, not silently plausible
  (FABRICATION_METRIC, repetition rate). Amendment: at scoring, an output whose recorded
  completion tokens reach the engine's `max_tokens` is scored without its trailing loop
  (`harness/loop_guard.py`). Two rules estimate where the loop starts: an exact periodic
  tail (block of at most 2,000 characters, at least three copies and 200 characters), and
  the third occurrence of a line (cut at its second occurrence). The earlier cut wins, and
  one copy of the repeated text remains. Outputs below the token limit and engines that
  report no token usage are never changed. The stored raw output is never changed. A
  guarded page carries `loop_guard` (rule, raw and scored lengths, unguarded metrics),
  the engine result lists `loop_guard_pages`, and the report names them. The guard is a
  scoring rule, not an engine setting: it applies to all engines alike and to outputs
  already recorded, including the sealed gold runs, which stay unopened; engine configs
  and resumes do not change. A released system that claims these scores must apply the
  same guard. Chosen on dev pages only, before any gold output is viewed or scored: the
  line rule alone first (it cut 10 outputs); the periodic rule and the earlier cut were
  added after the loop shapes on the same pages were inspected (loops inside one line
  with 6–8-character periods; loops that begin with inexact repeats). Dev effect
  (`scripts/dev_loop_guard.py`): all 29 token-limited outputs cut, loop pages 29 → 0;
  Run 2 step 1000 mean `cer_norm` 0.416 → 0.369, maximum `fab_rate` 0.274 → 0.042, median
  unchanged. Gate 1 dev selection (`scripts/dev_checkpoints.py`) stays as frozen in the
  model-track record. Owner decision 2026-10-16 (in session). Metric definitions and
  thresholds are unchanged; for token-limited outputs they are computed on the guarded
  text. No page IDs, images, or hashes changed.
* **2026-10-16 — GT v1.0 text frozen (§2, §11).** The author adjudicated every
  disagreement of the 36 double-keyed pages against the scans and found no case where
  the primary keyer was wrong and the second key right. The primary keyer's key is
  therefore v1.0 on those 36 pages. It is also v1.0 on the 7 single-keyed Fraktur/Latin
  pages and the 2 trial pages. The 8 early-modern pages keep the specialist key as
  adjudicated on 2026-09-14. The build applies only the v0.9 mechanical transforms
  (private repository, `scripts/build_gt_v10.py`; page hashes in its `docs/GT_V1.md`).
  The harness reports GT coverage 53/53. Entity lists (§2 step 5) are not built, so GT
  is not complete in the §2 sense: the sealed gold runs stay unopened until the owner
  decides whether entity annotation comes first. No page IDs, images, metric
  definitions, or thresholds changed.
* **2026-10-16 — unsealing order (§2).** Owner decision: entity lists for all scored
  pages are built and frozen before any sealed gold output is opened or scored, as the
  §2 hard ordering requires. No page IDs, images, metric definitions, or thresholds
  changed.
* **2026-10-17 — line-end strokes and historical month forms (§4, entity scoring).**
  Found while the owner annotated the gold entities, before any sealed gold output was
  opened. Owner agreement in session ("ok"). (a) §4 step 2 joined the words around every
  line-end `-`, `=`, or `⸗`, also a filler stroke after punctuation (§3.1, "1812.-"). The
  next line's first word was glued to the line's last word ("1812.Johann") and could not
  be recalled as an entity, also not from the GT itself. This revises the 2026-09-03 (c)
  remark that the dehyphenation joins `=`/`-` at line end either way. Now a line-end
  stroke never counts; it joins only directly after a letter (also one with a combining
  mark); otherwise it is dropped and the words stay apart. Gold v1.0: 6 of 238 line-end
  strokes change (3 after a full stop, 2 after an apostrophe, 1 after a dash); dev
  pages: 6 on one page. (b) Date matching (`harness/entities.py`) did not read
  historical month forms (Septbr., Septem, Augusti, Octobris), so such a date counted
  only as its digits and a modern transcription missed it, and it read the numeral month
  7ber (September) as July. Added Latin, contracted, truncated, numeral (7ber to Xber),
  and Germanic (Hornung, Scheiding, Julmond) forms, from general knowledge of historical
  German records, not from benchmark pages; a numeral month is one token. The entity-risk
  candidate patterns use the same month list. Both rules apply identically to gold and
  every engine. No page IDs, images, GT, thresholds, or other metric definitions changed.
  Gate 1 dev-page scores were computed with the earlier rules; comparisons among them
  stay valid.
* **2026-10-18 — gold entity lists frozen (§2 step 5).** The author annotated persons,
  places, and dates on all 53 scored pages, under the entity rules of the annotation page
  and dated rulings (greeting formulas, place names inside institution names, an author
  variant for one date whose month word is uncertain). The lists were checked against
  the frozen v1.0 GT and built with the harness at `9a04af7` (private repository,
  `scripts/ingest_entities.py`; hashes in its `docs/GT_V1.md`). The harness reports
  entity coverage 53/53, so GT is complete in the §2 sense and the sealed gold runs may be
  opened when the owner decides. At unsealing, the Gate 0 engines are scored first; the
  POST_GATE0 CALIBRATE anchors are ratified before any adapter gold output is scored
  (2026-10-04 entry). No page IDs, images, GT text, metric definitions, or thresholds
  changed.
* **2026-10-18 — sealed gold run opened (§2).** Owner decision in session: "we can
  unseal". Logged before any gold output is opened or scored. The sealed run
  `20260924-112302` (11 engines; its `RUN_NOTES.md`) is scored against GT v1.0 and the
  frozen entity lists with the harness code of `9a04af7` (§4 as amended 2026-10-17; loop
  guard 2026-10-16), by `harness score` and `harness report`. No engine is run again and no
  stored output changes. This run holds the Gate 0 engines only; adapter gold outputs
  follow after the POST_GATE0 CALIBRATE anchors are ratified (2026-10-04 entry). No page
  IDs, images, GT, metric definitions, or thresholds changed.
* **2026-10-18 — Gate 1 adapter gold run, sealed (§2, §6).** Owner decision in session
  ("confirmed, and evo is frozen. go"), after the Gate 0 branch (model-track
  D-2026-10-18-01). One new run dir holds three engines, run in this order on the EVO in
  one serving state (no reboot, no update, no compile-cache change between them):
  `qwen35_4b` again as the T1 reference, then the Gate 1 adapter `gate1_run2_s1000`, then
  `gate1_run3_s1200` for the VOID check of model-track D-2026-10-16-01. The two adapter
  engines (`configs/engines.yml`) are LoRA adapters merged into Qwen3.5-4B at BF16 and use
  the `qwen35_4b` prompt and settings unchanged; each config records the adapter's sha256.
  The checkpoints were selected on the dev pages before this entry (model-track
  EXP-20261011-gate1-runs). The run is sealed: its outputs are not opened, displayed,
  scored, or summarized beyond page counts and error states until the POST_GATE0 CALIBRATE
  anchors are ratified. The 2026-10-18 opening entry's "adapter gold outputs follow"
  means scoring, as in the 2026-10-04 entry. The 2026-09-24 `qwen35_4b` result stays the
  base model's leaderboard entry. No page IDs, images, GT, prompts, metric definitions, or
  thresholds changed.
* **2026-10-18 — POST_GATE0 CALIBRATE anchors ratified; Gate 2 target raised (model
  track; POST_GATE0 §7).** Owner decision in session ("anchors as proposed, raise Gate
  2"), model-track D-2026-10-18-02. Logged after the Gate 0 engines were scored and
  before any adapter gold output is scored (2026-10-04 entry). Anchors, on primary
  strata: suetterlin median `cer_norm` ≤ 0.15; ugly_kurrent ≤ 0.28 AND median entity
  recall ≥ 0.40; tidy_kurrent and twentieth_century_kurrent pooled ≤ 0.30; §8 hard-strata
  set ≤ 0.20 AND entity recall ≥ 0.65; degraded_fraktur `nls_norm` ≥ 0.896 reported, not
  counted. Rationale: about halfway between CHURRO and Transkribus German Genius on the
  Gate 0 run. tidy_kurrent alone has 2 pages, and the German CHURRO subset has no harness
  suite. Gate 2 target: beat German Genius on the hard-strata set (below 0.128 and above
  0.825). FROZEN-NOW thresholds T1–T4, the verdict rule, and the §8 kill criterion are
  unchanged. No page IDs, images, GT, metric definitions, or benchmark thresholds changed.
* **2026-10-18 — loop guard: lines without a letter or digit do not trigger the line
  rule (§5; 2026-10-16 entry).** Owner decision in session ("approve 2"). Found by the
  POST_GATE0 §3 error analysis of the Gate 0 outputs: on one CHURRO page that stopped at
  the token limit, a line holding only the table rule `|` occurred a third time, and the
  line rule cut the output at its second occurrence, which removed readable text after
  it. Lines without a letter or digit (table rules, `---`, ditto marks) repeat on real
  pages, so they no longer count toward the line rule (`harness/loop_guard.py`; cases
  F10 and F11 in `tests/test_loop_guard.py`). The periodic rule is unchanged, so a
  runaway of such lines is still cut. Effect on the Gate 0 run, checked before the
  change over all 54 guarded outputs of the 11 engines: one output changes (that CHURRO
  page, whose scored text grows from 336 to 982 of its 8,544 characters);
  nothing else changes. Logged before any adapter gold output is scored: the sealed
  adapter run is scored with the amended guard, and the Gate 0 run is scored again with
  it (its `RUN_NOTES.md`). Gate 1 dev-page selections stay as scored (2026-10-17 entry),
  and the POST_GATE0 anchors stay as ratified. No page IDs, images, GT, prompts, metric
  definitions, or thresholds changed.
* **2026-10-18 — annex pages reported only (§1, §5.6; POST_GATE0 §7 T3).** Owner
  decision in session ("approve demote"), model-track D-2026-10-18-03. The POST_GATE0 §3
  error analysis found that both annex pages A01 and A02, selected as pure-graphics
  fabrication probes where correct output is an abstention, contain real text. An
  engine that reads them correctly is counted as hallucinating. A reference
  transcription could not be completed (one page partly unreadable, the other
  unreadable to the author). Amendment: the annex pages stay in the selection, the
  freeze, and every run, and their results are still reported, labelled "reported only;
  not a fabrication signal". A failed or missing annex output no longer makes `score`
  or `report` incomplete, and the draft T3 completeness no longer waits for the annex.
  POST_GATE0 T3 loses its annex condition. Absent-evidence probes follow the
  negative-control plan of `docs/FABRICATION_METRIC.md`. Logged before any adapter annex
  output is opened or scored. No scored page, image, GT, metric definition, or
  scored-page threshold changed.

* **2026-10-20 — Gate 1 9B gold run, sealed (§2, §6).** Owner instruction in session
  ("evo is free for the night. Same procedure as previously", 2026-10-20), under the
  frozen protocol of model-track EXP-20261019-gate1-9b-run (POST_GATE0 §9 step 2;
  D-2026-10-18-04). Logged before the run. One new run dir holds two engines, run in this
  order on the EVO in one serving state (no reboot, no update, no compile-cache change
  between them): `qwen35_9b`, Qwen3.5-9B zero-shot
  (`Qwen/Qwen3.5-9B@c202236235762e1c871ad0ccb60c8ee5ba337b9a`), as the T1 reference ("its
  own base model zero-shot"), then the Gate 1 adapter `gate1_run7_s800`, a LoRA adapter
  merged into Qwen3.5-9B at BF16. Both use the `qwen35_4b` prompt and settings unchanged
  and are served alone by the same launcher and profile as the 4B engines; the adapter
  config records the adapter's sha256. The checkpoint was selected on the dev pages
  before this entry (step 800; EXP-20261019-gate1-9b-run). The run is sealed: its outputs
  are not opened, displayed, scored, or summarized beyond page counts and error states
  until the owner opens it. The freeze is the agent's reading of the owner instruction;
  the boot id and the package log are recorded before and after each engine in the run's
  `RUN_NOTES.md`. No page IDs, images, GT, prompts, metric definitions, or thresholds
  changed.

* **2026-10-21 — Gate 1 9B gold run opened (§2).** Owner decision in session: "yes please
  score". Logged before any output of `20261020-164104_gate1_9b_sealed` is opened or
  scored. Both engines are scored against GT v1.0 and the frozen entity lists by `harness
  score` and `harness report` with the harness of `da5ec8c` (configs at `492d0f5`), the
  code that scored the 2026-10-18 adapter run. T1 reference: `qwen35_9b` of this run, as
  logged in the 2026-10-20 entry. No engine is run again and no stored output changes. No
  page IDs, images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-21 — gold-use guards against adaptive overfitting (§2, §7).** Owner decision
  in session ("agreed on the guards"), model-track D-2026-10-21-02. The gold set is small
  (53 scored pages; 2 to 13 per handwriting stratum), so repeated looks at gold results
  can tune a model to it even when no gold page is trained on. From this entry on:
  (1) every recipe, data, and checkpoint decision for a model engine is made on dev pages,
  never on gold results; (2) gold runs only a release candidate that a §10 entry names
  before the run, as a sealed run, at most one per training-data round; (3) gold outputs
  are not used for error analysis that chooses training data or recipes (the 2026-10
  error taxonomy stays as recorded; it is not repeated); (4) a claim about a model's gold
  result also reports at least one external test set that gold did not influence;
  (5) before a public model claim, a refreshed held-out set from new sources is keyed and
  scored once, and a drop against this set is reported. Training-data sources stay
  subject to §7. No page IDs, images, GT, prompts, metric definitions, or thresholds
  changed.

* **2026-10-25 — Gate 1 9B release candidate gold run, sealed (§2, §6; gold-use guards
  2026-10-21).** Owner decision in session (2026-10-25, answer to the agent's question: run a
  sealed gold run of Run 11 step 800 as this data round's single release candidate, "Yes,
  today"). Logged before the run. The candidate is model-track Run 11 step 800
  (EXP-20261023-9b-2mp): Qwen3.5-9B with a LoRA adapter trained on the Run 5 recipe plus the
  filtered ICDAR 2017 READ pages, at a 2 MP training image cap; selected on the dev pages only
  (dev median 0.183 against Run 8's 0.212 in one serving state). This is the one gold run of
  the READ data round (guard 2). One new run dir holds two engines, run in this order on the
  EVO in one serving state (the EVO frozen by the owner for the run: no reboot, no other
  operating system, no compile-cache clear): `qwen35_9b` again as the T1 reference, then
  `gate1_run11_s800` (merged into Qwen3.5-9B at BF16, the `qwen35_4b` prompt and settings
  unchanged, served at the processor's default resolution like every engine; its config
  records the adapter's sha256). The run is sealed until the owner opens it. Any claim from it
  is reported with the Run 0 sealed external suites (guard 4), scored separately. No page IDs,
  images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-25 — Gate 1 9B release candidate gold run opened (§2).** Owner decision in
  session: "You can open and score gold and push". Logged before any output of
  `20261025-065703_gate1_run11_sealed` is opened or scored. Both engines are scored against GT
  v1.0 and the frozen entity lists by `harness score` and `harness report` with the harness
  of `da5ec8c` (configs at `227385d`), the code that scored the 2026-10-18 and 2026-10-21
  runs. T1 reference: `qwen35_9b` of this run. No engine is run again and no stored output
  changes. No page IDs, images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-31 — frontier VLM engine `gpt6_astra_max` (§6).** Owner request in session: "how
  a frontier model like Astra on max does on the benchmarks", then "we can use a codex session
  with sub for that, no need for api". Logged before any benchmark or dev page is sent. The
  engine is GPT-6-Astra at reasoning effort `max` through the Codex CLI (`codex_cli` engine,
  one session per page, the §6 prompt verbatim, the page image as-is; shell, web search, apps,
  browser, computer use, and image generation disabled; a session with any tool item is an
  engine error). §6 allows a frontier VLM on unrestricted pages: every scored page is CC0,
  PDM, or CC BY 4.0 (`gold/selection.yml`), and the two annex pages come from collections with
  scored CC0 pages. Only page images leave the machine; GT and entity lists do not. The
  harness runs this engine's pages in parallel (`concurrency`); a failed session (for example a
  usage limit) records nothing, so a resume gives the page its first attempt. Order: dev pages
  first; the gold run is sealed and waits for the owner to confirm the account's data controls
  (model training on the images off). No page IDs, images, GT, prompts, metric definitions, or
  thresholds changed.

* **2026-10-31 — frontier VLM engine `fable51_max` (§6).** Owner request in session, after the
  `gpt6_astra_max` dev run: "I also want to get a reading from Fable Max. I think you can do it
  with claude cli using the sub, no need for api". Logged before any benchmark or dev page is
  sent. The engine is Claude Fable 5.1 (`claude-fable-5-1`) at effort `max` through the Claude
  Code CLI (`claude_cli` engine, one `claude -p` session per page, the §6 prompt verbatim, the
  page image as-is in the user message). All built-in tools, MCP servers, settings files,
  skills, CLAUDE.md files, and auto-memory are disabled; a session with any tool use or more
  than one turn is an engine error. The CLI still adds its default system prompt, an
  environment block, and the account e-mail address; none carries page content. Page scope,
  data flow, concurrency, failed-session handling, and order (dev pages first; gold sealed until
  the owner confirms the account's data controls) are as for `gpt6_astra_max`. No page IDs,
  images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-31 — `fable51_max` empty system prompt (§6).** The first dev run
  (`evals/dev_stage_a/runs/20261031-102045_fable51_max`, CLI default system prompt) is void and
  is not scored. Under the default coding-agent system prompt, the model on 4 of 8 dev pages
  tried to find the page file on disk or a library catalogue and, with no tools available, wrote
  those tool calls as text: D1, D2, and D7 ended as multi-turn engine errors, and D6 recorded the
  tool-call text as its transcription. Nothing was executed. The engine now passes an empty
  system prompt (the CLI keeps a one-line SDK identity, the environment block, and the account
  e-mail address), and a final message with a tool call written as text is an engine error, as
  for tool use. The dev run is repeated in a fresh run directory; the gold run is still sealed.
  No page IDs, images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-31 — `fable51_max` one-line system prompt, length stops, data controls (§6).** The
  second dev run (`evals/dev_stage_a/runs/20261031-110148_fable51_max_sp`, empty system prompt)
  is superseded and is not scored as the engine's dev result. Seven pages were clean. On D2 the
  model wrote about 3,600 characters of transcription and then repeated a tool call written as
  text until the output token limit; the CLI then resumed the reply with a synthetic user
  message, which made a second turn. With an empty system prompt, the CLI still sends its
  one-line SDK identity and the environment block. The engine now passes the one-line system
  prompt "No tools are available. Reply with text only." The §6 prompt is unchanged. A reply
  that reaches the output token limit is a length stop, as for the OpenAI-compatible VLM
  engines: the text of the first reply is recorded with finish_reason `length`, and the resumed
  turns are not used. A tool call written as text in that text is still an engine error. The
  dev run is repeated in a fresh run directory. Owner confirmation in session: "training is
  disabled in data controls" (the Claude account). The gold run for `fable51_max` is no longer
  sealed on that condition; it runs only after a dev run with no engine errors. No page IDs,
  images, GT, prompts, metric definitions, or thresholds changed.

* **2026-10-31 — `fable51_max` gold run opened (§2).** Owner decision in session: "Yes, open
  and score". Logged before any output of `20261031-155542_fable51_max_sealed` is opened or
  scored. The run started after the third dev run
  (`evals/dev_stage_a/runs/20261031-154258_fable51_max_np`) had no engine errors. The engine is
  scored against GT v1.0 and the frozen entity lists by `harness score` and `harness report`
  with the harness at `5ff4ce9`. The scoring, entity, and report code is unchanged since
  `da5ec8c`, the code that scored the 2026-10-18, 2026-10-21, and 2026-10-25 runs. This is an
  external reference reading, not a model-track release candidate: its gold outputs are not
  used for error analysis that chooses training data or recipes (gold-use guard 3). No engine
  is run again and no stored output changes. No page IDs, images, GT, prompts, metric
  definitions, or thresholds changed.

* **2026-11-06 — editorial: roles in place of keyer and reviewer names (§2, §10, §11;
  release v1.0, owner decision O6).** The public protocol names no keyer or reviewer.
  §2, the §10 entries of 2026-07-09 and 2026-07-28, and §11 now say "primary keyer" and
  "second keyer"; `docs/FABRICATION_PILOT.md` says "reviewer 1" and "reviewer 2". The
  identities, agreements, and keying records stay in the private evaluation repository.
  Editorial only: no method, page IDs, images, hashes, GT, prompts, metric definitions, or
  thresholds changed.

* **2026-11-06 — release v1.0: §11 sub-decisions closed (§5.3, §7, §11; owner decisions
  O3, O4, O5, O9).** Owner decision for the v1.0 release (model-track
  `docs/RELEASE_V1_EXECUTION.md` §2). Logged before any release step.
  (1) **Images (O3).** The 53 scored page images are distributed as a gated dataset on
  Hugging Face under evaluation-only terms: no training, no redistribution, no
  transcription published in a training-usable form. The page manifest, source links,
  and SHA-256 hashes stay public in this repository. The two annex pages are not in the
  dataset, because `gold/selection.yml` records no licence for them; they stay reported
  only (§10, 2026-10-18).
  (2) **Submissions (O4).** A participant sends a private prediction bundle: one text file
  per page and a `run.json` with the engine description (`SUBMITTING.md`). The owner
  scores it offline with the release harness against the private GT. Only aggregates are
  published (per engine, per stratum); no page output and no per-page score. Cap: one
  scored submission per engine version per 30 days.
  (3) **Fabrication examples (O9).** §5.3 "reported with examples" does not apply to
  benchmark pages: no example text from a benchmark page is published, because any span
  is a piece of the private text layer (§7). Illustrations come from dev, silver, or
  other public-domain scans.
  (4) **Early-modern pages.** The 8 early-modern pages have the specialist key adjudicated
  on 2026-09-14 and are part of GT v1.0 (§10, 2026-10-16). The §11 embargo condition is
  met: they count in v1.0 like every other scored page.
  (5) **Version label (O5).** `Kurrent Pages Benchmark v1.0` = GT v1.0 + harness tag `v1.0.0` +
  this protocol with §10 up to the tag date. Scores compare only within v1.0 (§11).
  No method, page IDs, images, hashes, GT, prompts, metric definitions, or thresholds
  changed.

* **2026-11-06 — Gate 2: one sealed gold run per self-training round (gold-use guards
  2026-10-21).** Owner decision in session: "agreed on your self training plan. amendment is
  fine" (model-track `docs/GATE2_SELF_TRAINING_PLAN.md` §4, decision G2). Logged before any
  Gate 2 gold run. Each self-training round is a data round (guard 2) and gets exactly one
  sealed gold run, logged in this section before its training starts. The round's model is
  fixed in advance (fixed recipe and step, no checkpoint selection), so the run selects
  nothing. Two seeds per round, both run and both reported. Gold decides only whether the
  loop continues and which round is released: continue if the gold median `cer_norm`
  improves by at least 0.01 against the previous round; two rounds in a row below 0.01 is a
  plateau and the loop stops (model-track POST_GATE0 §8). Gold never chooses data, sources,
  filters, thresholds, steps, prompts, or decoding, and no per-page gold result is inspected.
  The other guards stand. No page IDs, images, GT, prompts, metric definitions, or thresholds
  changed.

* **2026-11-06 — Gate 2 Round 0 gold run, sealed; VLM keys `image_only` and `vllm_xargs`
  (§2, §6).** Owner decision in session: "Yes, start Round 0". Logged before the run.
  (1) **Engine keys.** `vlm_openai` accepts two optional keys, sent only when set:
  `image_only: true` sends the page without the prompt text (engines trained without one;
  the prompt file's hash is still recorded), and `vllm_xargs` is passed to vLLM as-is.
  Requests of every existing engine are unchanged.
  (2) **Engines.** `gate2_p1_s2400` (model-track P1, LightOnOCR-3-1B fully trained on the
  page-centric bundle, step 2400) and `gate2_p1r_s2400` (the same code and data, seed 1702).
  Both run image-only with the decoding of their dev evidence: greedy, whole-context
  repetition penalty 1.0, and the windowed penalty 1.1 over the last 20 tokens
  (model-track `scripts/windowed_repetition_penalty.py`, loaded by the server). Each config
  records the sha256 of the trained weights. Control: `gate1_run11_s800`, unchanged.
  (3) **Run.** One new run dir (`gate2_round0_sealed`) holds the three engines, run in the
  order P1, P1r, Run 11 on one RunPod GPU Pod in one serving state (RTX PRO 6000, vLLM 0.23.0,
  transformers 5.13.0; the serving identity is checked before and after each engine). The
  page images stay on the MacBook and reach the Pod only as requests through an SSH tunnel;
  no page file is stored on the Pod. Run 11 here is a cross-backend control: its 2026-10-25
  EVO row stays the reference, and the difference is reported.
  (4) **Use.** Round 0 is the Gate 2 baseline, not a release candidate. It reports the 1B gap
  to German Genius and the gold seed noise (P1 against P1r). If the seed difference on the
  gold median is 0.01 or more, later rounds use more seeds. The run is sealed until the owner
  opens it. No page IDs, images, GT, prompts, metric definitions, or thresholds changed.

* **2026-11-06 — Gate 2 Round 0 gold run opened (§2).** Owner decision in session, given
  before the run finished: "Yes, score on finish". Logged before any output of
  `20261106-094256_gate2_round0_sealed` is opened or scored. The run is complete: three
  engines, 55 page records each, no error record, one serving identity (RunPod Pod
  `zr48p0ht0dm32n`; the windowed-penalty processor was shown to act for both LightOn engines on
  dev page D1 before any gold page). All engines are scored against GT v1.0 and the frozen
  entity lists by `harness score` and `harness report` with the harness of the
  pre-registration (`a01167f`; unchanged at `68b00d1`). Only aggregates are read. No engine is
  run again and no stored output changes. No page IDs, images, GT, prompts, metric
  definitions, or thresholds changed.

* **2026-11-06 — Gate 2 continue rule adds entity recall.** Owner decision in session:
  "Yes, add it" (model-track `experiments/EXP-20261106-gate2-round0.md`, consequence 1).
  Logged before Round 1 is pre-registered and before any Round 1 data, label, or model
  exists. It replaces the continue rule of the 2026-11-06 Gate 2 entry; the other parts of
  that entry stand. Reason: Round 0 put the 1B level with German Genius on `cer_norm` and
  behind on entity recall, so a rule on `cer_norm` alone cannot see the remaining gap.
  (1) **Round value.** For each metric, the mean of the round's two seeds of the harness
  aggregates `overall.cer_norm_median` and `overall.entity_recall_median`. The previous
  round's value is computed the same way. Round 0 values: `cer_norm` 0.1201, entity recall
  0.6333 (P1 and P1r).
  (2) **Pass.** A round passes when (a) `cer_norm` falls by at least 0.01 and entity recall
  falls by no more than 0.05, or (b) entity recall rises by at least 0.05 and `cer_norm`
  rises by no more than 0.01. Each tolerance equals the other metric's threshold. The
  entity threshold is near the two-seed noise (Round 0 seed difference 0.067 for one seed).
  A false pass costs one more round.
  (3) **Stop.** Two rounds in a row that do not pass is a plateau, and the loop stops. The
  entrenchment stop (silver agreement rises while gold stays level) stands.
  (4) **Seeds.** Two seeds stay: the Round 0 seed difference on the `cer_norm` median was
  0.0001, below the 0.01 bar of the Round 0 entry.
  Hard-strata medians stay reported, not decided on. Gold still never chooses data,
  sources, filters, thresholds, steps, prompts, or decoding. No page IDs, images, GT,
  prompts, or metric definitions changed.

* **2026-11-06 — editorial: public name "Kurrent Pages Benchmark" (§1, §2, §10; release
  v1.0, owner decision O14).** The benchmark is published as the Kurrent Pages Benchmark;
  the release label of the 2026-11-06 release entry is now `Kurrent Pages Benchmark v1.0`.
  References to the private model and evaluation repositories now say "model-track" and
  "evaluation root"; the decision and experiment IDs they cite are unchanged. The private
  repositories keep their names. Editorial only: no method, page IDs, images, hashes, GT,
  prompts, metric definitions, or thresholds changed.

* **2026-11-06 — Gate 2 Round 1 gold run, sealed (§2, §6).** Owner decision in session: "Yes,
  start Round 1". Logged before any Round 1 label, filter result, or training run exists.
  (1) **Round.** Silver data and training as model-track
  `experiments/EXP-20261106-gate2-round1.md` (frozen, sha256 `cd1fbbc6e60b2f2b…`, after its
  one external review): unlabeled pages of the Staatsbibliothek zu Berlin with a PDM, CC0, or
  CC BY image licence; labels by `gate1_run11_s800` and `gate2_p1_s2400` with their harness
  requests; the frozen agreement filter; the label is the Run 11 text; P1's recipe on P1's
  data plus the silver pages; seeds 1701 and 1702; step 2400; no checkpoint selection. No
  gold page, result, or metric was used for any of these choices.
  (2) **Run.** One RunPod session, one run dir `gate2_round1_sealed`: engines
  `gate2_r1_s1701_s2400` and `gate2_r1_s1702_s2400`, decoding as `gate2_p1_s2400`, added to
  `configs/engines.yml` with their weights' sha256 after training and before the run (logged
  here), and `gate2_p1_s2400` as a same-session control (reported only). A dev sanity pass
  comes first in the same session and gates nothing.
  (3) **Decision.** The round rule of the 2026-11-06 entry "Gate 2 continue rule adds entity
  recall" decides, against Round 0 (`cer_norm` 0.1201, entity recall 0.6333): pass if the
  two-seed mean has `cer_norm` ≤ 0.1101 with entity recall ≥ 0.5833, or entity recall ≥ 0.6833
  with `cer_norm` ≤ 0.1301. A seed without a valid gold run makes the round a non-pass. The
  run is sealed until the owner opens it; only aggregates are read. No page IDs, images, GT,
  prompts, metric definitions, or thresholds changed.

## 11. Release, versioning, and distribution (added 2026-07-09)

- **GT stays private — held-out evaluation.** The ground truth is **not published**.
  The benchmark runs as a held-out/hosted eval: participants submit engine outputs for
  the released page images and we score them against the private GT. Rationale: the set
  was built for *zero public text* (§7 contamination controls, the whole
  `zero_public_text` selection constraint); publishing GT would create a public
  machine-readable text layer for these one-off/private pages, contaminate future
  training corpora, and destroy the property the selection was designed around.
  Publishing GT is a one-way door; it stays closed for now. Even **image** release scope
  is weighed separately (licenses permit it, but re-identification / future OCR of the
  images is a cost); default posture is minimal public exposure.
- **Versioning.**
  - **v0.9 — provisional.** May be produced on a *single* external keying (the second
    keyer's, available first, August). Explicitly labeled provisional, for internal
    signal + harness shakedown; **not** a citable/comparable release, **never** numbered v1.0.
  - **v1.0 — stable.** The adjudicated **double-keyed** GT (primary keyer + second
    keyer + author adjudication). First citable/comparable version.
  - **Scores are comparable only within a version.** Any GT change bumps the version and
    ships with a published changelog + diff. No cross-boundary comparison (esp. v0.9→v1.0).
- **Sub-decisions (closed 2026-11-06, §10):** submissions are private prediction bundles
  scored offline, aggregates only, one per engine version per 30 days; the scored page
  images are a gated evaluation-only dataset; the early-modern pages count in v1.0.
  Originally open: exact submission/scoring mechanism for the held-out eval; whether/how
  images are distributed; embargo on early-modern pages until they have GT.
