#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8080/v1}"
model="${2:-qwen2.5-vl-3b-awq}"

python3 - "$base_url" "$model" <<'PY'
from __future__ import annotations

import base64
import json
import struct
import sys
import urllib.request
import zlib

base_url = sys.argv[1].rstrip("/")
model = sys.argv[2]


def request(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(f"{base_url}{path}", data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def chunk(tag: bytes, data: bytes) -> bytes:
    body = tag + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def red_png_data_url(width: int = 64, height: int = 64) -> str:
    row = b"\x00" + (b"\xff\x00\x00" * width)
    raw = row * height
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


models = request("/models")
print("models:", json.dumps(models, ensure_ascii=False)[:500])

text_payload = {
    "model": model,
    "temperature": 0,
    "max_tokens": 32,
    "messages": [{"role": "user", "content": "Reply with exactly: evo-vlm-ok"}],
}
text_response = request("/chat/completions", text_payload)
print("text:", text_response["choices"][0]["message"]["content"].strip())

image_payload = {
    "model": model,
    "temperature": 0,
    "max_tokens": 32,
    "messages": [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": red_png_data_url()}},
                {"type": "text", "text": "What is the dominant color of this image?"},
            ],
        }
    ],
}
image_response = request("/chat/completions", image_payload)
print("image:", image_response["choices"][0]["message"]["content"].strip())
PY
