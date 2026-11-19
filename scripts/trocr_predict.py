"""Read line crops with a TrOCR model; used by `harness/engines/trocr_lines.py`.

Runs in a separate environment with torch and transformers. Prints {"texts": [...]} on stdout, one reading per
crop, in input order.

    python scripts/trocr_predict.py --model dh-unibe/trocr-kurrent --revision <commit> \
        --generate '{"num_beams": 4, "max_length": 128}' line_0000.png line_0001.png
"""

from __future__ import annotations

import argparse
import json
import sys

BATCH = 8


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--generate", required=True, help="JSON mapping passed to generate()")
    parser.add_argument("crops", nargs="+")
    args = parser.parse_args()

    import torch
    from PIL import Image
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    processor = TrOCRProcessor.from_pretrained(args.model, revision=args.revision)
    model = VisionEncoderDecoderModel.from_pretrained(args.model, revision=args.revision).to(device).eval()
    settings = json.loads(args.generate)
    texts: list[str] = []
    for start in range(0, len(args.crops), BATCH):
        images = [Image.open(path).convert("RGB") for path in args.crops[start:start + BATCH]]
        pixel_values = processor(images=images, return_tensors="pt").pixel_values.to(device)
        with torch.inference_mode():
            ids = model.generate(pixel_values, **settings)
        texts.extend(processor.batch_decode(ids, skip_special_tokens=True))
    json.dump({"texts": texts, "device": device}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
