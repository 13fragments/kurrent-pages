---
read_when: You publish or cite release v1.0.2 of the Kurrent Pages Benchmark.
---

# Kurrent Pages Benchmark v1.0.2 release notes

Documentation release. The benchmark version stays v1.0: the ground truth, the
pages, the prompts, the scoring code, and every score are those of v1.0.0, so
scores compare directly across v1.0.0, v1.0.1, and v1.0.2.

v1.0.2 replaces v1.0.1 for archiving: Zenodo could not read the citation file
of v1.0.1, so v1.0.1 has no Zenodo record. v1.0.2 contains every v1.0.1 change.

## Changes since v1.0.0

- **Leaderboard label.** The 9B row is now "13fragments 9B (internal, Run 11)"
  with the category "internal model-track run, not released". It was labelled
  a research preview; that model will not be released. Its scores are
  unchanged.
- **Citation metadata.** `CITATION.cff` names 13fragments as author, gives the
  concept DOI 10.5281/zenodo.24015417 (it resolves to the latest version), and
  has one licence value (Apache-2.0) so that Zenodo can read it. The protocol,
  documentation, and leaderboard stay CC BY 4.0.
