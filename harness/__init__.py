"""Benchmark harness for the German historical HTR gold set.

Implements BENCHMARK_PROTOCOL.md v0.1-freeze: end-to-end page->text runs
(engines/, runner), the normalization layers (normalization), and the
pre-registered metrics (scoring, entities, alignment).
"""

PROTOCOL_VERSION = "0.1-freeze"
SCORING_SCHEMA_VERSION = "0.2-draft"
