"""What the adapters that read images with Pillow share: an image as it looks on white paper
(PDFium's page images, OCRmyPDF's input), and the size of the page an image makes (OCRmyPDF's
input, the PDF pages of an edit)."""

from PIL import Image

A4_LONG_EDGE = 11.69  # inches
PLAUSIBLE_PAGE = (3.0, 17.0)  # long edge in inches: from a receipt to A3

# Modes with an alpha channel, straight or premultiplied (`RGBa`, `La`).
_ALPHA = ("RGBA", "LA", "PA", "RGBa", "La")


def flatten_on_white(image: Image.Image) -> Image.Image:
    """`image` on white: one with transparency (an alpha channel, or a palette with a
    transparent colour) becomes an RGB copy on white; any other is returned as it is."""
    if image.mode == "P" and "transparency" in image.info:
        image = image.convert("RGBA")
    if image.mode not in _ALPHA:
        return image
    if image.mode == "La":
        image = image.convert("LA")  # Pillow converts premultiplied grey to nothing else
    rgba = image.convert("RGBA")
    white = Image.new("RGB", rgba.size, "white")
    white.paste(rgba, mask=rgba.getchannel("A"))
    return white


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
