"""Engine type pipeline_http and the Pod pipeline server (§10 2026-11-25, batch 3).

The authors' own page pipelines (GLM-OCR SDK, dots.ocr parser, Chandra package) run on the Pod behind
scripts/pipeline_server.py; the harness sends the frozen page and stores the text the authors' code returns.
Ways it could fail, written before the code:
  P1 A config without base_url, pipeline, or model is accepted.
  P2 The request does not carry the frozen image bytes unchanged, or it carries the page name (a gold page ID)
     to the Pod instead of the file suffix alone.
  P3 A server for a different pipeline answers (wrong server on the tunnel) and its text is scored.
  P4 A page-level failure of the authors' code (HTTP 422) aborts the engine instead of failing the page.
  P5 An endpoint failure (5xx, connection refused) writes a page record instead of stopping the engine.
  P6 A reply without a text field is stored as an empty transcription without an error.
  P7 A failed request is sent again (protocol §6: no per-page retries).
  P8 The server's meta (finish_reason, request count) is lost, so the loop guard cannot read it.
  S1 The server runs a pipeline other than the one it was started for.
  S2 An exception of the authors' code kills the server or returns HTTP 200.
  S3 Page images stay on the Pod after the request.
  S4 The adapter sees a file whose suffix differs from the sent suffix (the dots.ocr parser dispatches on it).
"""

import base64
import importlib.util
import json
import threading
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from harness.engines import create_engine
from harness.engines.base import EngineError, EngineUnavailable
from harness.loop_guard import token_limited

ROOT = Path(__file__).resolve().parents[1]


def _config(**overrides):
    config = {"type": "pipeline_http", "base_url": "http://127.0.0.1:9/", "pipeline": "stub", "model": "stub-model"}
    config.update(overrides)
    return config


def _server_module():
    spec = importlib.util.spec_from_file_location("pipeline_server", ROOT / "scripts" / "pipeline_server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def served(tmp_path):
    """A pipeline server on a free port with a stub adapter; yields (base_url, calls)."""
    module = _server_module()
    calls = []

    def adapter(path: Path) -> dict:
        calls.append({"suffix": path.suffix, "bytes": path.read_bytes(), "exists_during": path.exists(), "path": path})
        data = path.read_bytes()
        if data == b"boom":
            raise RuntimeError("authors' code failed")
        return {"text": f"read {len(data)} bytes", "meta": {"finish_reason": "stop", "requests": 1}}

    handler = module.make_handler("stub", adapter, {"stub": "1.0"})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", calls
    server.shutdown()


def test_config_requires_base_url_pipeline_model():  # P1
    for key in ("base_url", "pipeline", "model"):
        with pytest.raises(EngineUnavailable, match=key):
            create_engine("p", _config(**{key: ""}))


def test_request_carries_frozen_bytes_and_suffix_only(served, tmp_path):  # P2, S4, S3
    base, calls = served
    image = tmp_path / "G01.jpg"
    image.write_bytes(b"\xff\xd8frozen-page")
    engine = create_engine("p", _config(base_url=base))
    out = engine.transcribe(image)
    assert out.text == "read 13 bytes"
    assert calls[0]["bytes"] == b"\xff\xd8frozen-page"
    assert calls[0]["suffix"] == ".jpg"
    assert "G01" not in calls[0]["path"].name
    assert calls[0]["exists_during"] and not calls[0]["path"].exists()


def test_engine_sends_no_page_name(monkeypatch, tmp_path):  # P2
    image = tmp_path / "G17.png"
    image.write_bytes(b"png")
    engine = create_engine("p", _config())
    seen = {}

    def fake_post(path, payload):
        seen.update(path=path, payload=payload)
        return {"pipeline": "stub", "text": "x", "meta": {}}

    monkeypatch.setattr(engine, "_post", fake_post)
    engine.transcribe(image)
    assert seen["path"] == "/transcribe"
    assert seen["payload"] == {"pipeline": "stub", "suffix": ".png", "image_b64": base64.b64encode(b"png").decode()}
    assert "G17" not in json.dumps(seen["payload"])


def test_wrong_pipeline_server_is_unavailable(served, tmp_path):  # P3, S1
    base, calls = served
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    engine = create_engine("p", _config(base_url=base, pipeline="other"))
    with pytest.raises(EngineUnavailable, match="pipeline"):
        engine.transcribe(image)
    with pytest.raises(EngineUnavailable, match="pipeline"):
        engine.check()
    assert calls == []


def test_authors_code_failure_fails_the_page_and_server_survives(served, tmp_path):  # P4, S2, S3
    base, calls = served
    bad, good = tmp_path / "a.png", tmp_path / "b.png"
    bad.write_bytes(b"boom")
    good.write_bytes(b"ok")
    engine = create_engine("p", _config(base_url=base))
    with pytest.raises(EngineError) as info:
        engine.transcribe(bad)
    assert not isinstance(info.value, EngineUnavailable)
    assert "authors' code failed" in str(info.value)
    assert not calls[0]["path"].exists()
    assert engine.transcribe(good).text == "read 2 bytes"


def test_endpoint_failure_is_unavailable_and_not_retried(monkeypatch, tmp_path):  # P5, P7
    import harness.engines.pipeline_http as mod

    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    engine = create_engine("p", _config())
    attempts = []

    def refuse(request, timeout):
        attempts.append(request.full_url)
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(mod.urllib.request, "urlopen", refuse)
    with pytest.raises(EngineUnavailable):
        engine.transcribe(image)
    assert len(attempts) == 1


def test_reply_without_text_is_an_error(monkeypatch, tmp_path):  # P6
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    engine = create_engine("p", _config())
    monkeypatch.setattr(engine, "_post", lambda path, payload: {"pipeline": "stub", "meta": {}})
    with pytest.raises(EngineError, match="text"):
        engine.transcribe(image)


def test_meta_is_kept_and_read_by_the_loop_guard(served, tmp_path):  # P8
    base, _ = served
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    engine = create_engine("p", _config(base_url=base))
    out = engine.transcribe(image)
    assert out.meta["finish_reason"] == "stop" and out.meta["requests"] == 1
    desc = engine.describe()
    assert token_limited({"meta": {"finish_reason": "length"}}, desc) is True
    assert token_limited({"meta": {"finish_reason": "stop", "usage": {"completion_tokens": 99999}}}, desc) is False
    assert token_limited({"meta": {}}, desc) is False
