# Vision Document v2: Permissive German Historical HTR

> Frozen context snapshot for `BENCHMARK_PROTOCOL.md` references. The canonical,
> evolving model-track vision lives in the private model repository; held-out
> targets and evaluation operations live in the private evaluation repository.

**Status:** Concept revised after strategy review; pre-implementation
**Last updated:** 2026-07-02
**Working title:** German Historical HTR
**Supersedes:** v1 (Transkribus-distillation-centered plan)
**Core direction:**
`Qwen3-VL base → permissive German corpus + synthetic Fraktur/Kurrent → self-training on unlabeled archival scans → human-corrected disagreement set later`

Transkribus is demoted from teacher to occasional benchmark. CRNN pipelines are promoted to first-class baselines with an explicit kill criterion.

---

## 1. One-Sentence Vision

Build a small, open, offline German historical text-recognition model — plus a standing benchmark — that runs on consumer hardware, handles the archival pages that break segmentation-based pipelines, and can be legally used on material that cannot be uploaded to cloud services.

---

## 2. What Changed Since v1

1. **Transkribus distillation removed from the critical path.** It was the dominant cost (€745–7,438 depending on scale), required written permission that READ-COOP has little incentive to grant for a public competing model, and its ceiling was "Transkribus minus epsilon." It is now a contingent option, not the plan.
2. **Synthetic data and self-training promoted to the main data engine.** The cost model collapses to mostly GPU rental.
3. **Kraken / PyLaia / eScriptorium added as first-class baselines.** These, not Tesseract, are the real open-source incumbents for handwriting. A kill criterion is defined against them.
4. **Evaluation reframed to end-to-end page level.** Segmentation failures count against pipeline engines instead of being excused by line-level benchmarking. This is where the VLM's structural advantage — if it exists — will show.
5. **Hallucination and entity retrieval become headline metrics.** VLMs fail by fluent fabrication, which is the worst possible failure mode for archival search. CER alone hides this.
6. **The offline argument is now concrete.** Not "cloud upload is undesirable" but: German archival material under Schutzfristen or containing personenbezogene Daten often cannot legally be sent to cloud SaaS at all. Offline is a hard requirement for part of the market, not a preference.
7. **Multilingual auxiliary training data is allowed.** CHURRO's strength came partly from breadth across scripts and centuries. Permissive non-German historical data may be used for training robustness; evaluation stays German-only.
8. **Budget restructured into cheap gates:** ~€0 → ~€200 → ~€500–2,000, each with explicit pass/kill criteria.

---

## 3. Core Thesis

The value of a VLM-based system is **not** lower CER on cleanly segmented text lines. That fight is over: mature CRNN models (Calamari on Fraktur, trained PyLaia/Kraken models on known hands) are fast, cheap, and extremely accurate on that task. A 4B VLM burning orders of magnitude more compute to tie them there is not a useful artifact.

The value proposition is everything *around* the recognition step:

> **End-to-end robustness on layout-hostile handwritten pages, graceful degradation on unseen hands, single-step page→text+entities, and legal offline deployability on hardware an archive or hobbyist can actually own.**

CRNN pipelines depend on line detection, and line detection is the silent killer on exactly the material that matters: dense Kurrent with interlinear insertions, marginalia wrapping around text blocks, registry tables where the "line" is a cell, mixed print-and-handwriting forms, curved and degraded layouts. When segmentation fails, the recognizer never sees the text — and line-level CER benchmarks never notice.

If this structural advantage fails to materialize on real pages, the project stops early and ships the benchmark. The benchmark harness, gold set, and corpus manifest are valuable regardless of which model wins.

---

## 4. Problem

German historical documents remain difficult to search, analyze, and translate because OCR/HTR quality varies sharply by script, period, layout, and scan quality.

The hard cases:

* **Fraktur:** historical blackletter print — long-s `ſ`, ligatures, rotunda-r `ꝛ`, historical punctuation and orthography. Largely solved by open CRNN OCR on clean scans; still fails on degraded material and complex layouts.
* **Kurrent / Sütterlin:** old German handwriting systems with letterforms fundamentally different from modern Latin script. Genuinely unsolved in the open, offline ecosystem for arbitrary unseen hands.
* **Archival layouts:** tables, marginalia, forms, registries, mixed print/handwriting, stamps, degraded scans — material that breaks segmentation.
* **Legally restricted material:** documents under Schutzfristen or containing personenbezogene Daten frequently cannot be processed by cloud SaaS under archive law and GDPR. Transkribus On-Premises exists only at enterprise pricing; frontier VLM APIs are unusable for this material entirely.
* **Evaluation confusion:** CER/WER distorted by transcription convention differences (diplomatic vs. normalized), and by benchmark contamination in both directions.

