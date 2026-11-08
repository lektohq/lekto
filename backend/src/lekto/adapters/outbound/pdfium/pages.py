"""Page images with PDFium (PDFs) and Pillow (images). Rendering a page takes milliseconds to
a fraction of a second, so it runs in a thread, under the process-wide PDFium lock."""

import asyncio
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import PIL
import pypdfium2
from PIL import ExifTags, Image, ImageSequence

from lekto.adapters.outbound.imaging import flatten_on_white
from lekto.adapters.outbound.pdfium.library import LOCK
from lekto.core.domain import media_types
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.pages import PREVIEW_FILE, RenderedPages

DEFAULT_WIDTH = 1200
DEFAULT_PREVIEW_WIDTH = 400
_QUALITY = 80
PIXELS_PER_POINT = 2
"""How fine a page is rendered at most: enough for the page width of an A4 page."""
MAX_EDGE = 10_000
"""Pixels of a page image's long edge at most: a page eight times as high as wide keeps the
full width, and a page of any size a PDF may give (14 400 points a side) renders within about
50 MB. Rendered at a fixed scale, such a page of a file of 553 bytes asked for 3.3 GB."""


class PdfiumPageRenderer:
    """Pages `width` pixels wide (an image narrower than that keeps its size), the preview
    `preview_width` wide."""

    def __init__(
        self, *, width: int = DEFAULT_WIDTH, preview_width: int = DEFAULT_PREVIEW_WIDTH
    ) -> None:
        self._width = width
        self._preview_width = preview_width

    async def render_pages(self, source: Path, *, media_type: str, target: Path) -> RenderedPages:
        return await asyncio.to_thread(self._render, source, media_type, target)

    def _render(self, source: Path, media_type: str, target: Path) -> RenderedPages:
        # Everything goes to a scratch directory first, so `target` stays empty on an error.
        scratch = target / ".rendering"
        scratch.mkdir()
        try:
            if media_type == media_types.PDF:
                pages = _pdf_pages(source, self._width)
                renderer = f"pdfium {pypdfium2.PDFIUM_INFO.build}"
            else:
                pages = _image_pages(source, self._width)
                renderer = f"pillow {PIL.__version__}"
            count = 0
            with pages as images:
                for count, image in enumerate(images, start=1):
                    if count == 1:
                        _save(_fit(image, self._preview_width), scratch / PREVIEW_FILE)
                    _save(_fit(image, self._width), scratch / f"{count}.webp")
            if count == 0:
                raise UnprocessableDocumentError(because(ReasonCode.DOCUMENT_NO_PAGES))
            for file in scratch.iterdir():
                file.replace(target / file.name)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        return RenderedPages(pages=count, renderer=renderer)


def page_scale(width: float, height: float, target: int) -> float:
    """Pixels per point for a page `width` by `height` points: at most `PIXELS_PER_POINT`, no
    wider than `target` pixels, its long edge at most `MAX_EDGE`. From the page's size, which
    the file gives as it likes."""
    return min(PIXELS_PER_POINT, target / max(width, 1.0), MAX_EDGE / max(width, height, 1.0))


@contextmanager
def _pdf_pages(source: Path, width: int) -> Iterator[Iterator[Image.Image]]:
    """The pages of a PDF, rendered one at a time at `page_scale` for `width` pixels; the
    caller fits them (rendering rounds up)."""
    try:
        with LOCK:
            document = pypdfium2.PdfDocument(source)
            count = len(document)  # a library call too: under the lock
    except pypdfium2.PdfiumError as error:
        raise UnprocessableDocumentError(
            because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=str(error))
        ) from None

    def pages() -> Iterator[Image.Image]:
        for index in range(count):
            with LOCK:
                page = document[index]
                try:
                    across, high = page.get_size()
                    bitmap = page.render(scale=page_scale(across, high, width))
                    image: Image.Image = bitmap.to_pil().convert("RGB")
                finally:
                    page.close()
            yield image

    try:
        yield pages()
    finally:
        with LOCK:
            document.close()


# How each EXIF orientation turns an image the right way up (as `ImageOps.exif_transpose`).
_UPRIGHT = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}
_SIDEWAYS = (5, 6, 7, 8)  # orientations that swap width and height


@contextmanager
def _image_pages(source: Path, width: int) -> Iterator[Iterator[Image.Image]]:
    """The frames of an image (a TIFF may have several), the right way up, on white, at most
    `width` wide. Each is made small first and turned and laid on white then: a file of a few
    hundred kilobytes may hold a picture of 170 megapixels, of which every full-size copy took
    another 700 MB. A JPEG is decoded at the smallest scale that still gives `width`."""
    try:
        opened = Image.open(source)
    except (OSError, Image.DecompressionBombError) as error:
        raise UnprocessableDocumentError(
            because(ReasonCode.IMAGE_UNREADABLE_DETAIL, detail=str(error))
        ) from None

    def frames() -> Iterator[Image.Image]:
        try:
            for frame in ImageSequence.Iterator(opened):
                orientation = frame.getexif().get(ExifTags.Base.Orientation, 1)
                sideways = orientation in _SIDEWAYS
                if opened.format == "JPEG":
                    opened.draft(None, (1, width) if sideways else (width, 1))
                small = _shrunk(frame, width, sideways=sideways)
                if orientation in _UPRIGHT:
                    small = small.transpose(_UPRIGHT[orientation])
                yield flatten_on_white(small).convert("RGB")
        except OSError as error:
            raise UnprocessableDocumentError(
                because(ReasonCode.IMAGE_UNREADABLE_DETAIL, detail=str(error))
            ) from None

    try:
        yield frames()
    finally:
        opened.close()


def _shrunk(frame: Image.Image, width: int, *, sideways: bool) -> Image.Image:
    """`frame` no wider than `width` once upright (`sideways`: turned by a quarter). A palette
    or bilevel image is converted first, so that it is not shrunk by its palette's nearest
    colours."""
    if frame.mode == "P":
        frame = frame.convert("RGBA" if "transparency" in frame.info else "RGB")
    elif frame.mode == "1":
        frame = frame.convert("L")
    across = frame.height if sideways else frame.width
    if across <= width:
        return frame
    scale = width / across
    size = (max(1, round(frame.width * scale)), max(1, round(frame.height * scale)))
    return frame.resize(size, reducing_gap=3.0)


def _fit(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    return image.resize((width, max(1, round(image.height * width / image.width))))


def _save(image: Image.Image, target: Path) -> None:
    image.save(target, "WEBP", quality=_QUALITY)
