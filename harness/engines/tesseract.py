"""Tesseract legacy baseline (VISION §6: Tesseract Fraktur).

Config keys: binary (default "tesseract"), lang (default "frk"), psm (default 3),
extra_args (list). Install: `brew install tesseract tesseract-lang` or distro
package + the `frk`/`deu_latf` traineddata.
"""

from __future__ import annotations

import time
from pathlib import Path

from harness.engines.base import (
    Engine, EngineError, EngineOutput, EngineUnavailable, command_version, run_command,
)


class TesseractEngine(Engine):
    def transcribe(self, image: Path) -> EngineOutput:
        lang = self.config.get("lang", "frk")
        command = [
            self.config.get("binary", "tesseract"),
            str(image),
            "stdout",
            "-l",
            lang,
            "--psm",
            str(self.config.get("psm", 3)),
            *self.config.get("extra_args", []),
        ]
        start = time.monotonic()
        result = run_command(command)
        if result.returncode != 0:
            # Missing traineddata is a local setup problem, not an OCR result —
            # it must abort the engine, never score as an empty hypothesis.
            if "Failed loading language" in result.stderr or "tessdata" in result.stderr:
                raise EngineUnavailable(f"tesseract language data broken: {result.stderr.strip()}")
            raise EngineError(f"tesseract failed on {image.name}: {result.stderr.strip()}")
        return EngineOutput(
            text=result.stdout.strip("\n"),
            model_id=f"tesseract:{lang}",
            duration_s=time.monotonic() - start,
        )

    def check(self) -> None:
        """Verify the configured language data actually loads."""
        lang = self.config.get("lang", "frk")
        command = [
            self.config.get("binary", "tesseract"),
            "--list-langs",
            *self.config.get("extra_args", []),
        ]
        result = run_command(command, timeout=30)
        available = {line.strip() for line in result.stdout.splitlines()[1:] if line.strip()}
        if result.returncode != 0 or lang not in available:
            raise EngineUnavailable(
                f"tesseract lang {lang!r} not available (have: {sorted(available)}) — "
                "install the traineddata or fix --tessdata-dir in extra_args"
            )

    def describe(self) -> dict:
        return {
            "type": "tesseract",
            "version": command_version([self.config.get("binary", "tesseract"), "--version"]),
            "config": self.config,
        }