**Who is not served today:**

* Archives with restricted holdings and no enterprise budget.
* Genealogists and local historians with one bundle of letters in one unknown hand — exactly the case where per-hand CRNN fine-tuning is useless.
* Researchers who need a pipeline they can run, inspect, and cite without per-page credits.

---

## 5. Where a VLM Can and Cannot Win

Being honest about this up front prevents wasted budget.

### The VLM path probably cannot win on

* Segmented-line CER on clean printed Fraktur (Calamari/OCR-D territory, often <1% CER).
* Industrial digitization of a single large corpus in one known hand (per-corpus CRNN fine-tuning wins on cost).
* Inference cost per line. A CRNN is orders of magnitude cheaper. This gap never closes.

### The VLM path can plausibly win on

* **Pages that break line detection:** interlinear insertions, marginalia, tables/registries, mixed print+handwriting, curved and dense layouts. End-to-end page→text sidesteps the segmentation stage entirely.
* **Unseen-hand generalization.** The Hodel/Schoch line of work shows general CRNN Kurrent models transfer only moderately to new writers and want per-hand fine-tuning. A VLM with a strong prior plausibly degrades more gracefully on the long tail of hands. This is *the* empirical question of the project.
* **Single-step extraction:** page in → text + names/dates/places out, with reading order, in one robust step.
* **Deployability by non-engineers.** eScriptorium pipelines are operable by DH engineers, not by archivists or genealogists. "Point this offline tool at a folder of scans" is a product only the VLM path delivers.
* **Legal usability:** open weights, offline, no upload, no credits.

Notably, Transkribus itself has moved its flagship models from CRNN-style architectures toward large transformer models — the incumbent's own read on where the ceiling is.

---

## 6. Baselines and the Kill Criterion

The benchmark harness treats every engine as an **end-to-end system: raw page in, text out.** Segmentation failures count against the pipeline, not against the page.

### Engines in benchmark v0

| Engine | Role | License status |
|---|---|---|
| Kraken + community Kurrent/German models | Primary open incumbent (handwriting) | Open |
| PyLaia (Teklia-maintained) | Open incumbent (handwriting) | Open |
| Calamari / OCR-D Fraktur models | Open incumbent (print) | Open |
| Tesseract Fraktur | Legacy baseline | Open |
| Qwen3-VL-4B (zero-shot) | Base model floor | Apache-2.0 |
| Qwen3-VL-8B (zero-shot, if practical) | Base model ceiling check | Apache-2.0 |
| CHURRO | Research reference target | Research-only |
| Transkribus (small credit budget) | Incumbent reference, benchmark only | SaaS |
| Frontier VLMs (optional, unrestricted pages only) | Quality ceiling reference | API |

### Gate 0 kill criterion

> If the open CRNN pipelines (Kraken/PyLaia end-to-end, including their segmentation) handle the ugly-Kurrent and mixed-layout gold pages at a usable level — defined before the run as gist-readable output plus majority entity recall — then the model track is killed and the project ships as a benchmark + corpus manifest, total spend ~€0.

The kill criterion must be written down **before** running the benchmark, because the author is also a competitor in it.

---

## 7. Model Strategy

### Primary base model

**Qwen3-VL-4B-Instruct** — Apache-2.0, modern VLM, strong OCR/document claims, fits comfortably on the Strix Halo for inference and cheap on rented GPUs for LoRA training. **Qwen3-VL-8B-Instruct** as the stretch option if local inference remains practical.

### Comparison / reference models

* **Qwen2.5-VL-7B-Instruct** — Apache-2.0, lineage-compatible with CHURRO's base.
* **CHURRO** — benchmark/reference only; never the legal foundation of the permissive model.
* **PaddleOCR-VL** — compact layout/OCR baseline, not the Kurrent bet.

### Contamination caveat — both directions

