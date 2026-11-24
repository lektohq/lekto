"""An image on white: what PDFium's page images and OCRmyPDF's input share."""

from pathlib import Path

import pytest
from PIL import Image

from lekto.adapters.outbound.imaging import check_pixels, flatten_on_white, in_plain_mode
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


@pytest.mark.parametrize(
    ("mode", "values", "grey"),
    [
        # A scanner's grey of 16 bits: black, a dark, a middle and a light grey, white.
        ("I;16", [0, 5140, 32896, 51400, 65535], [0, 20, 128, 200, 255]),
        ("I;16B", [0, 5140, 32896, 51400, 65535], [0, 20, 128, 200, 255]),
        # Integers of 16 bits in 32, as an older Pillow opened such a scan.
        ("I", [0, 5140, 32896, 51400, 65535], [0, 20, 128, 200, 255]),
        # Integers and floats of eight bits stay as they are, floats of 0 to 1 are scaled.
        ("I", [0, 20, 128, 200, 255], [0, 20, 128, 200, 255]),
        ("F", [0.0, 20.0, 128.0, 200.0, 255.0], [0, 20, 128, 200, 255]),
        ("F", [0.0, 0.25, 0.5, 0.75, 1.0], [0, 63, 127, 191, 255]),
    ],
)
def test_grey_of_more_than_eight_bits_keeps_its_tones(
    mode: str, values: list[float], grey: list[int]
) -> None:
    """Not cut off at 255: a scan of 16 bits stays a scan, not a white page."""
    image = Image.new(mode, (len(values), 1))
    for x, value in enumerate(values):
        image.putpixel((x, 0), value)
    plain = in_plain_mode(image)
    assert plain.mode == "L"
    assert [plain.getpixel((x, 0)) for x in range(len(values))] == grey
