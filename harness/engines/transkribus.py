"""Transkribus engine: reads text exported from the Transkribus web app.

The API is not available on the account's plan, so recognition runs in the web
app and this engine reads the plain-text export back in. Config keys:

    model: display name of the public model (e.g. "Text Titan II")
    model_id: numeric Transkribus model id, fixed before the first run (§6)
    export_dir: folder holding one ``{image stem}.txt`` per page
    credit_cap: total credits this engine may consume (VISION §10 budget)

A missing export file is an error, never an empty transcription: an empty
string would score as a segmentation failure the engine did not commit.
"""

from __future__ import annotations

import time
from pathlib import Path

from harness.engines.base import (
    Engine,
    EngineError,
    EngineOutput,
    EngineUnavailable,
    sha256_file,
)


class TranskribusEngine(Engine):
    def check(self) -> None:
        required = ("model", "model_id", "export_dir", "credit_cap")
        missing = [key for key in required if key not in self.config]
        if missing:
            raise EngineUnavailable(f"transkribus config missing: {', '.join(missing)}")
        if not self._export_dir().is_dir():
            raise EngineUnavailable(
                f"transkribus export dir not found: {self._export_dir()}"
            )

    def transcribe(self, image: Path) -> EngineOutput:
        self.check()
        start = time.monotonic()
        export = self._export_dir() / f"{image.stem}.txt"
        if not export.exists():
            raise EngineError(f"no Transkribus export for {image.stem}: {export}")
        text = export.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        return EngineOutput(
            text=text,
            model_id=f"transkribus:{self.config['model_id']}",
            duration_s=time.monotonic() - start,
            meta={"export_file": str(export), "export_sha256": sha256_file(export)},
        )

    def describe(self) -> dict:
        return {"type": "transkribus", "config": self.config}

    def _export_dir(self) -> Path:
        return Path(str(self.config.get("export_dir", "")))