Qwen3-VL has almost certainly seen GT4HistOCR, Wikisource, and similar public material in pretraining. **Zero-shot numbers on public benchmarks will flatter it.** The project's own fresh, never-published gold set is therefore the only measurement that fully counts; public benchmarks are for comparability with the literature.

### Expected zero-shot reality (set now, so Gate 0 isn't misread)

* Fraktur zero-shot: probably mediocre-to-decent. Fine.
* Kurrent/Sütterlin zero-shot: probably near-useless despite "32 OCR languages" marketing. **This is expected and is not a kill signal** — it is the premise of the project. The kill signal is defined in §6, and it is about the CRNN incumbents, not the base VLM.

---

## 8. Unit of Recognition

A decision v1 deferred and that shapes everything: line, region, or page?

**Decision:**

* **The product interface is page-level** (optionally region-level for very dense pages). This is where the differentiation lives; adopting a line-based interface would surrender the main advantage and inherit the segmentation dependency.
* **Training uses mixed granularity:** existing permissive line-level datasets are used as line/region crops with appropriate prompts; synthetic data is generated as full pages; PAGE-XML datasets (Reichsanzeiger-GT) supply region-level supervision with layout structure.
* **Evaluation is end-to-end at page level** using alignment-based scoring (align hypothesis to gold page text, then compute CER/WER/entity metrics on the alignment). Line-level scores are additionally reported on line-level benchmarks for comparability with published numbers.
* Reading order is part of the task and part of the score.

---

## 9. Data Strategy

The data strategy remains the moat, but the tiers are restructured. Every item still gets a license manifest entry.

### Tier 1 — Permissive real data

For training the final permissive model. Candidate sources:

* GT4HistOCR
* Reichsanzeiger-GT
* 19th-century German Kurrent dataset (Zenodo)
* Hodel/Schoch-adjacent open material where licenses allow training
* Own public-domain or rights-cleared scans
* **HTR-United registry sweep** — a catalogue of HTR ground truth with license metadata; exactly manifest-shaped input. Sweep it for every German-language, permissively licensed dataset.
* **Permissive non-German historical data as auxiliary training material** (Latin, French, Dutch historical hands and prints from HTR-United and similar). Rationale: CHURRO's robustness came substantially from breadth across scripts and centuries; a German-only corpus risks overfitting to specific hands and periods. Auxiliary data is train-only; all evaluation remains German.

Manifest schema (unchanged from v1):

```yaml
dataset_id:
source_url:
script:
period:
document_type:
license:
commercially_usable: true/false/unknown
transcription_convention:
layout_available: true/false
line_level: true/false
page_level: true/false
used_for_train: true/false
used_for_eval: true/false
notes:
```

### Tier 2 — Research-only benchmark data

Evaluation and comparison only; never in permissive training.

* CHURRO-DS dev/test and German subset
* Anything with research-only or unclear licensing

### Tier 3 — Synthetic data (new; the main engine)

Fully permissive, effectively unlimited, generated locally on the Strix Halo.

**Fraktur synthesis (mature, low-risk):**

* Text sources with period orthography: Deutsches Textarchiv (CC-BY), Wikisource, other public-domain corpora.
* Rendering: period Fraktur fonts (UniFraktur family and others), correct long-s and ligature rules applied programmatically.
* Degradation augmentation: blur, ink bleed-through, warping, binarization artifacts, paper texture, stains, skew (ocrodeg-style).
* Layout composition: synthetic newspapers, registries, tables, title pages, marginalia — full pages with known ground truth and known reading order.

**Kurrent synthesis (staged, higher-risk):**

* **Stage A — script prior:** Kurrent/Sütterlin computer fonts rendered with degradation. Font-rendered Kurrent is *not* handwriting; treat as pretraining curriculum that teaches letterforms, never as evidence of handwriting capability.
* **Stage B — hand diversity:** handwriting synthesis / style transfer trained on the permissive 19th-century Kurrent dataset to expand the variety of hands. Validate strictly against real held-out pages; if Stage B doesn't transfer, drop it rather than let it pollute the corpus.
* **Mixed pages:** composed print+handwriting forms (printed Fraktur labels, synthetic Kurrent entries) — directly targets the layout-hostile differentiator.

