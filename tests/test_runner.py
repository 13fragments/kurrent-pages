"""Resume/abort semantics of the run store — benchmark-integrity critical."""

import json
from pathlib import Path

import pytest
import yaml

from harness.engines.base import Engine, EngineError, EngineOutput, EngineUnavailable
from harness.gold import GoldPage, sha256_file
from harness.runner import run_engines, run_meta_conflicts, write_run_meta


class FlakyEngine(Engine):
    """Fails on the first call per page, succeeds afterwards."""

    def __init__(self):
        super().__init__("flaky", {})
        self.calls: dict[str, int] = {}

    def transcribe(self, image: Path) -> EngineOutput:
        n = self.calls.get(image.name, 0) + 1
        self.calls[image.name] = n
        if n == 1:
            raise EngineError("transient failure")
        return EngineOutput(text="recovered text", model_id="flaky", duration_s=0.0)


class DyingEngine(Engine):
    """Succeeds once, then the endpoint 'dies'."""

    def __init__(self):
        super().__init__("dying", {})
        self.calls = 0

    def transcribe(self, image: Path) -> EngineOutput:
        self.calls += 1
        if self.calls > 1:
            raise EngineUnavailable("endpoint gone")
        return EngineOutput(text="ok", model_id="dying", duration_s=0.0)


def _pages_and_images(tmp_path: Path, n: int = 3):
    images = tmp_path / "images"
    images.mkdir()
    pages = []
    for i in range(1, n + 1):
        gid = f"G{i:02d}"
        (images / f"{gid}.jpg").write_bytes(b"not-a-real-jpg")
        pages.append(
            GoldPage(
                id=gid, image_name=f"{gid}.jpg", strata=("suetterlin",), scored=True
            )
        )
    return pages, images


def test_recorded_failures_are_terminal_within_a_run(tmp_path: Path):
    """§6 single attempt: an error record is this run's result; resume must
    NOT quietly improve a scored run. A fresh run dir is a new attempt."""
    pages, images = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    engine = FlakyEngine()
    status1 = run_engines({"flaky": engine}, pages, images, run_dir)
    assert status1["flaky"]["G01"].startswith("error")
    record = json.loads(
        (run_dir / "outputs/flaky/G01.json").read_text(encoding="utf-8")
    )
    assert record["error"] and record["text"] == ""

    # Resume: recorded failure is terminal, engine not called again.
    status2 = run_engines({"flaky": engine}, pages, images, run_dir)
    assert status2["flaky"]["G01"] == "failed-terminal"
    assert engine.calls["G01.jpg"] == 1
    record = json.loads(
        (run_dir / "outputs/flaky/G01.json").read_text(encoding="utf-8")
    )
    assert "error" in record  # record untouched

    # A fresh run dir is a legitimate new attempt.
    status3 = run_engines({"flaky": engine}, pages, images, tmp_path / "run2")
    assert status3["flaky"]["G01"] == "ok"


class ConfigurableEngine(Engine):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)

    def transcribe(self, image: Path) -> EngineOutput:
        return EngineOutput(text="text", model_id="v", duration_s=0.0)


def test_resume_refuses_config_mismatch(tmp_path: Path):
    pages, images = _pages_and_images(tmp_path, n=2)
    run_dir = tmp_path / "run"
    status1 = run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "a"})}, pages, images, run_dir
    )
    assert all(s == "ok" for s in status1["eng"].values())

    # Same run dir, changed config: resume must refuse ALL pages, not mix outputs.
    status2 = run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "b"})}, pages, images, run_dir
    )
    assert all(s.startswith("resume-conflict") for s in status2["eng"].values())

    # Original config resumes cleanly.
    status3 = run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "a"})}, pages, images, run_dir
    )
    assert all(s == "exists" for s in status3["eng"].values())


