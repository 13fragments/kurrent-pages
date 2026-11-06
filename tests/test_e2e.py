"""End-to-end smoke test: mini gold set -> run (mock engine) -> score -> report."""

import json
from pathlib import Path

import pytest

from harness.cli import main
from harness.gold import sha256_file

GT_G01 = "Erſte Zeile des Briefes\nZweite Zeile mit Worten\nDritte Zeile am Ende"
HYP_G01 = "Erste Zeile des Briefes\nZweite Zeile mit Worten\nDritte Zeile am Ende"

SELECTION = """
selection:
  - {id: G01, file: "src/a.jpg", strata: [ugly_kurrent, suetterlin], hand: "h1", period: 1940, license: CC0, note: ""}
  - {id: G02, file: "src/b.jpg", strata: [degraded_fraktur], hand: "print", period: 1943, license: CC0, note: ""}
unscored_annex_candidates:
  - {file: "src/c.jpg", note: "photo page"}
"""

ENTITIES_G01 = """
entities:
  - {type: person, surface: "Erich Wagener", normalized: "Erich Wagener"}
"""


@pytest.fixture
def mini_repo(tmp_path: Path) -> dict:
    pil = pytest.importorskip("PIL.Image")
    images = tmp_path / "images"
    images.mkdir()
    for name in ("G01.jpg", "G02.jpg", "A01_annex.jpg"):
        pil.new("L", (60, 40), color=200).save(images / name)
    (tmp_path / "selection.yml").write_text(SELECTION, encoding="utf-8")
    sha_lines = [
        f"{sha256_file(images / n)}  {n}"
        for n in sorted(p.name for p in images.iterdir())
    ]
    (tmp_path / "v1_pages.sha256").write_text(
        "\n".join(sha_lines) + "\n", encoding="utf-8"
    )
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text(GT_G01, encoding="utf-8")
    (gt / "G02.txt").write_text("Gedruckter Fraktur Text", encoding="utf-8")
    entities = tmp_path / "entities"
    entities.mkdir()
    (entities / "G01.yml").write_text(ENTITIES_G01, encoding="utf-8")
    (entities / "G02.yml").write_text(
        "entities: []\n", encoding="utf-8"
    )  # annotated, none present
    hyp = tmp_path / "hyp"
    hyp.mkdir()
    (hyp / "G01.txt").write_text(HYP_G01 + "\nErich Wagener grüßt", encoding="utf-8")
    (hyp / "A01_annex.txt").write_text(
        "[unleserlich]", encoding="utf-8"
    )  # keyed by image stem
    # G02 hypothesis deliberately missing -> empty output -> seg_fail
    (tmp_path / "engines.yml").write_text(
        f"engines:\n  mock:\n    type: mock\n    text_dir: {hyp}\n", encoding="utf-8"
    )
    return {"root": tmp_path, "images": images}


def _base_args(repo: dict) -> list[str]:
    root = repo["root"]
    return [
        "--selection",
        str(root / "selection.yml"),
        "--sha",
        str(root / "v1_pages.sha256"),
        "--images",
        str(repo["images"]),
        "--gt",
        str(root / "gt"),
        "--entities",
        str(root / "entities"),
        "--engines-config",
        str(root / "engines.yml"),
    ]


