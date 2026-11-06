"""Kraken end-to-end pipeline (VISION §6: primary open handwriting incumbent).

Runs kraken's own baseline segmentation + recognition in one CLI invocation, so
segmentation quality counts against the engine (protocol §1).

Config keys: binary (default "kraken"), model (required: .mlmodel path), command
(optional list template overriding the default pipeline; placeholders {binary}
{image} {output} {model}). Install: `uv tool install kraken`; community German
Kurrent models e.g. via https://zenodo.org/communities/ocr_models.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from harness.engines.base import (
    Engine, EngineError, EngineOutput, EngineUnavailable, command_version,
    file_fingerprints, run_command,
)

_DEFAULT_COMMAND = [
    "{binary}", "-i", "{image}", "{output}", "binarize", "segment", "-bl", "ocr", "-m", "{model}",
]


class KrakenEngine(Engine):
    def transcribe(self, image: Path) -> EngineOutput:
        model = self._model()
        binary = self.config.get("binary", "kraken")
        template = self.config.get("command", _DEFAULT_COMMAND)
        with tempfile.TemporaryDirectory(prefix="kraken_") as tmp:
            output = Path(tmp) / "page.txt"
            command = [
                part.format(binary=binary, image=image, output=output, model=model)
                for part in template
            ]
            start = time.monotonic()
            result = run_command(command, timeout=self.config.get("timeout", 600.0))
            duration = time.monotonic() - start
            if result.returncode != 0 or not output.exists():
                raise EngineError(f"kraken failed on {image.name}: {result.stderr.strip()[-500:]}")
            text = output.read_text(encoding="utf-8")
        return EngineOutput(text=text.strip("\n"), model_id=f"kraken:{Path(model).name}", duration_s=duration)

    def check(self) -> None:
        self._model()
        self.describe()

    def _model(self) -> str:
        model = self.config.get("model")
        if not model or not Path(model).exists():
            raise EngineUnavailable(
                f"kraken model not found: {model!r} — download a community Kurrent/German "
                "recognition model and set `model:` in configs/engines.yml"
            )
        return model

    def describe(self) -> dict:
        return {
            "type": "kraken",
            "version": command_version([self.config.get("binary", "kraken"), "--version"]),
            "model_files": file_fingerprints(self._model()),
            "config": self.config,
        }