def test_resume_refuses_changed_image(tmp_path: Path):
    pages, images = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    engine = ConfigurableEngine("eng", {"model": "a"})
    run_engines({"eng": engine}, pages, images, run_dir)

    (images / "G01.jpg").write_bytes(b"swapped-image-bytes")
    status = run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "a"})}, pages, images, run_dir
    )
    assert status["eng"]["G01"].startswith("resume-conflict")  # refused, not reused


def test_resume_conflict_checks_failed_records_too(tmp_path: Path):
    """A terminal failure is a result; resuming over it with a new config must
    refuse, not attribute the old empty output to the new config."""
    pages, images = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    run_engines({"eng": FlakyEngine()}, pages, images, run_dir)  # writes error record
    from harness.runner import resume_conflicts

    changed = ConfigurableEngine("eng", {"model": "different"})
    conflicts = resume_conflicts({"eng": changed}, pages, images, run_dir)
    assert "eng" in conflicts


def test_resume_conflict_prescan_blocks_partial_run_mixing(tmp_path: Path):
    """Earlier pages missing, later page exists from config A: resuming with
    config B must not transcribe ANY page with B."""
    pages, images = _pages_and_images(tmp_path, n=2)
    run_dir = tmp_path / "run"
    run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "a"})}, [pages[1]], images, run_dir
    )
    assert (run_dir / "outputs/eng/G02.json").exists()

    status = run_engines(
        {"eng": ConfigurableEngine("eng", {"model": "b"})}, pages, images, run_dir
    )
    assert all(s.startswith("resume-conflict") for s in status["eng"].values())
    assert not (
        run_dir / "outputs/eng/G01.json"
    ).exists()  # nothing written with config B


def test_engine_unavailable_aborts_remaining_pages(tmp_path: Path):
    pages, images = _pages_and_images(tmp_path, n=3)
    run_dir = tmp_path / "run"
    status = run_engines({"dying": DyingEngine()}, pages, images, run_dir)
    assert status["dying"]["G01"] == "ok"
    assert status["dying"]["G02"].startswith("unavailable")
    assert status["dying"]["G03"].startswith("aborted")
    # No poisoned records for the aborted pages.
    assert not (run_dir / "outputs/dying/G02.json").exists()
    assert not (run_dir / "outputs/dying/G03.json").exists()


def test_score_run_skips_error_records(tmp_path: Path):
    from harness.runner import score_run

    pages, images = _pages_and_images(tmp_path, n=2)
    annex = GoldPage(id="A01", image_name="A01_annex.jpg", strata=(), scored=False)
    (images / annex.image_name).write_bytes(b"not-a-real-jpg")
    image_hash = sha256_file(images / pages[0].image_name)
    run_dir = tmp_path / "run"
    out = run_dir / "outputs" / "eng"
    out.mkdir(parents=True)
    (out / "G01.json").write_text(
        json.dumps({"page": "G01", "text": "Erste Zeile", "image_sha256": image_hash}),
        encoding="utf-8",
    )
    (out / "G02.json").write_text(
        json.dumps(
            {
                "page": "G02",
                "text": "",
                "error": "boom",
                "image_sha256": image_hash,
            }
        ),
        encoding="utf-8",
    )
    # a crashed engine on the annex page must NOT count as clean abstention
    (out / "A01.json").write_text(
        json.dumps(
            {
                "page": "A01",
                "text": "",
                "error": "boom",
                "image_sha256": image_hash,
            }
        ),
        encoding="utf-8",
    )
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(
        "".join(f"{image_hash}  {page.image_name}\n" for page in [*pages[:2], annex]),
        encoding="utf-8",
    )
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "freeze_sha_path": str(freeze),
                "freeze_sha256": sha256_file(freeze),
            }
        ),
        encoding="utf-8",
    )
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("Erste Zeile", encoding="utf-8")
    (gt / "G02.txt").write_text("Zweite Zeile", encoding="utf-8")
    results = score_run(run_dir, [*pages[:2], annex], gt, tmp_path / "entities")
    result = results["eng"]
    assert result["error_pages"] == ["G02"]
    assert result["annex_failed_pages"] == [
        "A01"
    ]  # failed probe is listed, never clean
    # Deterministic pipeline failure on a scored page counts AGAINST the
    # engine (§1): scored as empty output -> seg_fail, cer_norm 1.0.
    assert result["pages"]["G02"]["seg_fail"] is True
    assert result["pages"]["G02"]["cer_norm"] == 1.0
    # ...but a crashed engine never counts as annex-clean abstention.
    assert result["annex_pages"] == {}
    assert result["aggregate"]["annex"]["pages"] == 0


