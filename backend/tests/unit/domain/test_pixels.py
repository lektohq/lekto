"""Width and height from an image's head, without decoding it (DB-09)."""

import io

import pytest
from PIL import Image

from lekto.core.domain.pixels import pixels


def image(kind: str, size: tuple[int, int], mode: str = "RGB", **options: object) -> bytes:
    buffer = io.BytesIO()
    color = (255, 255, 255, 0) if mode == "RGBA" else (255, 255, 255)  # see-through: VP8X
    Image.new(mode, size, color).save(buffer, kind, **options)
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("data", "size"),
    [
        (image("PNG", (640, 48)), (640, 48)),
        (image("GIF", (120, 300)), (120, 300)),
        (image("JPEG", (299, 1)), (299, 1)),
        (image("JPEG", (800, 600), progressive=True), (800, 600)),
        (image("JPEG", (50, 70), exif=b"Exif\x00\x00" + b"\x00" * 2000), (50, 70)),
        (image("WEBP", (333, 77), quality=50), (333, 77)),  # lossy: VP8
        (image("WEBP", (16_000, 3), lossless=True), (16_000, 3)),  # lossless: VP8L
        (image("WEBP", (90, 30), mode="RGBA", quality=50), (90, 30)),  # alpha: VP8X
    ],
)
def test_the_head_names_the_size(data: bytes, size: tuple[int, int]) -> None:
    assert pixels(data) == size


def test_another_kind_or_a_cut_head_says_nothing() -> None:
    whole = image("JPEG", (40, 40))
    for data in (b"%PDF-1.7", b"", whole[:4], image("PNG", (4, 4))[:20], b"\xff\xd8\xff\xda"):
        assert pixels(data) is None
