"""Engine registry: engines.yml config entries -> Engine instances."""

from __future__ import annotations

from pathlib import Path

import yaml

from harness.engines.base import Engine, EngineError, EngineOutput, EngineUnavailable
from harness.engines.calamari import CalamariEngine
from harness.engines.claude_cli import ClaudeCliEngine
from harness.engines.codex_cli import CodexCliEngine
from harness.engines.kraken import KrakenEngine
from harness.engines.mock import MockEngine
from harness.engines.stubs import PylaiaEngine
from harness.engines.tesseract import TesseractEngine
from harness.engines.transkribus import TranskribusEngine
from harness.engines.vlm import VlmOpenAiEngine

ENGINE_TYPES: dict[str, type[Engine]] = {
    "tesseract": TesseractEngine,
    "kraken": KrakenEngine,
    "calamari": CalamariEngine,
    "vlm_openai": VlmOpenAiEngine,
    "codex_cli": CodexCliEngine,
    "claude_cli": ClaudeCliEngine,
    "pylaia": PylaiaEngine,
    "transkribus": TranskribusEngine,
    "mock": MockEngine,
}

__all__ = [
    "Engine",
    "EngineError",
    "EngineOutput",
    "EngineUnavailable",
    "ENGINE_TYPES",
    "load_engines",
    "create_engine",
]


def create_engine(name: str, config: dict) -> Engine:
    engine_type = config.get("type")
    if engine_type not in ENGINE_TYPES:
        raise EngineUnavailable(
            f"engine {name!r}: unknown type {engine_type!r} (known: {sorted(ENGINE_TYPES)})"
        )
    return ENGINE_TYPES[engine_type](name, config)


def load_engines(config_path: Path, names: list[str] | None = None) -> dict[str, Engine]:
    """Instantiate engines from configs/engines.yml, optionally a subset by name."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    configured = data.get("engines", {})
    selected = names if names is not None else list(configured)
    engines: dict[str, Engine] = {}
    for name in selected:
        if name not in configured:
            raise EngineUnavailable(
                f"engine {name!r} not in {config_path} (configured: {sorted(configured)})"
            )
        engines[name] = create_engine(name, configured[name])
    return engines