**Risk:** synthetic-to-real gap, especially for Kurrent. Mitigation: real permissive data remains the core; synthetic is curriculum and augmentation; every claim is validated on real held-out pages only.

### Tier 4 — Self-training silver data

Pseudo-labels on unlabeled real material — public-domain digitized newspapers, archive portal scans, own material.

Loop:

```text
unlabeled real pages
→ run ensemble (current adapter + CRNN pipelines + base VLM)
→ keep high-agreement outputs, confidence-filtered
→ add as silver training data
→ retrain
→ re-evaluate on FROZEN gold sets only
```

Rules:

* Silver never enters any evaluation set.
* Ensemble diversity is mandatory (a VLM agreeing with itself is not a signal).
* Watch for error entrenchment: if gold-set performance plateaus while silver-set agreement climbs, the loop is feeding on its own mistakes — stop.

Transkribus outputs, if ever used, live in this tier and require written permission first (see §10).

---

## 10. Transkribus Policy (Demoted)

### Use Transkribus for

* Small-scale benchmark comparison within a deliberately capped credit budget (order of €50–100 total).
* Error analysis: where does the incumbent fail on the gold set?

### Do not

* Build the cost model around distillation.
* Treat permission for large-scale output training as likely — READ-COOP has little incentive to bless a distilled open-weight competitor.
* Use Transkribus as the validation target after any distillation (circularity).

### Revisit distillation only if all of the following hold

1. Gates 1 and 2 passed (§15).
2. Synthetic + self-training has demonstrably plateaued on Kurrent.
3. Written permission from READ-COOP is actually in hand.

The community's well-documented frustration with the credit system is not an obstacle to this project — it is the market signal that the niche is open.

**Pricing record (for reference; no longer a planned cost):** 250 credits ≈ €59.50; handwriting 1 credit/page + line detection 0.25 credits/page; Organisation API −50%. At those rates: 5k pages ≈ €745–1,490; 20k ≈ €2,975–5,950; 50k ≈ €7,438–14,875.

---

## 11. Benchmark Strategy

The project should become a standing German historical HTR benchmark — one useful to others even if this project's model loses on it.

### Metrics

**Recognition quality:**

* CER / WER — reported separately for **diplomatic** and **normalized** transcription conventions. Long-s `ſ` vs `s`, `ß`, ligatures, abbreviation expansion and historical spelling distort CER when conventions are mixed; normalization must be explicit and reproducible.
* NLS (Normalized Levenshtein Similarity) for CHURRO comparability.
* End-to-end page-level scores via alignment (§8); reading-order errors scored.
* Segmentation-failure rate for pipeline engines (pages where line detection visibly collapses).

**Trust metrics (headline, first-class):**

* **Fabrication rate:** alignment-based insertion rate — fluent output text unsupported by the page. The characteristic VLM failure and the one that destroys archival trust.
* **Entity recall and precision:** names, dates, places against gold annotations. Recall operationalizes "search usefulness"; precision catches fabricated names. This is the metric that distinguishes the benchmark from another CER leaderboard.
* **Abstention behavior:** does the engine mark illegible passages as illegible, or invent?

**Utility metrics:**

* Correction-time proxy: is the output faster to correct than transcribing from scratch?

All metrics broken down per script, period, layout category, and degradation category.

### Benchmark sets