def test_score_run_reports_missing_outputs(tmp_path: Path):
    from harness.runner import score_run

    pages, _ = _pages_and_images(tmp_path, n=2)
    run_dir = tmp_path / "run"
    out = run_dir / "outputs" / "eng"
    out.mkdir(parents=True)
    (out / "G01.json").write_text(
        json.dumps({"page": "G01", "text": "Erste Zeile"}), encoding="utf-8"
    )
    # G02 output missing entirely (aborted run)
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("Erste Zeile", encoding="utf-8")
    (gt / "G02.txt").write_text("Zweite Zeile", encoding="utf-8")
    result = score_run(run_dir, pages, gt, tmp_path / "entities")["eng"]
    assert result["missing_pages"] == ["G02"]


def test_score_run_returns_empty_without_outputs_dir(tmp_path: Path):
    from harness.runner import score_run

    pages, images = _pages_and_images(tmp_path, n=1)
    assert (
        score_run(tmp_path / "run", pages, tmp_path / "gt", tmp_path / "entities") == {}
    )


def test_score_run_imports_hash_bound_adjudication(tmp_path: Path):
    from harness.adjudication import adjudication_template
    from harness.runner import score_run
    from harness.scoring import score_page

    pages, images = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    output = run_dir / "outputs" / "eng" / "G01.json"
    output.parent.mkdir(parents=True)
    hyp = "eins zwei drei fremder inhalt ohne bild jetzt"
    image_hash = "a" * 64
    output.write_text(
        json.dumps({"page": "G01", "text": hyp, "image_sha256": image_hash}),
        encoding="utf-8",
    )
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("eins zwei drei", encoding="utf-8")
    entities = tmp_path / "entities"
    entities.mkdir()
    (entities / "G01.yml").write_text("entities: []\n", encoding="utf-8")

    page_score = score_page("eins zwei drei", hyp, entities=[])
    page_score["image_sha256"] = image_hash
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{image_hash}  G01.jpg\n", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "freeze_sha_path": "/old/machine/freeze.sha256",
                "freeze_sha256": sha256_file(freeze),
            }
        ),
        encoding="utf-8",
    )
    form = adjudication_template("eng", "G01", page_score)
    assert form["spans"]
    for index, review in enumerate(form["reviews"]):
        review["reviewer"] = f"reviewer-{index + 1}"
        review["full_page_reviewed"] = True
        for item in review["candidate_labels"]:
            item["label"] = "fluent_fabrication" if index == 0 else "perception_error"
        for item in review["entity_labels"]:
            item["label"] = "supported"
    for item in form["spans"]:
        item["label"] = "fluent_fabrication"
    for item in form["entities"]:
        item["label"] = "supported"
    form["resolver"] = "private-resolver"
    adjudication = run_dir / "adjudications" / "eng" / "G01.yml"
    adjudication.parent.mkdir(parents=True)
    adjudication.write_text(yaml.safe_dump(form), encoding="utf-8")

    result = score_run(run_dir, pages, gt, entities, freeze_sha_path=freeze)["eng"]
    assert result["invalid_adjudications"] == []
    assert result["pages"]["G01"]["adjudication_status"] == "complete"
    assert result["aggregate"]["overall"]["fab_page_rate_adj"] == 1.0
    assert "adjudication_reviewers" not in result["pages"]["G01"]
    assert "adjudication_resolver" not in result["pages"]["G01"]
    serialized = (run_dir / "scores" / "eng.json").read_text(encoding="utf-8")
    assert "reviewer-1" not in serialized
    assert "reviewer-2" not in serialized
    assert "private-resolver" not in serialized


