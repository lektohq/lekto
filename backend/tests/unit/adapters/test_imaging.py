"""An image on white: what PDFium's page images and OCRmyPDF's input share."""

from pathlib import Path

import pytest
from PIL import Image

from lekto.adapters.outbound.imaging import check_pixels, flatten_on_white
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode
from lekto.core.ports.images import MAX_DOCUMENT_PIXELS
from tests.images import stated_png

RED = (200, 0, 0)
GREY = 90


def transparent(mode: str) -> Image.Image:
    """Two pixels of `mode`: a transparent one, then an opaque red (grey without colour)."""
    match mode:
        case "P":
            image = Image.new("P", (2, 1))
            image.putpalette([0, 0, 0, *RED])
            image.putpixel((1, 0), 1)
            image.info["transparency"] = 0
        case "PA":
            image = Image.new("PA", (2, 1))
            image.putpalette([0, 0, 0, *RED])
            image.putpixel((0, 0), (1, 0))
            image.putpixel((1, 0), (1, 255))
        case "RGBA" | "RGBa":
            image = Image.new("RGBA", (2, 1))
            image.putpixel((0, 0), (*RED, 0))
            image.putpixel((1, 0), (*RED, 255))
        case "LA" | "La":
            image = Image.new("LA", (2, 1))
            image.putpixel((0, 0), (0, 0))
            image.putpixel((1, 0), (GREY, 255))
    return image if image.mode == mode else image.convert(mode)


@pytest.mark.parametrize("mode", ["P", "PA", "RGBA", "RGBa", "LA", "La"])
def test_transparency_turns_white(mode: str) -> None:
    image = transparent(mode)
    assert image.mode == mode
    flat = flatten_on_white(image)
    assert flat.mode == "RGB"
    opaque = (GREY, GREY, GREY) if mode in ("LA", "La") else RED
    assert [flat.getpixel((0, 0)), flat.getpixel((1, 0))] == [(255, 255, 255), opaque]


@pytest.mark.parametrize("mode", ["1", "L", "P", "RGB", "CMYK", "I;16", "F"])
def test_an_image_without_transparency_stays_as_it_is(mode: str) -> None:
    image = Image.new(mode, (2, 1))
    assert flatten_on_white(image) is image


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_an_image_over_the_limit_is_refused_from_its_header(tmp_path: Path) -> None:
    assert MAX_DOCUMENT_PIXELS == 120_000_000
    with Image.open(stated_png(tmp_path / "large.png", 10_000, 12_000)) as image:
        check_pixels(image)  # at the limit: read
    with (
        Image.open(stated_png(tmp_path / "larger.png", 10_000, 12_001)) as image,
        pytest.raises(UnprocessableDocumentError) as raised,
    ):
        check_pixels(image)
    assert raised.value.reason.code is ReasonCode.IMAGE_TOO_LARGE
    assert raised.value.reason.params == {"pixels": 121, "max": 120}
    assert str(raised.value) == (
        "the image has 121 megapixels; Lekto reads images of up to 120 megapixels"
    )
