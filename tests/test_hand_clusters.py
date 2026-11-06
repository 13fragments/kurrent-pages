from pathlib import Path

from harness.gold import GoldPage, load_selection
from harness.report import _hand_cluster_sensitivity


def _page(gid: str, *, source: str, hand: str, hand_cluster: str = "") -> GoldPage:
    return GoldPage(
        id=gid,
        image_name=f"{gid}.jpg",
        strata=("suetterlin",),
        scored=True,
        source=source,
        hand=hand,
        hand_cluster=hand_cluster,
    )


def _complete_score(*, fabricated: bool) -> dict:
    return {"adjudication_status": "complete", "fab_page": fabricated}


def test_default_hand_clusters_are_source_qualified_and_explicit_ids_cross_sources():
    pages = [
        _page("G01", source="archive_a", hand="same hand"),
        _page("G02", source="archive_b", hand="same hand"),
        _page("G03", source="archive_a", hand="Writer", hand_cluster="known_writer"),
        _page(
            "G04", source="archive_b", hand="Writer later", hand_cluster="known_writer"
        ),
    ]
    scores = {
        "G01": _complete_score(fabricated=True),
        "G02": _complete_score(fabricated=False),
        "G03": _complete_score(fabricated=True),
        "G04": _complete_score(fabricated=False),
    }
    sensitivity = _hand_cluster_sensitivity(scores, pages)
    assert sensitivity["clusters"] == 3
    assert sensitivity["affected_clusters"] == 2


def test_selection_declares_known_cross_page_hand_clusters():
    pages = {
        page.id: page
        for page in load_selection(Path(__file__).parents[1] / "gold/selection.yml")
    }
    groups = [
        ("G08", "G09", "G52a", "G52b"),
        ("G14", "G15", "G16"),
        ("G17", "G18"),
        ("G19", "G21"),
        ("G27", "G43", "G44"),
        ("G33", "G34"),
        ("G35", "G36", "G51"),
        ("G41", "G42"),
    ]
    for group in groups:
        assert len({pages[gid].hand_cluster_id for gid in group}) == 1
    assert pages["G08"].source == "muenster_nl_daut_004"
