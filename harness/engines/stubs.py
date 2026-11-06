"""Engines registered but not yet implemented, with actionable messages.

Kept as first-class registry entries so `--engines pylaia` fails loudly with
instructions instead of silently not existing.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from harness.engines.base import Engine, EngineOutput, EngineUnavailable


class _StubEngine(Engine):
    unavailable_message: ClassVar[str]

    def check(self) -> None:
        raise EngineUnavailable(self.unavailable_message)

    def transcribe(self, image: Path) -> EngineOutput:
        self.check()
        raise AssertionError("unreachable")


class PylaiaEngine(_StubEngine):
    unavailable_message = (
        "pylaia engine not implemented in v0 — install teklia-pylaia, pick a public "
        "German/Kurrent model, and mirror harness/engines/calamari.py's two-stage pipeline"
    )

