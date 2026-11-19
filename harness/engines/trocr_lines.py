"""TrOCR line models behind kraken baseline segmentation (§10, 2026-11-19).

A line recognizer needs a segmentation stage, which counts against the engine (protocol §1). The row names both
parts: "<model> + kraken <version> blla". Pipeline, as the dh-unibe model cards and the DH Bern serving gateway
describe it:

1. `kraken -i <page> <json> segment -bl` on the original page (no binarization).
2. One crop per line: the bounding box of the line polygon, cut from the original page in RGB, in kraken's order.
3. `scripts/trocr_predict.py` reads all crops with the model card's generation settings, in a separate Python
   environment that has torch and transformers.
4. The lines are joined top to bottom with a line break. A line without a reading fails the page.

Config keys: model (Hugging Face ID), revision (pinned commit), python (interpreter of the recognizer environment),
generate (mapping passed to `generate()`, from the model card), kraken_binary (default "kraken"), timeout
(default 1800 seconds).
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from harness.engines.base import (
    Engine, EngineError, EngineOutput, EngineUnavailable, command_version, run_command,
)

_PREDICT_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "trocr_predict.py"


class TrocrLinesEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        for key in ("model", "revision", "python", "generate"):
            if not config.get(key):
                raise EngineUnavailable(f"trocr_lines engine {name!r}: missing config key {key!r}")
        if not isinstance(config["generate"], dict):
            raise EngineUnavailable(f"trocr_lines engine {name!r}: generate must be a mapping")
        if not Path(config["python"]).exists():
            raise EngineUnavailable(f"trocr_lines engine {name!r}: python not found: {config['python']}")

    def transcribe(self, image: Path) -> EngineOutput:
        start = time.monotonic()
        timeout = self.config.get("timeout", 1800.0)
        with tempfile.TemporaryDirectory(prefix="trocr_") as tmp:
            crops = self._segment_and_crop(image, Path(tmp), timeout)
            if not crops:
                raise EngineError(f"kraken found no lines on {image.name}")
            command = [
                self.config["python"], str(_PREDICT_SCRIPT),
                "--model", self.config["model"],
                "--revision", self.config["revision"],
                "--generate", json.dumps(self.config["generate"], sort_keys=True),
                *[str(c) for c in crops],
            ]
            result = run_command(command, timeout=timeout)
            if result.returncode != 0:
                raise EngineError(f"recognizer failed on {image.name}: {result.stderr.strip()[-500:]}")
            try:
                texts = json.loads(result.stdout)["texts"]
            except (ValueError, KeyError, TypeError) as exc:
                raise EngineError(f"recognizer output is not JSON with 'texts': {result.stdout[-300:]}") from exc
            if not isinstance(texts, list) or len(texts) != len(crops):
                count = len(texts) if isinstance(texts, list) else "no"
                raise EngineError(f"{len(crops)} lines, {count} readings on {image.name}")
        return EngineOutput(
            text="\n".join(t.strip() for t in texts),
            model_id=f"{self.config['model']}@{self.config['revision']}+kraken-blla",
            duration_s=time.monotonic() - start,
            meta={"lines": len(crops)},
        )

    def _segment_and_crop(self, image: Path, tmp: Path, timeout: float) -> list[Path]:
        from PIL import Image

        seg_path = tmp / "segmentation.json"
        binary = self.config.get("kraken_binary", "kraken")
        result = run_command([binary, "-i", str(image), str(seg_path), "segment", "-bl"], timeout=timeout)
        if result.returncode != 0 or not seg_path.exists():
            raise EngineError(f"kraken segmentation failed: {result.stderr.strip()[-500:]}")
        segmentation = json.loads(seg_path.read_text(encoding="utf-8"))
        crops: list[Path] = []
        with Image.open(image) as source:
            page = source.convert("RGB")
            for index, line in enumerate(segmentation.get("lines", [])):
                polygon = line.get("boundary")
                if not polygon:
                    raise EngineError(f"kraken line {index} on {image.name} has no polygon")
                xs = [p[0] for p in polygon]
                ys = [p[1] for p in polygon]
                box = (max(min(xs), 0), max(min(ys), 0), min(max(xs), page.width), min(max(ys), page.height))
                if box[2] <= box[0] or box[3] <= box[1]:
                    raise EngineError(f"kraken line {index} on {image.name} has an empty box")
                crop_path = tmp / f"line_{index:04d}.png"
                page.crop(box).save(crop_path)
                crops.append(crop_path)
        return crops

    def check(self) -> None:
        self.describe()

    def describe(self) -> dict:
        return {
            "type": "trocr_lines",
            "kraken_version": command_version([self.config.get("kraken_binary", "kraken"), "--version"]),
            "recognizer": {"model": self.config["model"], "revision": self.config["revision"]},
            "config": self.config,
        }
