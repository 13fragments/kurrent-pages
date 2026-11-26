"""Engines whose authors' own page pipeline runs behind an HTTP endpoint (§10 2026-11-25, batch 3).

Some document-OCR models are published with a page pipeline, not a single model request: a layout step and region
requests (GLM-OCR SDK), image preparation and a JSON-to-Markdown step (dots.ocr parser), or a package with its own
request loop and output step (Chandra). Their text must come out through the authors' own code. Each such pipeline
runs on the serving machine behind `scripts/pipeline_server.py`, which calls the authors' code once per page. This
engine sends the frozen page image and stores the text that the authors' code returns.

Config keys: base_url (the pipeline server, e.g. "http://localhost:8080"), pipeline (the name the server was started
with; a server that reports another name is treated as an unavailable endpoint), model (the served alias of the
model behind the pipeline), weights_sha256 and package (recorded only), timeout (default 1800).

The request carries the image bytes unchanged and the file suffix only, never the page name. An HTTP 422 reply means
that the authors' code raised on this page: the page fails (EngineError). Any other HTTP error or a lost connection
is endpoint state: the engine stops without a record (EngineUnavailable). There are no retries (protocol §6).
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

from harness.engines.base import Engine, EngineError, EngineOutput, EngineUnavailable


class PipelineHttpEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        for key in ("base_url", "pipeline", "model"):
            if not config.get(key):
                raise EngineUnavailable(f"pipeline engine {name!r}: missing config key {key!r}")

    def transcribe(self, image: Path) -> EngineOutput:
        payload = {"pipeline": self.config["pipeline"], "suffix": image.suffix.lower(),
                   "image_b64": base64.b64encode(image.read_bytes()).decode("ascii")}
        start = time.monotonic()
        reply = self._post("/transcribe", payload)
        duration = time.monotonic() - start
        self._check_pipeline(reply)
        text = reply.get("text")
        if not isinstance(text, str):
            raise EngineError(f"unexpected reply shape (no text): {str(reply)[:300]}")
        meta = reply.get("meta") if isinstance(reply.get("meta"), dict) else {}
        return EngineOutput(text=text.strip(), model_id=self.config["model"], duration_s=duration, meta=meta)

    def _check_pipeline(self, reply: dict) -> None:
        if reply.get("pipeline") != self.config["pipeline"]:
            raise EngineUnavailable(
                f"pipeline engine {self.name!r}: server runs pipeline {reply.get('pipeline')!r}, "
                f"expected {self.config['pipeline']!r}")

    def _post(self, path: str, payload: dict) -> dict:
        url = self.config["base_url"].rstrip("/") + path
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.config.get("timeout", 1800)) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            if exc.code == 409:  # the server runs another pipeline
                raise EngineUnavailable(f"pipeline engine {self.name!r}: HTTP 409 from {url}: {detail}") from exc
            if exc.code == 422:  # the authors' code raised on this page
                raise EngineError(f"HTTP 422 from {url}: {detail}") from exc
            raise EngineUnavailable(f"HTTP {exc.code} from {url}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EngineUnavailable(f"cannot reach {url}: {exc}") from exc

    def check(self) -> None:
        url = self.config["base_url"].rstrip("/") + "/info"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                info = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - any failure means unreachable
            raise EngineUnavailable(f"pipeline endpoint not reachable: {url} ({exc})") from exc
        self._check_pipeline(info)

    def describe(self) -> dict:
        return {"type": "pipeline_http", "pipeline": self.config["pipeline"], "model": self.config["model"],
                "base_url": self.config["base_url"], "config": dict(self.config)}