def test_full_pipeline(mini_repo, capsys):
    root = mini_repo["root"]
    runs_root = root / "runs"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "smoke",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    assert (run_dir / "run.json").exists()
    out_g01 = json.loads(
        (run_dir / "outputs/mock/G01.json").read_text(encoding="utf-8")
    )
    assert "Erste Zeile" in out_g01["text"]

    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 0
    scores = json.loads((run_dir / "scores/mock.json").read_text(encoding="utf-8"))
    g01 = scores["pages"]["G01"]
    # only the appended greeting differs: ~20 inserted chars over a 68-char reference
    assert 0.2 < g01["cer_norm"] < 0.35
    assert g01["cer_dipl"] > 0.0  # ſ -> s is a diplomatic error
    assert g01["entity_recall"] == 1.0
    assert scores["pages"]["G02"]["seg_fail"] is True
    assert scores["annex_pages"]["A01"]["abstention_ok"] is True
    assert "A01" not in scores["pages"]  # annex never mixes into scored pages
    agg = scores["aggregate"]
    assert agg["overall"]["n"] == 2
    assert agg["hard_strata"]["n"] == 1  # only G01 is hard-strata
    assert agg["per_tag"]["suetterlin"]["n"] == 1  # secondary tag gets its own cut
    assert agg["annex"]["abstention_ok"] == 1

    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 0
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "mock" in report and "kill criterion" in report.lower()

    assert (
        main(
            [
                *_base_args(mini_repo),
                "adjudication-templates",
                "--run-dir",
                str(run_dir),
            ]
        )
        == 0
    )
    templates = sorted((run_dir / "adjudications" / "mock").glob("*.yml"))
    assert [path.stem for path in templates] == ["G01", "G02"]
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 0
    pending_scores = json.loads(
        (run_dir / "scores/mock.json").read_text(encoding="utf-8")
    )
    assert pending_scores["invalid_adjudications"] == []
    assert {
        score["adjudication_status"] for score in pending_scores["pages"].values()
    } == {"unadjudicated"}
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 0
    template_args = [
        *_base_args(mini_repo),
        "adjudication-templates",
        "--run-dir",
        str(run_dir),
    ]
    assert main(template_args) == 0  # untouched templates are idempotently preserved
    templates[1].unlink()  # interrupted packet generation resumes missing forms
    assert main(template_args) == 0
    assert sorted(path.stem for path in templates[0].parent.glob("*.yml")) == [
        "G01",
        "G02",
    ]


def test_score_fails_on_unannotated_page(mini_repo):
    root = mini_repo["root"]
    (root / "entities" / "G01.yml").unlink()
    runs_root = root / "runs_ent"
    # run only proceeds via the smoke override now that annotations gate it too
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--allow-incomplete-gt",
                "--runs-root",
                str(runs_root),
                "--label",
                "e",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 1
    assert (
        main(
            [
                *_base_args(mini_repo),
                "adjudication-templates",
                "--run-dir",
                str(run_dir),
            ]
        )
        == 1
    )
    assert not (run_dir / "adjudications").exists()


def test_score_and_report_fail_on_partial_run(mini_repo):
    root = mini_repo["root"]
    runs_root = root / "runs_partial"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "p",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    (run_dir / "outputs/mock/G02.json").unlink()  # simulate an aborted run
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 1
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 1
    assert (run_dir / "report.md").exists()  # report written for inspection anyway
    assert "INCOMPLETE REPORT" in (run_dir / "report.md").read_text(encoding="utf-8")
    assert (
        main(
            [
                *_base_args(mini_repo),
                "adjudication-templates",
                "--run-dir",
                str(run_dir),
            ]
        )
        == 1
    )
    assert not (run_dir / "adjudications").exists()


def test_score_report_and_templates_reject_wrong_frozen_image_hash(mini_repo):
    root = mini_repo["root"]
    runs_root = root / "runs_wrong_image"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "wrong-image",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    record_path = run_dir / "outputs/mock/G01.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["image_sha256"] = "f" * 64
    record_path.write_text(json.dumps(record), encoding="utf-8")

    args = [*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]
    assert main(args) == 1
    scores = json.loads((run_dir / "scores/mock.json").read_text(encoding="utf-8"))
    assert scores["unbound_image_pages"] == ["G01"]
    assert "G01" not in scores["pages"]
    assert scores["aggregate"]["kill_check"]["complete"] is False
    assert scores["aggregate"]["kill_check"]["kill"] is False
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 1
    assert "outputs without a valid image hash" in (run_dir / "report.md").read_text(
        encoding="utf-8"
    )
    assert (
        main(
            [
                *_base_args(mini_repo),
                "adjudication-templates",
                "--run-dir",
                str(run_dir),
            ]
        )
        == 1
    )
    assert not (run_dir / "adjudications").exists()


