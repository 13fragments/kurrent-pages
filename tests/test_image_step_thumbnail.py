"""Image step `thumbnail_2048_png` (§10 2026-11-19): the LightOnOCR-3-4B card client at b71010f0,
`pil_image.thumbnail((2048, 2048))` then PNG. Failure modes: a small page is enlarged; the aspect ratio changes;
the page is not sent as RGB PNG; the step does not mirror Pillow's thumbnail (size off by rounding)."""

import io

from PIL import Image

from harness.engines.image_steps import check_step, prepared


def _page(tmp_path, size, mode="RGB"):
    path = tmp_path / "page.jpg"
    Image.new(mode, size, 128).convert("RGB").save(path, quality=90)
    return path


def test_large_page_is_reduced_like_pillow_thumbnail(tmp_path):
    path = _page(tmp_path, (3579, 4699))
    data, mime, record = prepared(path, "thumbnail_2048_png")
    expected = Image.open(path).convert("RGB")
    expected.thumbnail((2048, 2048))
    sent = Image.open(io.BytesIO(data))
    assert mime == "png" and sent.format == "PNG" and sent.mode == "RGB"
    assert sent.size == expected.size and max(sent.size) == 2048
    assert record["step"] == "thumbnail_2048_png" and record["resized"] is True


def test_small_page_is_not_enlarged(tmp_path):
    data, _mime, record = prepared(_page(tmp_path, (800, 600)), "thumbnail_2048_png")
    assert Image.open(io.BytesIO(data)).size == (800, 600)
    assert record["resized"] is False


def test_step_is_known():
    check_step("e", "thumbnail_2048_png")
