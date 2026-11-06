# Repository guardrails

- Benchmark-only repository: protocol, harness, public manifests, baselines,
  and synthetic/model-generated silver fixtures.
- Never add held-out images, gold transcriptions, gold entity annotations,
  freelancer correspondence, invoices, or agreements.
- `gold/` means public benchmark metadata only. Private targets belong in
  the private evaluation repository (the sibling checkout named in `README.md`).
- Never import or copy code from the model repository that needs access to held-out
  targets.
- Run `uv run python scripts/check_boundary.py` and `uv run pytest` before push.