def test_score_and_report_refuse_wrong_selection(mini_repo, capsys):
    root = mini_repo["root"]
    runs_root = root / "runs_mismatch"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "m",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    wrong_selection = root / "wrong_selection.yml"
    wrong_selection.write_text(
        """
selection:
  - {id: X01, file: "src/x.jpg", strata: [ugly_kurrent], hand: "h1", period: 1940, license: CC0, note: ""}
  - {id: X02, file: "src/y.jpg", strata: [degraded_fraktur], hand: "print", period: 1943, license: CC0, note: ""}
""",
        encoding="utf-8",
    )
    wrong_base = [
        "--selection",
        str(wrong_selection),
        "--gt",
        str(root / "gt"),
        "--entities",
        str(root / "entities"),
    ]

    assert main([*wrong_base, "score", "--run-dir", str(run_dir)]) == 2
    assert main([*wrong_base, "report", "--run-dir", str(run_dir)]) == 2
    captured = capsys.readouterr()
    assert "is not the selection recorded" in captured.err
    assert "Pass the selection used for this run" in captured.err
    assert not (run_dir / "scores" / "mock.json").exists()
    assert not (run_dir / "report.md").exists()


def test_score_and_report_reject_drifted_selection(mini_repo, capsys):
    # Same page IDs but an edited selection file (different strata/metadata → different
    # hash) must be rejected: per-stratum and Gate-0 aggregates depend on the exact
    # selection recorded at run time.
    root = mini_repo["root"]
    runs_root = root / "runs_drift"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "d",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    sel = root / "selection.yml"
    sel.write_text(
        sel.read_text(encoding="utf-8") + "\n# edited after the run\n", encoding="utf-8"
    )
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 2
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 2
    assert "is not the selection recorded" in capsys.readouterr().err
    assert not (run_dir / "scores" / "mock.json").exists()


def test_check_fails_until_gt_complete(mini_repo):
    # both scored pages have GT in the fixture -> check passes
    assert main([*_base_args(mini_repo), "check"]) == 0
    (mini_repo["root"] / "gt" / "G02.txt").unlink()
    assert main([*_base_args(mini_repo), "check"]) == 1


def test_check_fails_until_entities_complete(mini_repo):
    # both scored pages have entity annotations in the fixture -> check passes
    assert main([*_base_args(mini_repo), "check"]) == 0
    (mini_repo["root"] / "entities" / "G02.yml").unlink()
    assert main([*_base_args(mini_repo), "check"]) == 1


def test_score_and_report_fail_cleanly_without_outputs_dir(mini_repo):
    run_dir = mini_repo["root"] / "empty_run"
    run_dir.mkdir()
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 1
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 1


def test_run_blocked_until_gt_complete(mini_repo):
    (mini_repo["root"] / "gt" / "G02.txt").unlink()
    args = [
        *_base_args(mini_repo),
        "run",
        "--engines",
        "mock",
        "--runs-root",
        str(mini_repo["root"] / "runs_gt"),
        "--label",
        "x",
    ]
    assert main(args) == 2  # §2 ordering: no engine output before GT
    assert main([*args, "--allow-incomplete-gt"]) == 0  # explicit smoke override


def test_run_blocked_until_entities_complete(mini_repo):
    (mini_repo["root"] / "entities" / "G02.yml").unlink()
    args = [
        *_base_args(mini_repo),
        "run",
        "--engines",
        "mock",
        "--runs-root",
        str(mini_repo["root"] / "runs_e2"),
        "--label",
        "x",
    ]
    assert main(args) == 2  # entity annotations are gold targets too (§2)


def test_run_succeeds_with_terminal_page_failures(mini_repo, tmp_path):
    """A deterministic per-page failure is a recorded, scoreable result: the
    run must exit 0 (only unrecorded pages make a run incomplete)."""
    root = mini_repo["root"]
    runs_root = root / "runs_term"
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--runs-root",
                str(runs_root),
                "--label",
                "t",
            ]
        )
        == 0
    )
    run_dir = next(runs_root.iterdir())
    record_path = run_dir / "outputs/mock/G01.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["error"] = "segmentation failed"
    record["text"] = ""
    record_path.write_text(json.dumps(record), encoding="utf-8")
    # Resume: failed-terminal is a recorded result -> exit 0.
    assert (
        main(
            [
                *_base_args(mini_repo),
                "run",
                "--engines",
                "mock",
                "--run-dir",
                str(run_dir),
                "--label",
                "t",
            ]
        )
        == 0
    )