def test_score_run_requires_frozen_image_binding_for_annex_outputs(tmp_path: Path):
    from harness.runner import score_run

    annex = GoldPage(id="A01", image_name="A01.jpg", strata=(), scored=False)
    run_dir = tmp_path / "run"
    output = run_dir / "outputs" / "eng" / "A01.json"
    output.parent.mkdir(parents=True)
    output.write_text(
        json.dumps({"page": "A01", "text": "", "image_sha256": "a" * 64}),
        encoding="utf-8",
    )
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{'b' * 64}  A01.jpg\n", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "freeze_sha_path": str(freeze),
                "freeze_sha256": sha256_file(freeze),
            }
        ),
        encoding="utf-8",
    )

    result = score_run(run_dir, [annex], tmp_path / "gt", tmp_path / "entities")["eng"]
    assert result["unbound_image_pages"] == ["A01"]
    assert result["annex_pages"] == {}
    assert result["aggregate"]["annex"]["pages"] == 0
    assert result["aggregate"]["trust_check"]["annex_complete"] is False


def test_score_run_surfaces_invalid_adjudication(tmp_path: Path):
    from harness.runner import score_run

    pages, images = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    output = run_dir / "outputs" / "eng" / "G01.json"
    output.parent.mkdir(parents=True)
    image_hash = sha256_file(images / pages[0].image_name)
    output.write_text(
        json.dumps({"page": "G01", "text": "eins zwei", "image_sha256": image_hash}),
        encoding="utf-8",
    )
    freeze = tmp_path / "freeze.sha256"
    freeze.write_text(f"{image_hash}  G01.jpg\n", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "freeze_sha_path": str(freeze),
                "freeze_sha256": sha256_file(freeze),
            }
        ),
        encoding="utf-8",
    )
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("eins zwei", encoding="utf-8")
    adjudication = run_dir / "adjudications" / "eng" / "G01.yml"
    adjudication.parent.mkdir(parents=True)
    adjudication.write_text("full_page_reviewed: false\n", encoding="utf-8")

    result = score_run(run_dir, pages, gt, tmp_path / "entities")["eng"]
    assert len(result["invalid_adjudications"]) == 1
    assert result["pages"]["G01"]["adjudication_status"] == "invalid"


def test_score_run_surfaces_engine_with_no_output_directory(tmp_path: Path):
    from harness.runner import score_run

    pages, _ = _pages_and_images(tmp_path, n=1)
    run_dir = tmp_path / "run"
    output = run_dir / "outputs" / "present" / "G01.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps({"page": "G01", "text": "eins"}), encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({"engines": {"present": {}, "absent": {}}}), encoding="utf-8"
    )
    gt = tmp_path / "gt"
    gt.mkdir()
    (gt / "G01.txt").write_text("eins", encoding="utf-8")
    entities = tmp_path / "entities"
    entities.mkdir()
    (entities / "G01.yml").write_text("entities: []\n", encoding="utf-8")

    results = score_run(run_dir, pages, gt, entities)
    assert set(results) == {"absent", "present"}
    assert results["absent"]["missing_pages"] == ["G01"]
    assert results["absent"]["aggregate"]["overall"]["n"] == 0


