"""Calamari print baseline behind kraken baseline segmentation (VISION §6).

Calamari is a line recognizer; end-to-end page behavior therefore includes a
segmentation stage, which counts against this engine (protocol §1). Pipeline:
kraken binarize -> kraken segment -bl -> crop line bounding boxes (Pillow)
-> calamari-predict.

Config keys: checkpoint (required, .ckpt path/prefix), kraken_binary (default
"kraken"), predict_binary (default "calamari-predict"), predict_args (list).
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from harness.engines.base import (
    Engine, EngineError, EngineOutput, EngineUnavailable, command_version,
    file_fingerprints, run_command,
)


class CalamariEngine(Engine):
    def transcribe(self, image: Path) -> EngineOutput:
        checkpoint = self._checkpoint()
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="calamari_") as tmp:
            crops = self._segment_and_crop(image, Path(tmp))
            if not crops:
                raise EngineError(f"kraken found no lines on {image.name}")
            command = [
                self.config.get("predict_binary", "calamari-predict"),
                "--checkpoint",
                checkpoint,
                "--data.images",
                *[str(c) for c in crops],
                *self.config.get("predict_args", []),
            ]
            result = run_command(command, timeout=self.config.get("timeout", 600.0))
            if result.returncode != 0:
                raise EngineError(f"calamari failed on {image.name}: {result.stderr.strip()[-500:]}")
            lines = []
            missing = []
            for crop in crops:
                pred = crop.with_suffix(".pred.txt")
                if not pred.exists():
                    missing.append(pred.name)
                    continue
                lines.append(pred.read_text(encoding="utf-8").strip())
            if missing:
                shown = ", ".join(missing[:5])
                suffix = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
                raise EngineError(f"calamari missing prediction files: {shown}{suffix}")
        return EngineOutput(
            text="\n".join(lines),
            model_id=f"calamari:{Path(checkpoint).name}",
            duration_s=time.monotonic() - start,
            meta={"lines": len(crops)},
        )

    def _segment_and_crop(self, image: Path, tmp: Path) -> list[Path]:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise EngineUnavailable("calamari engine needs Pillow: uv sync --extra synth") from exc
        binary = self.config.get("kraken_binary", "kraken")
        bin_path = tmp / "binarized.png"
        seg_path = tmp / "segmentation.json"
        timeout = self.config.get("timeout", 600.0)
        bin_result = run_command(
            [binary, "-i", str(image), str(bin_path), "binarize"], timeout=timeout
        )
        if bin_result.returncode != 0 or not bin_path.exists():
            raise EngineError(f"kraken binarization failed: {bin_result.stderr.strip()[-500:]}")
        result = run_command(
            [binary, "-i", str(bin_path), str(seg_path), "segment", "-bl"], timeout=timeout
        )
        if result.returncode != 0 or not seg_path.exists():
            raise EngineError(f"kraken segmentation failed: {result.stderr.strip()[-500:]}")
        segmentation = json.loads(seg_path.read_text(encoding="utf-8"))
        crops: list[Path] = []
        with Image.open(bin_path) as page:
            for index, line in enumerate(segmentation.get("lines", [])):
                if line.get("boundary"):  # polygon: [[x, y], ...]
                    xs = [p[0] for p in line["boundary"]]
                    ys = [p[1] for p in line["boundary"]]
                    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
                elif line.get("bbox"):  # rectangle: [x0, y0, x1, y1]
                    x0, y0, x1, y1 = line["bbox"]
                else:
                    continue
                box = (max(x0, 0), max(y0, 0), min(x1, page.width), min(y1, page.height))
                if box[2] <= box[0] or box[3] <= box[1]:
                    continue
                crop_path = tmp / f"line_{index:04d}.png"
                page.crop(box).save(crop_path)
                # Calamari's image loader expects a same-base .gt.txt sidecar
                # even during prediction unless explicitly configured otherwise.
                crop_path.with_suffix(".gt.txt").write_text("", encoding="utf-8")
                crops.append(crop_path)
        return crops

    def check(self) -> None:
        self._checkpoint()
        self.describe()

    def _checkpoint(self) -> str:
        checkpoint = self.config.get("checkpoint")
        if not checkpoint:
            raise EngineUnavailable(
                "calamari checkpoint not set — get an OCR-D/Calamari Fraktur model and set "
                "`checkpoint:` in configs/engines.yml"
            )
        # Calamari checkpoints are a file or a prefix (foo -> foo.ckpt.json…);
        # a dangling path must fail preflight, not score as page failures.
        path = Path(checkpoint)
        if not path.exists() and not list(path.parent.glob(f"{path.name}*")):
            raise EngineUnavailable(f"calamari checkpoint not found on disk: {checkpoint}")
        return checkpoint

    def describe(self) -> dict:
        checkpoint = self._checkpoint()
        return {
            "type": "calamari",
            "version": command_version([self.config.get("predict_binary", "calamari-predict"), "--version"]),
            "kraken_version": command_version([self.config.get("kraken_binary", "kraken"), "--version"]),
            "checkpoint_files": file_fingerprints(checkpoint),
            "config": self.config,
        }
