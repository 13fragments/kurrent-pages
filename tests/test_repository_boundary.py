from scripts.check_boundary import violations


def test_repository_boundary() -> None:
    assert violations() == []

