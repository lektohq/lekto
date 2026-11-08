"""Page images with PDFium (PDFs) and Pillow (images). Rendering a page takes milliseconds to
a fraction of a second, so it runs in a thread, under the process-wide PDFium lock."""

import asyncio
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import PIL
import pypdfium2
from PIL import Image, ImageOps, ImageSequence

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
                pages = _image_pages(source)
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
                    bitmap = page.render(scale=page_scale(*page.get_size(), width))
                    image: Image.Image = bitmap.to_pil().convert("RGB")
                finally:
                    page.close()
            yield image

    try:
        yield pages()
    finally:
        with LOCK:
            document.close()


@contextmanager
def _image_pages(source: Path) -> Iterator[Iterator[Image.Image]]:
    """The frames of an image (a TIFF may have several), the right way up, on white."""
    try:
        opened = Image.open(source)
    except (OSError, Image.DecompressionBombError) as error:
        raise UnprocessableDocumentError(
            because(ReasonCode.IMAGE_UNREADABLE_DETAIL, detail=str(error))
        ) from None

    def frames() -> Iterator[Image.Image]:
        try:
            for frame in ImageSequence.Iterator(opened):
                upright = ImageOps.exif_transpose(frame) or frame
                yield flatten_on_white(upright).convert("RGB")
        except OSError as error:
            raise UnprocessableDocumentError(
                because(ReasonCode.IMAGE_UNREADABLE_DETAIL, detail=str(error))
            ) from None

    try:
        yield frames()
    finally:
        opened.close()


def _fit(image: Image.Image, width: int) -> Image.Image:
    if image.width <= width:
        return image
    return image.resize((width, max(1, round(image.height * width / image.width))))


def _save(image: Image.Image, target: Path) -> None:
    image.save(target, "WEBP", quality=_QUALITY)