def test_run_wide_reviewer_pair_and_order_are_enforced():
    from harness.runner import _enforce_consistent_reviewer_pair

    scores = {
        "G01": {
            "adjudication_status": "complete",
            "adjudication_reviewers": ["Reviewer A", "Reviewer B"],
        },
        "G02": {
            "adjudication_status": "complete",
            "adjudication_reviewers": ["reviewer b", "reviewer a"],
        },
        "G03": {
            "adjudication_status": "complete",
            "adjudication_reviewers": ["Reviewer A", "Reviewer C"],
        },
    }
    invalid = []
    _enforce_consistent_reviewer_pair(scores, invalid)
    assert scores["G01"]["adjudication_status"] == "complete"
    assert scores["G02"]["adjudication_status"] == "invalid"
    assert scores["G03"]["adjudication_status"] == "invalid"
    assert len(invalid) == 2


def test_annotated_page_with_zero_entities_counts_as_covered():
    from harness.report import _stats
    from harness.scoring import score_page

    with_empty_annotation = score_page(
        "Text ohne Namen", "Text ohne Namen", entities=[]
    )
    assert with_empty_annotation["entity_annotated"] is True
    assert with_empty_annotation["entity_recall"] is None
    unannotated = score_page("Text ohne Namen", "Text ohne Namen", entities=None)
    stats = _stats([with_empty_annotation, unannotated])
    assert stats["entity_pages"] == 1  # coverage counts annotations, not recalls


def test_kill_check_requires_complete_coverage(tmp_path: Path):
    from harness.report import kill_check

    # perfect numbers but only 3 of 35 hard pages scored -> cannot fire
    partial = {
        "n": 3,
        "entity_pages": 3,
        "cer_norm_median": 0.1,
        "entity_recall_median": 0.9,
        "seg_fail_rate": 0.0,
    }
    verdict = kill_check(partial, expected_pages=35)
    assert verdict["complete"] is False and verdict["kill"] is False
    complete = {**partial, "n": 35, "entity_pages": 35}
    verdict = kill_check(complete, expected_pages=35)
    assert verdict["complete"] is True and verdict["kill"] is True
    verdict = kill_check(complete, expected_pages=35, eligible=False)
    assert verdict["conditions_met"] is True and verdict["kill"] is False
    # entity annotations missing on some hard pages -> incomplete
    verdict = kill_check({**complete, "entity_pages": 30}, expected_pages=35)
    assert verdict["kill"] is False


def test_kill_eligibility_includes_open_crnn_candidates():
    from harness.report import _kill_eligible

    assert _kill_eligible({"type": "kraken", "config": {}}) is True
    assert _kill_eligible({"type": "calamari", "config": {}}) is True
    assert _kill_eligible({"type": "vlm_openai", "config": {}}) is False
    assert (
        _kill_eligible({"type": "vlm_openai", "config": {"kill_eligible": True}})
        is True
    )


def test_run_meta_preserved_on_resume(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    engine = FlakyEngine()
    write_run_meta(run_dir, {"flaky": engine}, {"images_dir": "x"})
    original = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))

    write_run_meta(run_dir, {"dying": DyingEngine()}, {"images_dir": "x"})
    merged = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert merged["created"] == original["created"]
    assert merged["git_commit"] == original["git_commit"]
    assert set(merged["engines"]) == {"flaky", "dying"}
    assert len(merged["resumed"]) == 1


def test_run_meta_refuses_changed_inputs_on_resume(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    original_extra = {
        "images_dir": "/tmp/images-a",
        "selection_sha256": "sel-a",
        "freeze_sha256": "freeze-a",
    }
    changed_extra = {**original_extra, "images_dir": "/tmp/images-b"}

    write_run_meta(
        run_dir, {"eng": ConfigurableEngine("eng", {"model": "a"})}, original_extra
    )

    conflicts = run_meta_conflicts(run_dir, changed_extra)
    assert any("images_dir" in conflict for conflict in conflicts)
    with pytest.raises(ValueError, match="images_dir"):
        write_run_meta(
            run_dir, {"new": ConfigurableEngine("new", {"model": "b"})}, changed_extra
        )

    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert "new" not in meta["engines"]