def test_freeze_check_blocks_modified_image(mini_repo):
    (mini_repo["images"] / "G01.jpg").write_bytes(b"tampered")
    code = main(
        [
            *_base_args(mini_repo),
            "run",
            "--engines",
            "mock",
            "--runs-root",
            str(mini_repo["root"] / "runs2"),
            "--label",
            "x",
        ]
    )
    assert code == 2


def test_freeze_check_blocks_unhashed_selected_page(mini_repo):
    # Remove G01's line from the manifest: the page image exists but is no
    # longer covered by the freeze — the run must be blocked.
    sha = mini_repo["root"] / "v1_pages.sha256"
    lines = [
        line
        for line in sha.read_text(encoding="utf-8").splitlines()
        if "G01.jpg" not in line
    ]
    sha.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code = main(
        [
            *_base_args(mini_repo),
            "run",
            "--engines",
            "mock",
            "--runs-root",
            str(mini_repo["root"] / "runs3"),
            "--label",
            "x",
        ]
    )
    assert code == 2


# Annex pages are reported, not gating (§10, 2026-10-18): both contain real text.
# Ways the demotion could fail, written before the code:
#   D1 A failed or missing annex output still marks score or report incomplete.
#   D2 T3 completeness still depends on the annex pages (tests/test_report.py).
#   D3 The report still presents annex results as abstention evidence (test_report.py).
#   D4 Over-correction: a missing scored page no longer marks the run incomplete
#      (test_score_and_report_fail_on_partial_run).
#   D5 Annex outputs or their gaps disappear from the results instead of being reported.


def _run_mock(mini_repo, label: str) -> Path:
    runs_root = mini_repo["root"] / f"runs_{label}"
    args = [*_base_args(mini_repo), "run", "--engines", "mock", "--runs-root", str(runs_root)]
    assert main([*args, "--label", label]) == 0
    return next(runs_root.iterdir())


def test_failed_annex_output_is_reported_but_does_not_mark_the_run_incomplete(mini_repo):  # D1, D5
    run_dir = _run_mock(mini_repo, "annexfail")
    record_path = run_dir / "outputs/mock/A01.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["error"] = "never uploaded"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 0
    assert main([*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]) == 0
    scores = json.loads((run_dir / "scores/mock.json").read_text(encoding="utf-8"))
    assert scores["annex_failed_pages"] == ["A01"]
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "INCOMPLETE REPORT" not in report
    assert "reported only" in report


def test_missing_annex_output_is_reported_but_does_not_mark_the_run_incomplete(mini_repo):  # D1, D5
    run_dir = _run_mock(mini_repo, "annexmissing")
    (run_dir / "outputs/mock/A01.json").unlink()
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 0
    scores = json.loads((run_dir / "scores/mock.json").read_text(encoding="utf-8"))
    assert scores["missing_pages"] == []
    assert scores["annex_failed_pages"] == ["A01"]


