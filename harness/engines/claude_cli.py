"""Frontier VLM through the Claude Code CLI on the owner's Claude subscription (§6 optional
frontier VLM, unrestricted pages only; §10 amendment 2026-10-31).

One `claude -p` session per page, in an empty working directory. The page image goes as-is
(base64, original bytes) in one stream-json user message, followed by the pre-registered §6
prompt. All built-in tools, MCP servers, settings files, skills, CLAUDE.md files, and
auto-memory are disabled, so the transcription is the model's own reading of the image. The
system prompt is one line that says no tools are available: under the default coding-agent
prompt, and also under an empty one, the model on hard pages tried to find the page file or a
library catalogue and wrote those tool calls as text. The CLI still adds a one-line SDK
identity, an environment block, and the account e-mail; none of them carries page content.

The stream is checked: assistant content other than text and thinking, more than one turn, or
a tool call written as text makes the page an engine error (recorded, scored as empty). One
exception: when a reply reaches the output token limit, the CLI resumes it with a synthetic
user message. That page is a length stop, as for an OpenAI-compatible engine: the text of the
first reply is recorded with finish_reason "length", and the resumed turns are not used.

Config keys: model (e.g. claude-fable-5-1), effort (e.g. max), prompt_file,
timeout (default 3600 s), concurrency (default 1; pages run in parallel within this engine),
claude_bin (default "claude").

A failed session (non-zero exit or an error result, for example a usage limit) raises
EngineUnavailable: nothing is recorded, and a resume gives the page its first attempt. That is
not a per-page retry under §6.
"""

from __future__ import annotations

import base64
import json
import os
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

MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
ALLOWED_CONTENT = {"text", "thinking", "redacted_thinking"}
SYSTEM_PROMPT = "No tools are available. Reply with text only."
TEXT_TOOL_CALL = "<invoke name="
LENGTH_NOTICE = "Output token limit hit."
# CLAUDE.md files and auto-memory are not settings: `--setting-sources ""` does not drop them
ISOLATION_ENV = {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}


def length_notice(event: dict) -> bool:
    """True for the synthetic user message the CLI sends to resume a reply cut at the limit."""
    content = event["message"]["content"]
    text = content if isinstance(content, str) else "".join(
        block.get("text", "") for block in content if isinstance(block, dict))
    return bool(event.get("isSynthetic")) and text.startswith(LENGTH_NOTICE)


class ClaudeCliEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        for key in ("model", "effort", "prompt_file"):
            if not config.get(key):
                raise EngineUnavailable(f"engine {name!r}: config key {key!r} is required")
        self.prompt = Path(config["prompt_file"]).read_text(encoding="utf-8")
        self.claude = config.get("claude_bin", "claude")
        self.timeout = float(config.get("timeout", 3600))
        self.concurrency = int(config.get("concurrency", 1))

    def command(self) -> list[str]:
        return [
            self.claude, "-p", "--model", self.config["model"], "--effort", self.config["effort"],
            "--system-prompt", SYSTEM_PROMPT, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
            "--disable-slash-commands", "--no-session-persistence", "--input-format", "stream-json",
            "--output-format", "stream-json", "--verbose",
        ]

    def message(self, image: Path) -> str:
        media_type = MEDIA_TYPES.get(image.suffix.lower())
        if media_type is None:
            raise EngineError(f"unsupported image type: {image.suffix}")
        data = base64.b64encode(image.read_bytes()).decode("ascii")
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}},
            {"type": "text", "text": self.prompt},
        ]
        return json.dumps({"type": "user", "message": {"role": "user", "content": content}}) + "\n"

    def transcribe(self, image: Path) -> EngineOutput:
        stdin = self.message(image)
        with tempfile.TemporaryDirectory(prefix="claude-page-") as tmp:
            start = time.monotonic()
            # a timeout raises EngineError: recorded, as for every other engine
            result = run_command(self.command(), timeout=self.timeout, input=stdin,
                                 env={**os.environ, **ISOLATION_ENV}, cwd=Path(tmp))
            duration = time.monotonic() - start
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        final = next((e for e in reversed(events) if e.get("type") == "result"), None)
        if result.returncode != 0 or final is None or final.get("is_error"):
            detail = json.dumps(final)[:300] if final else result.stderr[-300:]
            raise EngineUnavailable(f"claude exit {result.returncode}: {detail}")
        messages = [e["message"] for e in events if e.get("type") == "assistant"]
        content = Counter(block.get("type") for message in messages for block in message["content"])
        models = sorted({message.get("model") for message in messages})
        transformations = [t for message in messages for t in message.get("input_transformations") or []]
        user_events = [e for e in events if e.get("type") == "user"]
        length = bool(user_events) and all(length_notice(e) for e in user_events)
        if length:
            first = messages[0].get("id")
            text = "".join(block.get("text", "") for message in messages if message.get("id") == first
                           for block in message["content"] if block.get("type") == "text")
        else:
            text = final.get("result") or ""
        meta = {
            "content": dict(sorted(content.items(), key=str)),
            "num_turns": final.get("num_turns"),
            "stop_reason": final.get("stop_reason"),
            "finish_reason": "length" if length else "stop",
            "input_transformations": transformations,
            "usage": final.get("usage"),
            "model_usage": final.get("modelUsage"),
        }
        if set(content) - ALLOWED_CONTENT or (final.get("num_turns") != 1 and not length):
            raise EngineError(f"tool use in session: {sorted(set(content) - ALLOWED_CONTENT)}, "
                              f"turns {final.get('num_turns')}, final message {text[:200]!r}")
        if TEXT_TOOL_CALL in text:
            raise EngineError(f"tool call written as text: {text[:200]!r}")
        if not text.strip():
            raise EngineError("empty final message")
        return EngineOutput(text=text, model_id=",".join(models), duration_s=duration, meta=meta)

    def describe(self) -> dict:
        return {
            "type": type(self).__name__,
            "claude_version": command_version([self.claude, "--version"]),
            "system_prompt": SYSTEM_PROMPT,
            "isolation_env": ISOLATION_ENV,
            "config": self.config,
        }

    def check(self) -> None:
        version = command_version([self.claude, "--version"])
        if version == "unknown":
            raise EngineUnavailable("claude CLI not found")
