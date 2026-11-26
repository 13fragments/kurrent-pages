"""Serve one authors' page pipeline over HTTP for the harness engine type pipeline_http (§10 2026-11-25, batch 3).

Runs on the serving machine, in the authors' own environment, next to the vLLM server of the model. Standard library
only, plus the authors' package, which is imported when the server starts. Each request carries one page image; the
server writes it to a temporary file, calls the authors' code once with the documented defaults, deletes the file,
and returns the text that the authors' code produced. Requests are served one at a time.

Pipelines (each adapter calls the authors' documented entry point; nothing in the text is changed here):
  chandra_vllm  chandra-ocr: InferenceManager(method="vllm").generate([BatchInputItem(image, "ocr_layout")]), the
                model card's Python example; text = result.markdown. Package defaults: server
                http://localhost:8000/v1, served name "chandra".
  dots_parser   dots.ocr (GitHub, last commit before dots.ocr 1.5): DotsOCRParser with the defaults of its command
                line (temperature 0.1, top_p 1.0, 16,384 tokens, dpi 200, fitz preprocessing), prompt
                prompt_layout_all_en; text = the .md file that parse_file() writes (page headers and footers kept).
  glmocr_sdk    glmocr (GLM-OCR SDK), self-hosted mode: the package's own config.yaml with MaaS off, the vLLM port
                8000, and the layout model at a pinned local path; text = PipelineResult.markdown_result.

Observation only: for the pipelines that use the OpenAI client (chandra_vllm, dots_parser), the server counts the
model requests of each page and records the finish reason and completion tokens of the last one. It does not change
any request or reply.

Usage (on the Pod): python -I pipeline_server.py --pipeline chandra_vllm [--port 8080] [--served chandra]
                    [--layout-dir DIR]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import shutil
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import metadata
from pathlib import Path

SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
VLLM_PORT = 8000

_calls: list[dict] = []
_calls_lock = threading.Lock()


def observe_openai() -> None:
    """Record finish_reason and completion tokens of every chat completion the authors' code requests."""
    from openai.resources.chat import completions

    original = completions.Completions.create

    def create(self, *args, **kwargs):
        reply = original(self, *args, **kwargs)
        try:
            row = {"finish_reason": reply.choices[0].finish_reason,
                   "completion_tokens": getattr(reply.usage, "completion_tokens", None)}
        except Exception:  # noqa: BLE001 - observation must never change the authors' flow
            row = {"finish_reason": None, "completion_tokens": None}
        with _calls_lock:
            _calls.append(row)
        return reply

    completions.Completions.create = create


def _observed_meta() -> dict:
    with _calls_lock:
        rows = list(_calls)
    last = rows[-1] if rows else {}
    return {"requests": len(rows), "finish_reason": last.get("finish_reason"),
            "completion_tokens": last.get("completion_tokens")}


def _reset_observed() -> None:
    with _calls_lock:
        _calls.clear()


def chandra_adapter(served: str):
    from PIL import Image

    from chandra.model import InferenceManager
    from chandra.model.schema import BatchInputItem

    observe_openai()
    manager = InferenceManager(method="vllm")

    def adapter(path: Path) -> dict:
        _reset_observed()
        result = manager.generate([BatchInputItem(image=Image.open(path), prompt_type="ocr_layout")],
                                  vllm_model_name=served)[0]
        if result.error:
            raise RuntimeError("chandra: generation error after the package's own retries")
        return {"text": result.markdown,
                "meta": {**_observed_meta(), "token_count": result.token_count, "raw_chars": len(result.raw)}}

    return adapter


def dots_adapter(served: str):
    from dots_ocr.parser import DotsOCRParser

    observe_openai()
    # dots_ocr/parser.py main(): the command-line defaults
    parser = DotsOCRParser(protocol="http", ip="127.0.0.1", port=VLLM_PORT, model_name=served, temperature=0.1,
                           top_p=1.0, max_completion_tokens=16384, num_thread=16, dpi=200, min_pixels=None,
                           max_pixels=None, use_hf=False)

    def adapter(path: Path) -> dict:
        _reset_observed()
        out = Path(tempfile.mkdtemp(prefix="dots_out_"))
        try:
            results = parser.parse_file(str(path), output_dir=str(out), prompt_mode="prompt_layout_all_en",
                                        bbox=None, fitz_preprocess=True)
            result = results[0]
            text = Path(result["md_content_path"]).read_text(encoding="utf-8")
            return {"text": text, "meta": {**_observed_meta(), "filtered": bool(result.get("filtered"))}}
        finally:
            shutil.rmtree(out, ignore_errors=True)

    return adapter