1. **Own fresh gold set — 30–50 pages** (upgraded from v1's 5–10, which was too thin to support any spend decision). Stratified across: clean Fraktur, degraded Fraktur, tidy Kurrent, ugly Kurrent, Sütterlin, table/registry, marginalia, mixed print/handwriting. Never published in training-usable form; annotated with entities. This is the single most valuable asset in the project, because it is the only set contamination-proof in both directions. A few days of the author's own transcription time against every future budget decision.
2. **CHURRO dev/test + German subset** — research comparison only; never trained on; never over-optimized against.
3. **GT4HistOCR** — Fraktur line-level, comparability with literature; beware mixed transcription guidelines.
4. **Reichsanzeiger-GT** — Fraktur layout/tables/PAGE-XML/reading order.
5. **19th-century German Kurrent dataset** — with overlap/contamination checks against training use of the same source.
6. **Hodel/Schoch Kurrent test set** — independent 19th-century Kurrent benchmark; also the reference point for the unseen-hand generalization question.

### Benchmark hygiene

The author competes in his own benchmark, so the benchmark must be credible to the OCR-D / UB Mannheim / eScriptorium communities:

* Protocol written and versioned **before** results (BENCHMARK_PROTOCOL.md).
* Splits frozen and hashed; contamination checks documented.
* Harness code public from the start.
* Every engine run with documented, reproducible settings; no cherry-picked prompts.

---

## 12. Hallucination Policy

A CRNN fails loudly: visible garbage. A VLM fails silently: fluent, plausible German that was never on the page. For the target use case — searching archival material for names, dates, and places — silent fabrication is strictly worse than noise.

Consequences for the project:

* Fabrication rate and entity precision are release-gating metrics, not diagnostics.
* Training includes abstention: illegible or uncertain passages should be marked (`[unleserlich]` or similar), and synthetic data should include genuinely illegible regions with abstention as the gold answer.
* The product surfaces uncertainty: per-region confidence, visual flagging of low-confidence passages in the side-by-side viewer.
* Decoding constraints (temperature, repetition handling, optional constrained decoding for structured fields) are part of the engineering, not an afterthought.

---

## 13. Hardware & Deployment

The Strix Halo machine (Ryzen AI Max+ 395, 96GB unified memory, ROCm) is not just the dev box — it is the **reference deployment target**. The deliberate constraint: the model must run well on hardware an archive, a genealogy society, or a hobbyist could plausibly own. This constraint is a feature; it keeps the model small and the product honest.

### Strix Halo handles

* Qwen3-VL-4B inference comfortably; 8B likely workable.
* CHURRO and CRNN baselines for the harness.
* Batch evaluation, scoring, normalization.
* Synthetic data generation (rendering + degradation is CPU/GPU-light).
* Self-training inference loops over unlabeled corpora.
* Dashboard and orchestration (existing n8n/Docker infra).

### Rented NVIDIA handles

* LoRA/adapter training runs and sweeps. A 4B LoRA fits single-4090/A6000-class rentals; without a 50k-page distillation corpus, training scale is modest and runs are cheap (tens of euros per serious run at current spot prices).
* Do not fight ROCm training; it is allowed to work but not allowed to become the project.

---

## 14. Product Shape

The first artifact is a reproducible benchmark and offline pipeline; the second is the model. Together they converge on:

> **An offline tool: point it at a folder of scans → get searchable text, PAGE-XML/hOCR, an entity index (names, dates, places), uncertainty flags, and a side-by-side viewer.**

Components:

1. Input folder of scans.
2. Engine runners: Qwen3-VL (+adapter), Kraken/PyLaia, Calamari, CHURRO, optional Transkribus/frontier for benchmarking.
3. Normalization layer (diplomatic ↔ normalized, explicit rules).
4. Scoring layer (all §11 metrics).
5. Text + PAGE-XML output with reading order.
6. Entity extraction and index.
7. Side-by-side comparison viewer with uncertainty highlighting.
8. Adapter training pipeline (rental-GPU scripts, containerized).
9. Versioned results store + dashboard.

### Users, in order of certainty

1. The author (Bundesarchiv-adjacent material, rare book and archival projects).
2. Archives and institutions with legally restricted holdings and no enterprise budget.
3. Genealogists and local historians with small bundles in unknown hands.
4. DH researchers who need citable, reproducible, credit-free pipelines.

### Releases

Model weights (Apache-2.0-compatible), corpus manifest, synthetic pipeline, benchmark harness and protocol — all public. The corpus manifest and benchmark are useful to the community even if a better model appears next month; that is the durable contribution.

---

## 15. Success Criteria & Gates

### Gate 0 — Benchmark v0 (~€0, local compute only)

Build the harness, assemble the 30–50 page gold set, run all engines end-to-end.

**Pass:** CRNN pipelines demonstrably fail end-to-end on the layout-hostile and unseen-hand categories, AND the VLM path (base model + CHURRO as proof-of-ceiling) shows structural promise there.
**Kill:** open CRNN pipelines handle those categories at a usable level (§6). Ship the benchmark, stop the model track.

Per-script expectation-setting: Kurrent zero-shot near-uselessness is expected, not a kill signal.

### Gate 1 — First adapter (~€200 GPU rental)

Train Qwen3-VL LoRA on Tier 1 permissive real + Tier 3 synthetic data.

**Pass:** clear improvement over base Qwen3-VL on the fresh gold set; beats or matches CRNN pipelines end-to-end on the hard categories; approaches CHURRO on German Fraktur and tidy Kurrent; fabrication rate within the pre-defined bound.
**Kill:** no meaningful improvement over base, or fabrication uncontrollable.

### Gate 2 — Self-training scale-up (~€500–2,000)

Self-training loop over unlabeled real material + adapter sweeps + script-specific adapters.

**Pass:** Kurrent usefulness threshold on unseen hands — gist-readable output plus majority entity recall on the ugly-Kurrent gold category; correction faster than manual transcription.
**Kill:** self-training plateaus or entrenches; then either revisit Transkribus distillation under §10's conditions, or accept the current level and ship.

### Later

* Human-corrected disagreement set (only disagreement / low-confidence pages) to push past teacher-free limits in targeted domains.
* Public benchmark adoption by other researchers.
* Legally clean corpus and model releases.

---

## 16. Non-Goals

* Beating CRNNs on clean segmented-line CER. Conceded by design.
* Beating Transkribus globally across all material.
* Full multilingual CHURRO replication.
* Training from scratch.
* A commercial SaaS.
* Perfect Kurrent transcription without human correction.
* Enterprise deployment features before benchmark confidence exists.

---

## 17. Main Risks

### 1. The VLM edge may not exist
Gate 0 is designed to find this out for ~€0. If it kills the project, a useful public benchmark still shipped.

### 2. Synthetic-to-real gap (especially Kurrent)
Font-rendered Kurrent is not handwriting. Mitigation: real permissive data stays the core; synthetic is curriculum/augmentation; Stage B style transfer validated on real held-out or dropped; no capability claims from synthetic performance.

### 3. Self-training entrenchment
Pseudo-labels can amplify the model's own errors. Mitigation: frozen gold sets, mandatory ensemble diversity, agreement-vs-gold divergence monitoring, silver never in evaluation.

### 4. Hallucination
Fluent fabrication destroys the search use case. Mitigation: release-gating fabrication metrics, abstention training, uncertainty surfacing (§12).

### 5. Licensing
Reduced exposure now that Transkribus distillation is off the critical path. Remaining discipline: strict manifest, CHURRO-DS out of permissive training, research-only experiments cleanly separated, auxiliary multilingual data license-checked like everything else.

### 6. Contamination, both directions
Qwen3-VL has likely seen the public benchmarks; CHURRO has too. Mitigation: fresh gold set is the ground truth of record; hash overlap checks; public numbers reported with the caveat.

### 7. ROCm training friction
Rent NVIDIA for training; Strix Halo stays the inference/eval worker.

### 8. Solo-project scope creep
The gates are the mitigation. No spend without the previous gate passing, in writing, in DECISIONS.md.

---

## 18. Immediate Plan

### Step 1 — Benchmark v0 harness
Raw page in → engine → normalization → alignment → CER/WER/NLS + entity + fabrication scoring → markdown/HTML comparison sheet. Engines: Qwen3-VL-4B, Kraken (+ community Kurrent models), PyLaia, Calamari/OCR-D Fraktur, CHURRO. End-to-end; segmentation failures counted.

### Step 2 — Source manifest
`datasets.yml` for every dataset. Full HTR-United sweep for German and auxiliary permissive material.

### Step 3 — Gold set
Assemble and transcribe 30–50 fresh pages, stratified across the eight categories, entity-annotated. Budget a few evenings of transcription; it underwrites every later decision.

### Step 4 — Run Gate 0
Write BENCHMARK_PROTOCOL.md and the kill criterion *first*, then run, then publish results either way.

### Step 5 — Synthetic pipeline
Fraktur synthesis end-to-end (DTA text × fonts × degradation × layout composition). Kurrent Stage A fonts. Generated locally.

### Step 6 — First adapter (Gate 1, ~€200)
LoRA on permissive real + synthetic. Evaluate on gold set against Gate 1 criteria.

### Step 7 — Self-training loop (Gate 2)
Only if Gate 1 passes.

---

## 19. Repository Structure

```text
/german-historical-htr
  /docs
    VISION.md
    DECISIONS.md
    LICENSE_NOTES.md
    BENCHMARK_PROTOCOL.md

  /data
    datasets.yml
    manifests/
    raw/
    processed/
    splits/
    contamination/
    gold/                # own fresh gold set + entity annotations

  /harness
    engines/
      qwen3vl/
      kraken/
      pylaia/
      calamari/
      churro/
      transkribus/       # benchmark-only, capped budget
    normalization/
    alignment/
    scoring/             # incl. entity + fabrication metrics
    reports/

  /synthetic
    fraktur/
      textsources/
      fonts/
      degradation/
      layouts/
    kurrent/
      fonts/             # Stage A
      styletransfer/     # Stage B
    composed_pages/

  /selftraining
    unlabeled/
    ensemble/
    silver/
    monitoring/

  /training
    configs/
    lora/
    scripts/
    containers/

  /evals
    own_gold/
    churro/
    gt4histocr/
    reichsanzeiger/
    kurrent_19c/
    hodel_schoch/

  /dashboard
    app/
    db/

  /infra
    docker/
    n8n/
    workers/
```

---

## 20. Decision Log

### v2 decisions

1. Transkribus distillation is off the critical path; benchmark-only within a capped credit budget; revisit only under §10's three conditions.
2. Synthetic data + self-training is the primary data engine.
3. Kraken/PyLaia/eScriptorium-ecosystem models are first-class baselines; Gate 0 kill criterion defined against them before any benchmark run.
4. Evaluation is end-to-end page-level; segmentation failures count against pipeline engines.
5. Fabrication rate and entity recall/precision are headline, release-gating metrics.
6. Fresh gold set is 30–50 stratified, entity-annotated pages; it is the measurement of record.
7. Page/region-level is the product interface; training uses mixed granularity.
8. Permissive multilingual auxiliary data allowed for training; evaluation stays German-only.
9. Strix Halo is the reference deployment target, not just the dev box.
10. Budget gates: ~€0 → ~€200 → ~€500–2,000, each with written pass/kill criteria.
11. Benchmark protocol and code are public from the start.

### Carried over from v1

12. No training on CHURRO-DS for the permissive model; CHURRO is reference and benchmark.
13. Qwen3-VL-4B/8B as primary permissive base candidates.
14. Fraktur is warm-up; Kurrent/Sütterlin + layout + offline is the differentiator.
15. Strict license manifest for everything.
16. Human correction excluded from early phases; later only for disagreement/hard cases.

### Superseded from v1

* ~~Transkribus as the Kurrent teacher and major cost center~~ → §10.
* ~~5–10 page gold set~~ → 30–50 pages.
* ~~German-only training corpus~~ → German-only *evaluation*; auxiliary permissive multilingual training allowed.
* ~~€1,000–20,000 budget tiers driven by Transkribus credits~~ → gated GPU-rental budget.

---

## 21. Working Pitch

> German archival material in Kurrent and Sütterlin is effectively unreadable to almost everyone, and the material that most needs transcription — restricted holdings, personal papers, records under Schutzfristen — often cannot legally be uploaded to cloud services at all. We are building a small open model and a standing public benchmark for German historical text recognition that runs offline on affordable hardware. We don't compete with mature open OCR on clean printed lines, and we don't rent the incumbent's models back page by page. The bet is specific: modern vision-language models can read whole difficult pages — bad hands, marginalia, tables, mixed print and script — where segmentation-based pipelines fall apart. The benchmark tells everyone, reproducibly, whether that bet pays off, which engine works on which material, and which pages truly need a human expert. The model, corpus manifest, and harness are released openly either way.

---

## 22. References

### CHURRO

1. CHURRO paper — https://arxiv.org/abs/2509.19768
2. CHURRO paper, HTML — https://arxiv.org/html/2509.19768v1
3. CHURRO GitHub — https://github.com/stanford-oval/Churro
4. CHURRO model — https://huggingface.co/stanford-oval/churro-3B
5. CHURRO dataset — https://huggingface.co/datasets/stanford-oval/churro-dataset

### Base models

6. Qwen3-VL-4B-Instruct — https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct
7. Qwen3-VL-8B-Instruct — https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct
8. Qwen3-VL technical report — https://arxiv.org/abs/2511.21631
9. Qwen2.5-VL technical report — https://arxiv.org/abs/2502.13923
10. Qwen2.5-VL-7B-Instruct — https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
11. Qwen2.5-VL-3B license (CHURRO lineage) — https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct/blob/main/LICENSE
12. Qwen research license — https://github.com/QwenLM/Qwen/blob/main/Tongyi%20Qianwen%20RESEARCH%20LICENSE%20AGREEMENT
13. PaddleOCR-VL-1.5 — https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5

### Open CRNN/HTR ecosystem (baselines & incumbents)

14. Kraken — https://kraken.re / https://github.com/mittagessen/kraken
15. eScriptorium — https://gitlab.com/scripta/escriptorium
16. PyLaia — https://github.com/jpuigcerver/PyLaia (Teklia-maintained fork in production use)
17. Calamari — https://github.com/Calamari-OCR/calamari
18. OCR-D Calamari — https://github.com/OCR-D/ocrd_calamari
19. OCR-D project — https://ocr-d.de
20. State-of-the-art Fraktur OCR with open-source engines — https://arxiv.org/abs/1810.03436

### Datasets & registries

21. HTR-United — https://htr-united.github.io
22. GT4HistOCR (Zenodo) — https://zenodo.org/records/1344132
23. GT4HistOCR paper — https://arxiv.org/abs/1809.05501
24. Reichsanzeiger-GT — https://github.com/UB-Mannheim/reichsanzeiger-gt
25. Reichsanzeiger-GT paper — https://pmc.ncbi.nlm.nih.gov/articles/PMC10980999/
26. 19th-century German Kurrent dataset — https://zenodo.org/records/17252677
27. Hodel/Schoch Kurrent benchmark paper — https://openhumanitiesdata.metajnl.com/articles/10.5334/johd.46
28. Hodel/Schoch Kurrent test set — https://doi.org/10.5281/zenodo.4746341
29. Swiss Federal Council minutes dataset — https://zenodo.org/records/4905561
30. ScaDS.AI German handwriting data — https://scads.ai/open-data-for-german-handwriting-recognition/
31. ScaDS.AI dataset — https://zenodo.org/records/18301532
32. Deutsches Textarchiv (synthetic text source, CC-BY) — https://www.deutschestextarchiv.de

### Synthetic data tooling

33. ocrodeg document degradation — https://github.com/NVlabs/ocrodeg
34. UniFraktur fonts — https://unifraktur.sourceforge.net

### Transkribus (benchmark reference only)

35. Plans/pricing — https://www.transkribus.org/plans
36. Credit system — https://help.transkribus.org/credit-system
37. Legal terms — https://legal.transkribus.org/terms
38. German Kurrent & Sütterlin model — https://www.transkribus.org/models/german-kurrent-and-sutterlin-17th-20th-century
39. On-Premises — https://www.transkribus.org/onprem/details

### Broader context

40. MLLM vs Transkribus-style HTR benchmark — https://arxiv.org/abs/2503.15195
41. Image-to-text LMs for 19th-century newspapers — https://arxiv.org/abs/2502.14901

### Hardware / cost

42. AMD Strix Halo local LLM article — https://www.amd.com/en/developer/resources/technical-articles/2026/how-to-run-a-one-trillion-parameter-llm-locally-an-amd.html
43. Lemonade SDK llama.cpp ROCm builds — https://github.com/lemonade-sdk/llamacpp-rocm
44. RunPod pricing — https://www.runpod.io/pricing
45. Vast.ai pricing — https://vast.ai/pricing

---

## 23. Current Bottom Line

The project is a cheap, well-gated bet with a guaranteed consolation prize.

Do not frame it as:

> "I will beat Transkribus" or "I will replicate CHURRO."

Frame it as:

> "I will build the standing benchmark that shows where open German historical HTR actually stands end-to-end — and a small offline model that targets the specific gap the benchmark exposes: difficult handwritten pages, unseen hands, and material that can never leave the building."

The first artifact is the benchmark and the 30–50 page gold set (~€0).
The first technical artifact is a Qwen3-VL adapter trained on permissive + synthetic data (~€200).
The main engine is synthetic data and self-training, not purchased teacher labels.
The consolation prize, if the model loses, is a public benchmark the field needs anyway.
The later moat is human-corrected disagreement data.
