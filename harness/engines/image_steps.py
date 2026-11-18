"""Engine image steps for engines that opt in (protocol §10, 2026-11-13; key `preprocess`).

Protocol §1 gives every engine exactly the frozen page image. An engine entry may name one fixed image step that is
part of that engine, as a serving stack's internal processing would be; the released system that claims the score
applies the same step. The harness applies it to the frozen image in memory before the request; the frozen file is
never changed or copied, and the record keeps the frozen image hash, the step, and every painted box.

`furniture_fp_v16`: `harness/furniture.py`, a byte copy of the model track's `scripts/furniture_preprocess.py`
(version fp-v16, record EXP-20261112-release-engine-dev). A page with no painted box is sent as the original file; a
painted page is sent as JPEG quality 95 at the original size. Pillow and numpy are imported only on this path.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from harness.engines.base import EngineUnavailable

STEPS = {
    "furniture_fp_v16": {
        "module": "furniture.py",
        "version": "fp-v16",
        "sha256": "2f81aca8a42eb001f5fa35a8661a613af7cc2063a4a1c5fd4c05bcbcf5b3fc60",
    },
    # §10 2026-11-15: CHURRO's default OCR image preprocessor (stanford-oval/churro at 23c3ac6,
    # src/churro_ocr/_internal/image.py prepare_ocr_image): RGB, longest side at most 2,500 px (LANCZOS, no
    # upscaling); sent as PNG, as its image encoder does for an image without a source format.
    "fit_2500_png": {"module": None, "version": "churro-23c3ac6"},
}
FIT_MAX = 2500


def check_step(engine: str, step: str) -> None:
    """Raise EngineUnavailable unless the step is known, its module is the pinned copy, and its imports work."""
    if step not in STEPS:
        raise EngineUnavailable(f"engine {engine!r}: unknown preprocess step {step!r} (known: {sorted(STEPS)})")
    spec = STEPS[step]
    if spec["module"] is None:
        try:
            import PIL  # noqa: F401
        except ImportError as exc:
            raise EngineUnavailable(f"engine {engine!r}: preprocess {step} needs Pillow ({exc})") from exc
        return
    path = Path(__file__).resolve().parent.parent / spec["module"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
        raise EngineUnavailable(f"engine {engine!r}: {spec['module']} differs from the pinned {step} copy")
    try:
        from harness import furniture
    except ImportError as exc:  # numpy or Pillow missing
        raise EngineUnavailable(f"engine {engine!r}: preprocess {step} needs numpy and Pillow ({exc})") from exc
    if furniture.VERSION != spec["version"]:
        raise EngineUnavailable(f"engine {engine!r}: {spec['module']} is {furniture.VERSION}, not {spec['version']}")


def prepared(image: Path, step: str | None) -> tuple[bytes, str, dict | None]:
    """Return (bytes to send, image subtype for the data URL, step record or None)."""
    suffix = image.suffix.lower().lstrip(".") or "jpeg"
    mime = "jpeg" if suffix in ("jpg", "jpeg") else suffix
    raw = image.read_bytes()
    if step is None:
        return raw, mime, None
    from PIL import Image

    if step == "fit_2500_png":
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            width, height = source.size
            image = source
            if width > FIT_MAX or height > FIT_MAX:
                scale = min(FIT_MAX / width, FIT_MAX / height)
                image = source.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="PNG")
        data = buffer.getvalue()
        return data, "png", {"step": step, "version": STEPS[step]["version"], "size": [width, height],
                             "resized": width > FIT_MAX or height > FIT_MAX,
                             "sent_sha256": hashlib.sha256(data).hexdigest()}

    from harness import furniture

    with Image.open(io.BytesIO(raw)) as source:
        painted, rec = furniture.preprocess(source)
    if rec["boxes"]:
        buffer = io.BytesIO()
        painted.save(buffer, format="JPEG", quality=95)
        data, mime = buffer.getvalue(), "jpeg"
    else:
        data = raw
    record = {"step": step, "version": rec["version"], "boxes": rec["boxes"], "notes": rec["notes"],
              "painted_share": rec["painted_share"], "sent_sha256": hashlib.sha256(data).hexdigest()}
    return data, mime, record
