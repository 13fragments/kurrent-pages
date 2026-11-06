"""Frontier VLM through the Codex CLI on the owner's ChatGPT subscription (§6 optional
frontier VLM, unrestricted pages only; §10 amendment 2026-10-31).

One `codex exec` session per page, in an empty working directory, with the page image
attached as-is and the pre-registered §6 prompt on stdin. Shell, web search, apps, browser,
computer use, and image generation are disabled, so the transcription is the model's own
reading of the image. The JSON event stream is checked: any item other than the agent's
message and its reasoning makes the page an engine error (recorded, scored as empty).

Config keys: model (e.g. gpt-6-astra), reasoning_effort (e.g. max), prompt_file,
timeout (default 3600 s), concurrency (default 1; pages run in parallel within this engine),
codex_bin (default "codex").

A failed session (non-zero exit, `turn.failed`, or an error event, for example a usage
limit) raises EngineUnavailable: nothing is recorded, and a resume gives the page its first
attempt. That is not a per-page retry under §6.
"""

from __future__ import annotations

import json
import tempfile
import time
from collections import Counter
from pathlib import Path

from harness.engines.base import (
    Engine,
    EngineError,
    EngineOutput,
    EngineUnavailable,
    command_version,
    run_command,
)

DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "apps", "browser_use", "computer_use", "image_generation",
)
ALLOWED_ITEMS = {"agent_message", "reasoning"}


class CodexCliEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        for key in ("model", "reasoning_effort", "prompt_file"):
            if not config.get(key):
                raise EngineUnavailable(f"engine {name!r}: config key {key!r} is required")
        self.prompt = Path(config["prompt_file"]).read_text(encoding="utf-8")
        self.codex = config.get("codex_bin", "codex")
        self.timeout = float(config.get("timeout", 3600))
        self.concurrency = int(config.get("concurrency", 1))

    def command(self, workdir: Path, image: Path, out_path: Path) -> list[str]:
        command = [
            self.codex, "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
            "--ignore-rules", "-s", "read-only", "-C", str(workdir),
            "-m", self.config["model"], "-c", f"model_reasoning_effort={self.config['reasoning_effort']}",
            "-c", "web_search=disabled",
        ]
        for feature in DISABLED_FEATURES:
            command += ["--disable", feature]
        # `-i` takes several files; `--` ends it so the prompt stays the positional argument
        return command + ["--json", "-o", str(out_path), "-i", str(image), "--", self.prompt]

    def transcribe(self, image: Path) -> EngineOutput:
        with tempfile.TemporaryDirectory(prefix="codex-page-") as tmp:
            workdir = Path(tmp)
            out_path = workdir / "last_message.txt"
            start = time.monotonic()
            # a timeout raises EngineError: recorded, as for every other engine
            result = run_command(self.command(workdir, image.resolve(), out_path), timeout=self.timeout)
            duration = time.monotonic() - start
            events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
            kinds = Counter(
                (event.get("type"), (event.get("item") or {}).get("type")) for event in events
            )
            failed = [e for e in events if e.get("type") in {"turn.failed", "error"}]
            if result.returncode != 0 or failed:
                detail = json.dumps(failed[-1])[:300] if failed else result.stderr[-300:]
                raise EngineUnavailable(f"codex exit {result.returncode}: {detail}")
            items = {item for (kind, item) in kinds if kind == "item.completed" and item}
            text = out_path.read_text(encoding="utf-8") if out_path.exists() else ""
            usage = next((e.get("usage") for e in events if e.get("type") == "turn.completed"), None)
        meta = {
            "events": {f"{kind}:{item}": count for (kind, item), count in sorted(kinds.items(), key=str)},
            "usage": usage,
        }
        if items - ALLOWED_ITEMS:
            raise EngineError(f"tool use in session: {sorted(items - ALLOWED_ITEMS)}")
        if not text.strip():
            raise EngineError("empty final message")
        return EngineOutput(text=text, model_id=self.config["model"], duration_s=duration, meta=meta)

    def describe(self) -> dict:
        return {
            "type": type(self).__name__,
            "codex_version": command_version([self.codex, "--version"]),
            "disabled_features": list(DISABLED_FEATURES),
            "config": self.config,
        }

    def check(self) -> None:
        version = command_version([self.codex, "--version"])
        if version == "unknown":
            raise EngineUnavailable("codex CLI not found")
