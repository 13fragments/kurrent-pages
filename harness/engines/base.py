"""Engine interface: raw page image in, transcription out (protocol §1 task).

Engines receive exactly the frozen page image — no per-engine preprocessing is
permitted (§1). Anything an engine needs (binarization, segmentation) happens
inside the engine and counts as part of that engine's end-to-end result.
"""

from __future__ import annotations

import hashlib
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class EngineError(RuntimeError):
    """Engine produced no usable result for a page."""


class EngineUnavailable(EngineError):
    """Engine cannot run in this environment (missing binary/model/endpoint)."""


@dataclass
class EngineOutput:
    text: str
    model_id: str
    duration_s: float
    meta: dict = field(default_factory=dict)


class Engine(ABC):
    """One benchmark engine config. `name` is the config key from engines.yml."""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def transcribe(self, image: Path) -> EngineOutput: ...

    def describe(self) -> dict:
        """Version/config info logged into run.json (§6 reproducibility)."""
        return {"type": type(self).__name__, "config": self.config}

    def check(self) -> None:
        """Raise EngineUnavailable if the engine cannot run. Default: try describe()."""
        self.describe()


def run_command(
    command: list[str],
    timeout: float = 600.0,
    input: str | None = None,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command, input=input, env=env, cwd=cwd, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise EngineUnavailable(f"binary not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise EngineError(f"timed out after {timeout}s: {' '.join(command)}") from exc


def command_version(command: list[str]) -> str:
    result = run_command(command, timeout=30)
    return (result.stdout or result.stderr).strip().splitlines()[0] if (
        result.stdout or result.stderr
    ) else "unknown"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_fingerprints(path_or_prefix: str) -> list[dict[str, str]]:
    """SHA-256 fingerprints for an exact file/path or checkpoint prefix."""
    path = Path(path_or_prefix)
    files: set[Path] = set()
    if path.is_file():
        files.add(path)
    if path.is_dir():
        files.update(p for p in path.rglob("*") if p.is_file())
    files.update(p for p in path.parent.glob(f"{path.name}*") if p.is_file())
    if not files:
        raise EngineUnavailable(f"model/checkpoint files not found: {path_or_prefix}")
    return [{"path": str(p), "sha256": sha256_file(p)} for p in sorted(files)]