def test_gold_review_packets_from_a_scored_run(mini_repo, tmp_path, monkeypatch, capsys):
    # Failure modes: packets from an unscored or rescored-elsewhere run, an
    # engine or page ID leaking into reviewer files, a dry run that prints
    # private text, gold packets written to a tracked path.
    from harness import pilot_gold
    from harness.pilot import main as pilot_main

    run_dir = _run_mock(mini_repo, "gold")
    root = mini_repo["root"]
    gold_args = [
        "export-gold", "--run-dir", str(run_dir), "--engine", "mock",
        "--selection", str(root / "selection.yml"), "--sha", str(root / "v1_pages.sha256"),
        "--images", str(mini_repo["images"]), "--gt", str(root / "gt"),
    ]
    capsys.readouterr()
    assert pilot_main([*gold_args, "--dry-run"]) == 2  # not scored yet
    assert "cannot read a run file" in capsys.readouterr().out
    assert main([*_base_args(mini_repo), "score", "--run-dir", str(run_dir)]) == 0
    capsys.readouterr()

    assert pilot_main([*gold_args, "--dry-run"]) == 0
    printed = capsys.readouterr().out
    summary = json.loads(printed)
    assert summary["dry_run"] and summary["unit_count"] == 2 and summary["empty_hypotheses"] == 1
    for private in ("G01", "G02", "Zeile", "Wagener", "mock"):
        assert private not in printed

    outside = tmp_path / "not-ignored"
    assert pilot_main([*gold_args, "--seed", "t3-test", "--out", str(outside)]) == 2
    assert not outside.exists()

    monkeypatch.setattr(pilot_gold, "_git_ignored", lambda path: True)
    out = tmp_path / "gold-packets"
    assert pilot_main([*gold_args, "--seed", "t3-test", "--out", str(out)]) == 0
    reviewer_files = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in out.glob("packets/*/*") if path.is_file()
    )
    for private in ("G01", "G02", "mock", str(run_dir.name)):
        assert private not in reviewer_files
    packets = [json.loads(p.read_text()) for p in sorted(out.glob("packets/*/packet.json"))]
    assert all(p["reference_source"] == "gold" for p in packets)
    assert {u["unit_id"] for u in packets[0]["units"]} == {u["unit_id"] for u in packets[1]["units"]}
    g01 = next(u for u in packets[0]["units"] if u["hypothesis_normalized"].startswith("Erste"))
    assert len(g01["line_breaks"]) == 3
    coordinator = json.loads((out / "coordinator/map.json").read_text())
    assert {u["source"]["page"] for u in coordinator["units"].values()} == {"G01", "G02"}


def test_gold_export_refuses_tracked_paths():
    from harness.pilot_gold import _git_ignored

    repo = Path(__file__).resolve().parents[1]
    assert _git_ignored(repo / "evals" / "own_gold" / "t3-packets")
    assert not _git_ignored(repo / "harness" / "t3-packets")


# Aggregates-only report (release v1.0, blocker B7). Ways a public report can leak:
# P1 a page ID (gap lists, examples, the annex character dict keyed by page);
# P2 output or GT text (example sections); P3 a group of one page, whose median is
# that page's score; P4 a `*_max` field, which is one page's value; P5 a private
# path from run.json; P6 overwriting the private report.md; P7 a partial run that
# looks complete.
def _public_outputs(out_dir: Path) -> str:
    return "\n".join(
        (out_dir / name).read_text(encoding="utf-8")
        for name in ("report_public.md", "aggregates.json")
    )


def test_aggregates_only_report_publishes_no_page_text_or_path(mini_repo):  # P1-P6
    run_dir = _run_mock(mini_repo, "public")
    out_dir = mini_repo["root"] / "public"
    args = [*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]
    assert main([*args, "--aggregates-only", "--out", str(out_dir)]) == 0
    published = _public_outputs(out_dir)
    for leak in ("G01", "G02", "A01", "Zeile", "Erich", "Wagener", "unleserlich"):
        assert leak not in published  # P1, P2
    assert str(mini_repo["root"]) not in published  # P5
    assert "_max" not in published  # P4
    aggregates = json.loads((out_dir / "aggregates.json").read_text(encoding="utf-8"))
    mock = aggregates["engines"]["mock"]
    assert mock["overall"]["n"] == 2 and mock["overall"]["cer_norm_median"] is not None
    assert mock["hard_strata"] == {"n": 1, "suppressed": True}  # P3
    assert all(group == {"n": 1, "suppressed": True} for group in mock["per_stratum"].values())
    assert mock["annex"] == {"pages": 1, "abstention_ok": 1, "hallucinated_chars_total": 0}
    assert not (run_dir / "report.md").exists()  # P6


def test_aggregates_only_report_refuses_a_partial_run(mini_repo):  # P7
    run_dir = _run_mock(mini_repo, "publicpartial")
    (run_dir / "outputs/mock/G01.json").unlink()
    out_dir = mini_repo["root"] / "public_partial"
    args = [*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]
    assert main([*args, "--aggregates-only", "--out", str(out_dir)]) == 1
    assert "INCOMPLETE" in (out_dir / "report_public.md").read_text(encoding="utf-8")
    aggregates = json.loads((out_dir / "aggregates.json").read_text(encoding="utf-8"))
    assert aggregates["engines"]["mock"]["gaps"]["missing_pages"] == 1
    assert "G01" not in _public_outputs(out_dir)


