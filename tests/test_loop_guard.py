"""Loop guard (protocol §10, 2026-10-16): runaway VLM outputs cut before scoring.

Ways the guard could fail, written before the code:
  F1 It changes an output that did not stop at the engine's token limit.
  F2 It fires for an engine that reports no token usage (CRNN, Transkribus).
  F3 It edits the stored raw output instead of only the scored hypothesis.
  F4 It fires when usage or the token limit is missing (it must fail safe).
  F5 It misses an exact loop inside one line (short repeating period).
  F6 It misses a loop of repeated lines.
  F7 It cuts text from before the loop starts.
  F8 It changes scores without a trace: guarded pages must carry the rule and the
     unguarded metrics, and the engine result must list them.
  F9 It changes engine configs, so sealed runs would no longer resume.
  F10 It cuts at repeated lines that hold no letter or digit (table rules such as
      `|` or `---`, ditto marks), which repeat on real pages (added 2026-10-18).
  F11 Once F10 is fixed, it misses a runaway of such lines at the end of the output.
"""

import json
from pathlib import Path

import pytest

from harness.cli import main
from harness.loop_guard import cut_loop, token_limited

PAGE = "Erste Zeile des Briefes\nZweite Zeile mit Worten\n"


def test_inline_loop_keeps_text_before_it_and_one_period():  # F5, F7
    text = PAGE + "Dritte Zeile " + "| — " * 400
    cut, rule = cut_loop(text)
    assert rule == "periodic"
    assert cut.startswith(PAGE + "Dritte Zeile ")
    assert len(cut) < len(PAGE) + 40


def test_line_loop_keeps_text_before_it_and_one_copy():  # F6, F7
    text = PAGE + "".join(f"Posten {n}\nSumme\nÜbertrag\n" if n < 3 else "Summe\nÜbertrag\n" for n in range(300))
    cut, rule = cut_loop(text)
    assert rule is not None
    assert cut.startswith(PAGE + "Posten 0\nSumme\nÜbertrag\nPosten 1")
    assert cut.count("Übertrag") <= 3


def test_loop_with_changing_numbers_is_cut_by_the_line_rule():  # F6, F7
    text = PAGE + "\n".join(f"Posten {n}\nSumme" for n in range(100))
    cut, rule = cut_loop(text)
    assert rule == "line"
    assert cut == PAGE + "Posten 0\nSumme\nPosten 1"


def test_repeated_letterless_lines_do_not_trigger_the_line_rule():  # F10, F7
    rows = "".join(f"|\n---\n-\"-\nPosten {n} | {n}.50\n" for n in range(6))
    text = PAGE + rows + "Summe am Ende\n"
    assert cut_loop(text) == (text, None)


def test_runaway_letterless_lines_are_still_cut():  # F11
    text = PAGE + "Dritte Zeile\n" + "|\n" * 300
    cut, rule = cut_loop(text)
    assert rule == "periodic"
    assert cut.startswith(PAGE + "Dritte Zeile")
    assert len(cut) < len(PAGE) + 20


def test_text_without_loop_is_unchanged():  # F7
    text = PAGE + "Dritte Zeile am Ende\n"
    assert cut_loop(text) == (text, None)


def test_trigger_needs_usage_at_the_token_limit():  # F1, F2, F4
    vlm = {"type": "vlm_openai", "config": {"model": "m"}}
    at_limit = {"meta": {"usage": {"completion_tokens": 4096}}}
    below = {"meta": {"usage": {"completion_tokens": 4095}}}
    assert token_limited(at_limit, vlm)
    assert not token_limited(below, vlm)
    assert not token_limited({"meta": {}}, vlm)
    assert not token_limited({}, vlm)
    assert not token_limited(at_limit, {"type": "kraken", "config": {}})
    assert token_limited(
        {"meta": {"usage": {"completion_tokens": 50}}},
        {"type": "mock", "config": {"max_tokens": 50}},
    )


GT = "Erſte Zeile des Briefes\nZweite Zeile mit Worten\nDritte Zeile am Ende"
LOOP = "Erste Zeile des Briefes\nZweite Zeile mit Worten\nDritte Zeile am Ende " + "| — " * 200

SELECTION = """
selection:
  - {id: G01, file: "src/a.jpg", strata: [ugly_kurrent], hand: "h1", period: 1940, license: CC0, note: ""}
"""


@pytest.fixture
def loop_repo(tmp_path: Path) -> dict:
    pil = pytest.importorskip("PIL.Image")
    from harness.gold import sha256_file

    images = tmp_path / "images"
    images.mkdir()
    pil.new("L", (60, 40), color=200).save(images / "G01.jpg")
    (tmp_path / "selection.yml").write_text(SELECTION, encoding="utf-8")
    (tmp_path / "v1_pages.sha256").write_text(f"{sha256_file(images / 'G01.jpg')}  G01.jpg\n", encoding="utf-8")
    for name, body in (("gt", GT), ("hyp", LOOP)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "G01.txt").write_text(body, encoding="utf-8")
    (tmp_path / "entities").mkdir()
    (tmp_path / "entities" / "G01.yml").write_text("entities: []\n", encoding="utf-8")
    hyp = tmp_path / "hyp"
    (tmp_path / "engines.yml").write_text(
        "engines:\n"
        f"  at_limit:\n    type: mock\n    text_dir: {hyp}\n    max_tokens: 50\n    completion_tokens: 50\n"
        f"  below_limit:\n    type: mock\n    text_dir: {hyp}\n    max_tokens: 50\n    completion_tokens: 49\n",
        encoding="utf-8",
    )
    return {"root": tmp_path, "images": images}


def _args(repo: dict) -> list[str]:
    root = repo["root"]
    return ["--selection", str(root / "selection.yml"), "--sha", str(root / "v1_pages.sha256"),
            "--images", str(repo["images"]), "--gt", str(root / "gt"), "--entities", str(root / "entities"),
            "--engines-config", str(root / "engines.yml")]


def test_score_cuts_only_token_limited_outputs_and_keeps_raw(loop_repo):  # F1, F3, F8, F9
    runs = loop_repo["root"] / "runs"
    assert main([*_args(loop_repo), "run", "--engines", "at_limit,below_limit",
                 "--runs-root", str(runs), "--label", "loop"]) == 0
    run_dir = next(runs.iterdir())
    raw_before = (run_dir / "outputs/at_limit/G01.json").read_bytes()
    assert main([*_args(loop_repo), "score", "--run-dir", str(run_dir)]) == 0

    assert (run_dir / "outputs/at_limit/G01.json").read_bytes() == raw_before
    guarded = json.loads((run_dir / "scores/at_limit.json").read_text(encoding="utf-8"))
    plain = json.loads((run_dir / "scores/below_limit.json").read_text(encoding="utf-8"))
    g, p = guarded["pages"]["G01"], plain["pages"]["G01"]
    assert g["loop_guard"]["rule"] == "periodic"
    assert g["loop_guard"]["unguarded"]["cer_norm"] == p["cer_norm"]
    assert g["cer_norm"] < 0.2 < p["cer_norm"]
    assert guarded["loop_guard_pages"] == ["G01"]
    assert "loop_guard" not in p and plain["loop_guard_pages"] == []
    # resuming with the unchanged engine config is still allowed
    assert main([*_args(loop_repo), "run", "--engines", "at_limit,below_limit",
                 "--run-dir", str(run_dir)]) == 0
