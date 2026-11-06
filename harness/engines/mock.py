"""Mock engine for harness smoke tests and dry runs.

Config keys: text (fixed string) or text_dir (reads {image stem}.txt;
missing file -> empty output, which exercises the seg-fail path);
completion_tokens (optional; reported as token usage, with max_tokens, to
exercise the loop guard's token-limit trigger).
"""

from __future__ import annotations

import time
from pathlib import Path

from harness.engines.base import Engine, EngineOutput


class MockEngine(Engine):
    def transcribe(self, image: Path) -> EngineOutput:
        start = time.monotonic()
        text_dir = self.config.get("text_dir")
        if text_dir:
            candidate = Path(text_dir) / f"{image.stem}.txt"
            text = candidate.read_text(encoding="utf-8") if candidate.exists() else ""
        else:
            text = self.config.get("text", "")
        meta = {}
        if self.config.get("completion_tokens") is not None:
            meta["usage"] = {"completion_tokens": self.config["completion_tokens"]}
        return EngineOutput(text=text, model_id="mock", duration_s=time.monotonic() - start, meta=meta)

    def describe(self) -> dict:
        return {"type": "mock", "config": self.config}
