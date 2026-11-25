# Kurrent Pages practice set

This set has seven page images with their transcriptions. Use it to test your
engine pipeline and the submission format of the
[Kurrent Pages Benchmark](https://github.com/13fragments/kurrent-pages) on your
own computer. You get a score in a few minutes. Then you can send your outputs
for the private scoring with less risk of a format error.

## This set is not the benchmark

- The 53 benchmark pages and their transcriptions are private. None of the
  practice pages is a benchmark page.
- The practice transcriptions are public, and models can have trained on them.
  All seven pages come from datasets that we use to train our own models.
- A practice score checks that your pipeline runs and that your files have the
  correct format. The benchmark pages come from other sources, so the scores
  differ.
- Do not report a practice score as a benchmark result.
- Seven pages are too few to compare two engines.

## Contents

| Path | Contents |
|---|---|
| `images/P01.jpg` … `images/P07.jpg` | page images |
| `gt/P01.txt` … `gt/P07.txt` | transcriptions |
| `entities/P01.yml` … `entities/P07.yml` | persons, places, and dates on each page |
| `selection.yml` | page list for the harness |
| `pages.sha256` | SHA-256 hash of each image |
| `metadata.csv` | source, licence, attribution, and stratum of each page |

## Pages

| ID | Document | Date | Script | Stratum |
|---|---|---|---|---|
| P01 | letter | 1829 | Kurrent | `ugly_kurrent` |
| P02 | letter | 1864 | Kurrent | `tidy_kurrent` |
| P03 | minutes with a margin note | 1850 | Kurrent | `marginalia` |
| P04 | minutes | 1794–95 | Kurrent | `tidy_kurrent` |
| P05 | lecture notes | 1827–28 | Kurrent | `tidy_kurrent` |
| P06 | lecture notes | 1828 | Latin-script handwriting | `latin_cursive` |
| P07 | printed notice from a newspaper | 1893 | Fraktur | `clean_fraktur` |

The set has no Sütterlin page. We found no Sütterlin source with open licences
for both the image and the transcription.

## Transcriptions

The transcriptions follow section 3 of `BENCHMARK_PROTOCOL.md`. Some examples:

- Handwriting: every long s is `s`. Print: the long s stays `ſ`.
- Line breaks stay as on the page. A hyphen at a line end stays.
- An unkeyed margin note follows its text block on its own line, after `⟪M⟫ `.
- A page or item number in the margin is its own line.
- `⟪Z⟫` marks a sign without letter value. The harness does not score it.
- `⟦ ⟧` marks an uncertain reading. The harness scores it as normal text.

We converted each transcription from its source edition and checked it against
the image. We did not key the pages again. Some errors can remain. Send
corrections to `kurrent-pages@13fragments.com`.

## Score your engine

You need a checkout of the benchmark repository and
[uv](https://docs.astral.sh/uv/). Run every command in the repository folder.
The practice set is in its `practice/` folder.

1. Install the harness:

   ```sh
   git clone https://github.com/13fragments/kurrent-pages.git
   cd kurrent-pages
   uv sync
   ```

2. Run your engine on each image. Write a bundle in the format of
   `SUBMITTING.md`, with the practice page IDs:

   ```
   my_engine_1.0/
     run.json
     pages/
       P01.txt
       ...
       P07.txt
   ```

   In `run.json`, set `benchmark_version` to `Kurrent Pages practice set`. For
   `image_sha256`, use the hashes in `pages.sha256`. This command prints them
   in the correct form:

   ```sh
   python3 -c "import json; print(json.dumps({n[:-4]: h for h, n in (l.split() for l in open('practice/pages.sha256'))}, indent=2))"
   ```

3. Import the bundle. The importer checks the bundle format and the image
   hashes:

   ```sh
   uv run python scripts/import_submission.py --bundle my_engine_1.0 \
     --selection practice/selection.yml --sha practice/pages.sha256 \
     --runs-root practice_runs
   ```

   The importer prints the run folder.

4. Score the run:

   ```sh
   uv run python -m harness --selection practice/selection.yml \
     --sha practice/pages.sha256 --images practice/images \
     --gt practice/gt --entities practice/entities \
     report --run-dir practice_runs/<run folder>
   ```

   The harness writes `report.md` in the run folder, with the score of each
   page. Add `--aggregates-only --out <folder>` to get the summary in the
   form that the leaderboard uses.

   The harness output says "Benchmark aggregates" and prints a kill-criterion
   line. These labels come from the benchmark code. On this set, every number
   is a practice score.

If your engine has an adapter in `configs/engines.yml`, the harness can also
run it on the practice pages. Use the same options as in step 4, and replace
`report --run-dir …` with `run --engines <name> --runs-root practice_runs`.
Then score the run as in step 4.

## Licences and attribution

The images and the transcriptions keep the licences of their sources. All of
them allow reuse with attribution. `metadata.csv` gives the full attribution
of each page.

| Pages | Image | Transcription |
|---|---|---|
| P01 | Staatsbibliothek zu Berlin, MA Depos. 3,5; Public Domain Mark 1.0 | "Fanny loves Wilhelm" letter transcriptions, [doi:10.5281/zenodo.15223355](https://doi.org/10.5281/zenodo.15223355); CC BY 4.0 |
| P02 | ICDAR2017 READ dataset (Escher letters, Staatsarchiv Zürich), [doi:10.5281/zenodo.835489](https://doi.org/10.5281/zenodo.835489); CC BY 4.0 | same dataset; CC BY 4.0 |
| P03 | Akademieprotokolle, Austrian Academy of Sciences (ÖAW) and ACDH-CH; CC BY 4.0 | [acdh-oeaw/akademie-data](https://github.com/acdh-oeaw/akademie-data); CC BY 4.0 |
| P04 | Konzilsprotokolle, Universitätsarchiv Greifswald, READ dataset [doi:10.5281/zenodo.215383](https://doi.org/10.5281/zenodo.215383); CC BY 4.0 | same dataset; CC BY 4.0 |
| P05, P06 | Staatsbibliothek zu Berlin, Ms. germ. qu. 2345 and Ms. germ. qu. 1711; Public Domain Mark 1.0 | [Deutsches Textarchiv](https://www.deutschestextarchiv.de/), Hidden Kosmos project; CC BY 4.0 |
| P07 | Deutscher Reichsanzeiger, Universitätsbibliothek Mannheim; Public Domain Mark 1.0 | [UB-Mannheim/reichsanzeiger-gt](https://github.com/UB-Mannheim/reichsanzeiger-gt); CC0 1.0 |

Our changes:

- P07 is one notice cut from a newspaper page.
- The transcriptions were converted to the benchmark conventions.
  `metadata.csv` lists each change.

The page list, the metadata, the entity lists, and our changes to the
transcriptions are published by 13fragments under CC BY 4.0.