# Submission import (O4). Ways an imported bundle can be scored wrongly: I1 a file
# for a page outside the selection; I2 an output from a different image (hash
# mismatch); I3 a missing scored page that silently shrinks the population instead of
# counting as a failure (§1); I4 an engine name that escapes the runs root; I5 an
# import that overwrites an earlier scored run; I6 a page file that is a symlink (to a
# private GT file, say).
def _bundle(mini_repo, tmp_path: Path, pages: dict[str, str], hashes: dict | None = None) -> Path:
    images = mini_repo["images"]
    bundle = tmp_path / "bundle"
    (bundle / "pages").mkdir(parents=True)
    for page, text in pages.items():
        (bundle / "pages" / f"{page}.txt").write_text(text, encoding="utf-8")
    meta = {
        "engine": "acme_htr",
        "engine_version": "2.1",
        "benchmark_version": "Kurrent Pages Benchmark v1.0",
        "description": "test engine",
        "image_sha256": hashes
        or {page: sha256_file(images / f"{page}.jpg") for page in ("G01", "G02")},
        "length_stopped": [],
    }
    (bundle / "run.json").write_text(json.dumps(meta), encoding="utf-8")
    return bundle


def _import(mini_repo, bundle: Path, runs_root: Path) -> int:
    import subprocess
    import sys

    root = mini_repo["root"]
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts/import_submission.py"),
         "--bundle", str(bundle), "--runs-root", str(runs_root),
         "--selection", str(root / "selection.yml"), "--sha", str(root / "v1_pages.sha256")],
        capture_output=True, text=True,
    ).returncode


def test_imported_submission_scores_missing_pages_as_failures(mini_repo, tmp_path):  # I3, I5
    bundle = _bundle(mini_repo, tmp_path, {"G01": HYP_G01})
    runs_root = mini_repo["root"] / "submissions"
    assert _import(mini_repo, bundle, runs_root) == 0
    run_dir = next(runs_root.iterdir())
    out_dir = mini_repo["root"] / "submission_public"
    args = [*_base_args(mini_repo), "report", "--run-dir", str(run_dir)]
    assert main([*args, "--aggregates-only", "--out", str(out_dir)]) == 0
    engine = json.loads((out_dir / "aggregates.json").read_text(encoding="utf-8"))["engines"]["acme_htr"]
    assert engine["overall"]["n"] == 2 and engine["gaps"]["error_pages"] == 1
    assert engine["overall"]["seg_fail_rate"] == 0.5
    assert _import(mini_repo, bundle, runs_root) == 0  # a second import gets its own run dir
    assert len(list(runs_root.iterdir())) == 2


def test_import_rejects_foreign_pages_wrong_images_bad_names_and_links(mini_repo, tmp_path):  # I1, I2, I4, I6
    runs_root = mini_repo["root"] / "rejected"
    foreign = _bundle(mini_repo, tmp_path / "a", {"G01": "x", "D01": "y"})
    assert _import(mini_repo, foreign, runs_root) == 2
    wrong_hash = _bundle(mini_repo, tmp_path / "b", {"G01": "x"}, {"G01": "0" * 64, "G02": "0" * 64})
    assert _import(mini_repo, wrong_hash, runs_root) == 2
    bad_name = _bundle(mini_repo, tmp_path / "c", {"G01": "x"})
    meta = json.loads((bad_name / "run.json").read_text(encoding="utf-8"))
    (bad_name / "run.json").write_text(json.dumps({**meta, "engine": "../x"}), encoding="utf-8")
    assert _import(mini_repo, bad_name, runs_root) == 2
    linked = _bundle(mini_repo, tmp_path / "d", {"G02": "x"})
    (linked / "pages/G01.txt").symlink_to(mini_repo["root"] / "gt/G01.txt")
    assert _import(mini_repo, linked, runs_root) == 2  # I6
    assert not runs_root.exists() or not any(runs_root.iterdir())
