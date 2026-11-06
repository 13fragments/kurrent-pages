# Repository boundaries

## Data flow

```text
model repository -- prediction bundle --> private evaluation repository
                                                  |
                                                  +-- aggregate result/report --> benchmark release
```

No held-out image, transcription, entity label, or page-specific debugging
signal flows back to the model repository. Model development uses separately sourced
training data and an explicit development split. The silver set in this repo
tests harness behavior only; it is not evidence of model quality.

## Vocabulary

- **Gold**: held-out benchmark targets only; private evaluation data.
- **Train**: data permitted for parameter updates.
- **Dev/validation**: non-benchmark data permitted for model selection.
- **Silver**: machine-generated labels; provenance must name the generator.

## Release rule

This repository was initialized from a sanitized snapshot. The original
history became a private archive repository because it contains private
correspondence. Never graft or merge that history here. Run
`scripts/check_boundary.py` before changing visibility or publishing a release.

