"""What the adapters that read images with Pillow share: an image as it looks on white paper
(PDFium's page images, OCRmyPDF's input), and the size of the page an image makes (OCRmyPDF's
input, the PDF pages of an edit)."""

from PIL import Image

from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.images import MAX_DOCUMENT_PIXELS

A4_LONG_EDGE = 11.69  # inches
PLAUSIBLE_PAGE = (3.0, 17.0)  # long edge in inches: from a receipt to A3

# Modes with an alpha channel, straight or premultiplied (`RGBa`, `La`).
_ALPHA = ("RGBA", "LA", "PA", "RGBa", "La")


def check_pixels(image: Image.Image) -> None:
    """UnprocessableDocumentError unless `image` (a frame of it) has at most
    `MAX_DOCUMENT_PIXELS`: on what Pillow read of its header, before anything is decoded."""
    width, height = image.size
    if width * height > MAX_DOCUMENT_PIXELS:
        raise UnprocessableDocumentError(
            because(
                ReasonCode.IMAGE_TOO_LARGE,
                pixels=-(-width * height // 1_000_000),  # rounded up: never "120 of 120"
                max=MAX_DOCUMENT_PIXELS // 1_000_000,
            )
        )


def flatten_on_white(image: Image.Image) -> Image.Image:
    """`image` on white: one with transparency (an alpha channel, or a palette with a
    transparent colour) becomes an RGB copy on white; any other is returned as it is."""
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode not in _ALPHA:
        return image
    if image.mode == "La":
        image = image.convert("LA")  # Pillow converts premultiplied grey to nothing else
    rgba = image if image.mode == "RGBA" else image.convert("RGBA")  # no copy of a large one
    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgba, mask=rgba.getchannel("A"))
    return white


def in_plain_mode(image: Image.Image, *, palette: bool = False) -> Image.Image:
    """`image` as one bit, grey or RGB, and with `palette` also as a palette: itself if it is in
    one of them, an image of integers or floats as grey, any other (CMYK, YCbCr, LAB, HSV, and a
    palette without `palette`) as RGB. A PDF page holds the first three; OCRmyPDF takes a
    palette too."""
    if image.mode in ("1", "L", "RGB") or (palette and image.mode == "P"):
        return image
    if image.mode.startswith(("I", "F")):
        return image.convert("L")
    return image.convert("RGB")


def image_dpi(size: tuple[int, int], stated: object) -> int:
    """The resolution for an image of `size` pixels that states `stated` (Pillow's `dpi`): the
    stated one if it gives a page within `PLAUSIBLE_PAGE`, else the one that makes its long edge
    that of A4. Photos often state none, or 72 dpi, which gives pages of several feet."""
    long_edge = max(size)
    if isinstance(stated, tuple) and stated:
        resolution = min(float(value) for value in stated)
        if resolution > 0 and PLAUSIBLE_PAGE[0] <= long_edge / resolution <= PLAUSIBLE_PAGE[1]:
            return max(1, round(resolution))
    return max(1, round(long_edge / A4_LONG_EDGE))
