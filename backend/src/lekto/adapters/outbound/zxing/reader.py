"""Bar codes, QR codes and other symbols with zxing-cpp, on the pages of a PDF rendered by
PDFium.

Each page is rendered in grey at `DPI` (small codes need it: a matrix code of a franking mark
has modules of a third of a millimetre), its long edge at most `MAX_EDGE` pixels, and zxing-cpp
reads every format it knows from it. A long document is read as far as `max_pages`, unless
every page is asked for (separator sheets). The PDF is read in a child
(`python -m lekto.adapters.outbound.zxing`, see `pdfium.child`). Rendering goes through the
PDFium lock; the copy of the pixels and decoding do not need it. A result zxing-cpp marks
invalid, or with no text, is left out; the same code twice on a page counts once.
"""

import importlib.metadata
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

import pypdfium2
import zxingcpp
from PIL import Image

from lekto.adapters.outbound.pdfium.child import DEFAULT_TIMEOUT, run_child
from lekto.adapters.outbound.pdfium.library import LOCK
from lekto.core.domain.codes import Code
from lekto.core.domain.errors import UnprocessableDocumentError, ValidationError
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.locations import Box
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.codes import CodeReader, CodeReading

DPI = 300
POINTS_PER_INCH = 72  # the unit of a PDF page's size
MAX_EDGE = 5000  # pixels: A4 at 300 dpi is 3508
MAX_PAGES = 50


MODULE = "lekto.adapters.outbound.zxing"
"""The module a child runs (`__main__`)."""


class ZxingCodeReader(CodeReader):
    """Reads the PDF in a child with `timeout` and `memory` (`pdfium.child.run_child`)."""

    def __init__(
        self,
        *,
        max_pages: int = MAX_PAGES,
        timeout: timedelta = DEFAULT_TIMEOUT,
        memory: int | None = None,
    ) -> None:
        self._max_pages = max_pages
        self._timeout = timeout
        self._memory = memory

    async def read_codes(self, source: Path, *, every_page: bool = False) -> CodeReading:
        pages = "all" if every_page else str(self._max_pages)
        answer = await run_child(
            MODULE, "codes", [str(source), pages], timeout=self._timeout, memory=self._memory
        )
        try:
            if not (
                isinstance(answer, dict)
                and isinstance(codes := answer.get("codes"), list)
                and isinstance(reader := answer.get("reader"), str)
                and isinstance(read := answer.get("pages"), int)
            ):
                raise ValidationError("not a reading")
            return CodeReading(
                codes=tuple(Code.from_json(code) for code in codes), reader=reader, pages=read
            )
        except ValidationError:
            raise RuntimeError("codes gave no usable answer") from None


def codes_task(args: Sequence[str], _: JsonValue) -> JsonValue:
    """The child's task `codes PDF PAGES`: the codes on the first `PAGES` pages, or on all."""
    source, pages = args
    reading = read_codes(Path(source), max_pages=None if pages == "all" else int(pages))
    return {
        "codes": [code.to_json() for code in reading.codes],
        "reader": reading.reader,
        "pages": reading.pages,
    }


def read_codes(source: Path, *, max_pages: int | None) -> CodeReading:
    """The codes on the first `max_pages` pages of `source` (None: all), in this process
    (blocking)."""
    try:
        with LOCK:
            document = pypdfium2.PdfDocument(source)
            total = len(document)  # a library call too: under the lock
    except pypdfium2.PdfiumError as error:
        raise UnprocessableDocumentError(
            because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=str(error))
        ) from None
    codes: list[Code] = []
    try:
        pages = total if max_pages is None else min(total, max_pages)
        for index in range(pages):
            image = _render(document, index)
            codes.extend(_codes_of(image, index + 1))
    finally:
        with LOCK:
            document.close()
    name = (
        f"zxing-cpp {importlib.metadata.version('zxing-cpp')}, pdfium {pypdfium2.PDFIUM_INFO.build}"
    )
    return CodeReading(codes=tuple(codes), reader=name, pages=pages)


def _render(document: pypdfium2.PdfDocument, index: int) -> Image.Image:
    with LOCK:
        try:
            page = document[index]
        except pypdfium2.PdfiumError as error:
            raise UnprocessableDocumentError(
                because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=f"page {index + 1}: {error}")
            ) from None
        try:
            width, height = page.get_size()
            scale = min(DPI / POINTS_PER_INCH, MAX_EDGE / max(width, height, 1))
            bitmap = page.render(scale=scale, grayscale=True)
        except pypdfium2.PdfiumError as error:
            raise UnprocessableDocumentError(
                because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=f"page {index + 1}: {error}")
            ) from None
        finally:
            page.close()
    # The pixels lie in a buffer of our own (`PdfBitmap.new_native`), so the copy into a PIL
    # image (about 17 MB for a page at 300 dpi) needs no PDFium call: outside the lock, where it
    # does not hold up the other users of PDFium. Releasing the bitmap is one (AD-07).
    image: Image.Image = bitmap.to_pil().convert("L")
    with LOCK:
        bitmap.close()
    return image


def _codes_of(image: Image.Image, page: int) -> list[Code]:
    found: list[Code] = []
    seen: set[tuple[str, str]] = set()
    for barcode in zxingcpp.read_barcodes(image):
        if not barcode.valid or not barcode.text:
            continue
        format = str(barcode.format)
        if (format, barcode.text) in seen:
            continue
        seen.add((format, barcode.text))
        position = barcode.position
        corners = (
            position.top_left,
            position.top_right,
            position.bottom_right,
            position.bottom_left,
        )
        xs = [point.x / image.width for point in corners]
        ys = [point.y / image.height for point in corners]
        box = Box.clamped(min(xs), min(ys), max(xs), max(ys))
        found.append(Code(page=page, format=format, text=barcode.text, box=box))
    return found
