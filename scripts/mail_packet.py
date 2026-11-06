#!/usr/bin/env python3
"""Build a mail-sized copy of a reviewer packet.

Gmail rejects messages over 25 MB, and the frozen packets carry full-resolution
scans (four 5 MB pages in the 12-unit pilot). This copies a packet folder,
downscales only images above --max-bytes to --max-width (JPEG quality 92), zips
the copy under the packet's own folder name (so the reviewer unzips one folder),
and writes MAILCOPY.json next to the zip: per image the original and shipped
sha256 and dimensions. The packet in the pilot directory is untouched; export
bindings come from packet.json and are unaffected. Coordinator-only file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True, help="packet folder (contains review.html)")
    parser.add_argument("--out", type=Path, required=True, help="output .zip")
    parser.add_argument("--max-bytes", type=int, default=2_500_000)
    parser.add_argument("--max-width", type=int, default=4000)
    parser.add_argument("--quality", type=int, default=92)
    parser.add_argument("--single-file", action="store_true", help="zip one self-contained review.html with the scans embedded as data URIs (works even when opened from inside the zip)")
    args = parser.parse_args()
    packet = args.packet.resolve()
    if not (packet / "review.html").is_file() or not (packet / "packet.json").is_file():
        parser.error("not a packet folder")
    record = {"packet": packet.name, "max_bytes": args.max_bytes, "max_width": args.max_width, "quality": args.quality, "images": {}}
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / packet.name
        shutil.copytree(packet, copy, ignore=shutil.ignore_patterns(".DS_Store"))
        for image in sorted((copy / "images").glob("*")):
            original = packet / "images" / image.name
            entry = {"original_sha256": sha256(original), "original_bytes": original.stat().st_size}
            if original.stat().st_size > args.max_bytes:
                with Image.open(original) as im:
                    entry["original_size"] = list(im.size)
                    scale = min(1.0, args.max_width / im.width)
                    resized = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS) if scale < 1 else im.copy()
                    resized.save(image, "JPEG", quality=args.quality, optimize=True)
                    entry["shipped_size"] = list(resized.size)
            entry["shipped_sha256"] = sha256(image)
            entry["shipped_bytes"] = image.stat().st_size
            record["images"][image.name] = entry
        args.out.parent.mkdir(parents=True, exist_ok=True)
        if args.single_file:
            import base64
            from harness.pilot_html import render_review_html
            packet_json = json.loads((copy / "packet.json").read_text(encoding="utf-8"))
            for unit in packet_json["units"]:
                data = (copy / unit["image_file"]).read_bytes()
                unit["image_file"] = "data:image/jpeg;base64," + base64.b64encode(data).decode()
            single = copy / "review.html"
            single.write_text(render_review_html(packet_json), encoding="utf-8")
            record["single_file"] = True
            record["html_bytes"] = single.stat().st_size
            with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(single, "review.html")
        else:
            with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in sorted(copy.rglob("*")):
                    if path.is_file():
                        zf.write(path, path.relative_to(copy.parent))
    record["zip_bytes"] = args.out.stat().st_size
    args.out.with_suffix(".MAILCOPY.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    changed = sum(1 for e in record["images"].values() if e["original_sha256"] != e["shipped_sha256"])
    print(f"{args.out} {record['zip_bytes']/1e6:.1f} MB; {changed} of {len(record['images'])} images downscaled; record {args.out.with_suffix('.MAILCOPY.json').name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
