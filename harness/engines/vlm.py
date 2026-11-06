"""VLM engines over an OpenAI-compatible chat-completions endpoint.

Covers every VLM in the protocol §6 table with one runner: Qwen3-VL served
locally (llama.cpp / lmstudio / vLLM on the Strix Halo), CHURRO via `vllm
serve stanford-oval/churro-3B`, and frontier APIs that speak the same schema
(unrestricted pages only, per protocol).

Config keys: base_url (e.g. "http://localhost:8080/v1"), model, prompt_file
(pre-registered §6 prompt, path relative to repo root), api_key_env (optional
env var name), max_tokens (default 4096), temperature (default 0.0),
repetition_penalty (optional; sent only when set — vLLM sampling parameter,
§10 amendment 2026-09-24), chat_template_kwargs (optional mapping sent as-is, e.g.
{enable_thinking: false} for Qwen3.5's non-thinking mode), image_only (optional;
true sends the page without the prompt text, for engines trained without one;
prompt_file stays required and its hash is still recorded), vllm_xargs (optional
mapping sent as-is, e.g. the windowed repetition penalty of
model-track scripts/windowed_repetition_penalty.py; §10 entry 2026-11-06), timeout
(default 600), retries (default 0 — protocol §6 forbids per-page retries in
scored runs; any override is recorded in run.json via describe()).

The page image is sent as-is (base64), no resizing — protocol §1 forbids
per-engine preprocessing; anything the serving stack does internally is part
of that engine's end-to-end behavior.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from harness.engines.base import Engine, EngineError, EngineOutput, EngineUnavailable


class VlmOpenAiEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        for key in ("base_url", "model", "prompt_file"):
            if not config.get(key):
                raise EngineUnavailable(f"vlm engine {name!r}: missing config key {key!r}")
        prompt_path = Path(config["prompt_file"])
        if not prompt_path.exists():
            raise EngineUnavailable(f"vlm engine {name!r}: prompt file not found: {prompt_path}")
        self.prompt = prompt_path.read_text(encoding="utf-8").strip()
        self.prompt_sha256 = hashlib.sha256(self.prompt.encode("utf-8")).hexdigest()

    def transcribe(self, image: Path) -> EngineOutput:
        payload = {
            "model": self.config["model"],
            "temperature": self.config.get("temperature", 0.0),
            "max_tokens": self.config.get("max_tokens", 4096),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        # Qwen2.5-VL on vLLM treats image-first content as the
                        # reliable OpenAI-compatible multimodal shape.
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url(image)},
                        },
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
        }
        if self.config.get("image_only"):
            payload["messages"][0]["content"].pop()
        if self.config.get("repetition_penalty") is not None:
            payload["repetition_penalty"] = self.config["repetition_penalty"]
        if self.config.get("chat_template_kwargs"):
            payload["chat_template_kwargs"] = dict(self.config["chat_template_kwargs"])
        if self.config.get("vllm_xargs"):
            payload["vllm_xargs"] = dict(self.config["vllm_xargs"])
        start = time.monotonic()
        response = self._post(payload)
        duration = time.monotonic() - start
        try:
            message = response["choices"][0]["message"]
            text = message.get("content") or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise EngineError(f"unexpected response shape: {str(response)[:300]}") from exc
        return EngineOutput(
            text=text.strip(),
            model_id=response.get("model", self.config["model"]),
            duration_s=duration,
            meta={"prompt_sha256": self.prompt_sha256, "usage": response.get("usage")},
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key_env = self.config.get("api_key_env")
        if key_env:
            key = os.environ.get(key_env)
            if not key:
                raise EngineUnavailable(f"vlm engine {self.name!r}: env var {key_env} not set")
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _post(self, payload: dict) -> dict:
        url = self.config["base_url"].rstrip("/") + "/chat/completions"
        headers = self._headers()
        body = json.dumps(payload).encode("utf-8")
        retries = self.config.get("retries", 0)
        timeout = self.config.get("timeout", 600)
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            request = urllib.request.Request(url, data=body, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
                if exc.code < 500 and exc.code not in (401, 403, 404, 429):
                    # Page-specific 4xx (bad request, payload too large…) is
                    # deterministic for this page/config -> terminal EngineError.
                    raise EngineError(f"HTTP {exc.code} from {url}: {detail}") from exc
                # Auth/model/quota (401/403/404/429) and 5xx are endpoint state,
                # not properties of the page: EngineUnavailable aborts the
                # engine without writing a record.
                last_error = EngineUnavailable(f"HTTP {exc.code} from {url}: {detail}")
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = EngineUnavailable(f"cannot reach {url}: {exc}")
            if attempt < retries:
                time.sleep(min(2**attempt * 2, 30))
        raise last_error  # type: ignore[misc]

    def check(self) -> None:
        """Cheap reachability probe: GET {base_url}/models with the same auth as runs."""
        url = self.config["base_url"].rstrip("/") + "/models"
        headers = {k: v for k, v in self._headers().items() if k != "Content-Type"}
        try:
            urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10).read()
        except Exception as exc:  # noqa: BLE001 - any failure means unreachable
            raise EngineUnavailable(f"vlm endpoint not reachable: {url} ({exc})") from exc

    def describe(self) -> dict:
        return {
            "type": "vlm_openai",
            "model": self.config["model"],
            "base_url": self.config["base_url"],
            "prompt_sha256": self.prompt_sha256,
            "config": {k: v for k, v in self.config.items() if k != "api_key_env"},
        }


def _data_url(image: Path) -> str:
    suffix = image.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{encoded}"