def glmocr_adapter(served: str, layout_dir: str):
    import yaml

    import glmocr

    config = yaml.safe_load((Path(glmocr.__file__).parent / "config.yaml").read_text(encoding="utf-8"))
    config["pipeline"]["maas"]["enabled"] = False
    config["pipeline"]["ocr_api"]["api_host"] = "127.0.0.1"
    config["pipeline"]["ocr_api"]["api_port"] = VLLM_PORT
    config["pipeline"]["ocr_api"]["model"] = served
    config["pipeline"]["layout"]["model_dir"] = layout_dir
    config_path = Path(tempfile.mkdtemp(prefix="glmocr_cfg_")) / "config.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    parser = glmocr.GlmOcr(config_path=str(config_path))

    def adapter(path: Path) -> dict:
        result = parser.parse(str(path), save_layout_visualization=False)
        return {"text": result.markdown_result or "", "meta": {"config": str(config_path)}}

    return adapter


PACKAGES = {"chandra_vllm": ["chandra-ocr", "openai"], "dots_parser": ["dots_ocr", "openai"],
            "glmocr_sdk": ["glmocr", "transformers", "torch"]}


def versions(pipeline: str) -> dict:
    found = {}
    for name in PACKAGES.get(pipeline, []):
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    return found


def make_handler(pipeline: str, adapter, package_versions: dict):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt, *args):  # one line per request on stderr, no page content
            super().log_message(fmt, *args)

        def do_GET(self):
            if self.path == "/info":
                self._send(200, {"pipeline": pipeline, "versions": package_versions})
            else:
                self._send(404, {"error": "unknown path"})

        def do_POST(self):
            if self.path != "/transcribe":
                self._send(404, {"error": "unknown path"})
                return
            try:
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
                suffix = str(payload.get("suffix", "")).lower()
                data = base64.b64decode(payload["image_b64"], validate=True)
            except (ValueError, KeyError, TypeError, binascii.Error) as exc:
                self._send(400, {"error": f"bad request: {type(exc).__name__}"})
                return
            if payload.get("pipeline") != pipeline:
                self._send(409, {"pipeline": pipeline, "error": f"this server runs {pipeline!r}"})
                return
            if suffix not in SUFFIXES:
                self._send(400, {"error": f"unsupported suffix {suffix!r}"})
                return
            work = Path(tempfile.mkdtemp(prefix="page_"))
            error = None
            try:
                path = work / f"page{suffix}"
                path.write_bytes(data)
                result = adapter(path)
            except Exception as exc:  # noqa: BLE001 - the authors' code failed on this page
                traceback.print_exc()
                error = f"{type(exc).__name__}: {exc}"[:500]
            finally:
                shutil.rmtree(work, ignore_errors=True)  # before the reply: no page stays on the machine
            if error is not None:
                self._send(422, {"pipeline": pipeline, "error": error})
                return
            self._send(200, {"pipeline": pipeline, "text": result["text"], "meta": result.get("meta", {})})

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pipeline", required=True, choices=sorted(PACKAGES))
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--served", required=True, help="served model name of the vLLM server on port 8000")
    ap.add_argument("--layout-dir", help="glmocr_sdk: local directory of the pinned layout model")
    args = ap.parse_args()
    if args.pipeline == "chandra_vllm":
        adapter = chandra_adapter(args.served)
    elif args.pipeline == "dots_parser":
        adapter = dots_adapter(args.served)
    else:
        if not args.layout_dir:
            ap.error("glmocr_sdk needs --layout-dir")
        adapter = glmocr_adapter(args.served, args.layout_dir)
    server = HTTPServer(("127.0.0.1", args.port), make_handler(args.pipeline, adapter, versions(args.pipeline)))
    print(json.dumps({"pipeline": args.pipeline, "port": args.port, "versions": versions(args.pipeline)}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
