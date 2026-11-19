"""The PDFium library is not thread-safe, not even for different documents: every use in this
process goes through `LOCK`. What reads the pages of a PDF runs in a child (`child`); in the
worker itself it only counts pages."""

import threading
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pypdfium2
import pypdfium2.raw as pdfium_c

from lekto.adapters.outbound.pdfium.child import DEFAULT_TIMEOUT, run_child
from lekto.core.domain.errors import UnprocessableDocumentError
from lekto.core.domain.reasons import ReasonCode, because

LOCK = threading.Lock()
MODULE = "lekto.adapters.outbound.pdfium"
"""The module a child runs (`__main__`)."""


def count_pages(path: Path) -> int:
    """Pages of a PDF (blocking; run it in a thread)."""
    with LOCK:
        try:
            document = pypdfium2.PdfDocument(path)
        except pypdfium2.PdfiumError as error:
            raise UnprocessableDocumentError(
                because(ReasonCode.PDF_UNREADABLE_DETAIL, detail=str(error))
            ) from None
        try:
            return len(document)
        finally:
            document.close()


# A page's text cannot be read when this share of its characters (whitespace aside) maps to
# nothing: control characters, private use, unassigned code points, the replacement character.
UNREADABLE_SHARE = 0.3
_UNMAPPED = frozenset({"Cc", "Co", "Cn", "Cs"})


def unreadable_share(text: str) -> float:
    """The share of the characters of `text` (whitespace aside) that map to nothing; 0 without
    any."""
    characters = [char for char in text if not char.isspace()]
    if not characters:
        return 0.0
    unmapped = sum(
        char == "\ufffd" or unicodedata.category(char) in _UNMAPPED for char in characters
    )
    return unmapped / len(characters)


def has_unreadable_text(path: Path) -> bool:
    """Whether a page of the PDF has text that cannot be read (`UNREADABLE_SHARE`): a font
    without a character map (`/ToUnicode`), as some PDF printers write them, gives its codes,
    which come out as control characters (blocking). False for a PDF, or a page of it, that
    cannot be read: OCRmyPDF says why."""
    with LOCK:
        try:
            document = pypdfium2.PdfDocument(path)
        except pypdfium2.PdfiumError:
            return False
        try:
            return any(
                unreadable_share(page.get_textpage().get_text_range()) >= UNREADABLE_SHARE
                for page in document
            )
        except pypdfium2.PdfiumError:
            return False
        finally:
            document.close()


def has_hidden_text(path: Path) -> bool:
    """Whether a page of the PDF has invisible text, the layer an OCR puts over a scan
    (blocking). False for a PDF, or a page of it, that cannot be read: OCRmyPDF says why."""
    with LOCK:
        try:
            document = pypdfium2.PdfDocument(path)
        except pypdfium2.PdfiumError:
            return False
        try:
            for page in document:
                textpage = page.get_textpage()
                for index in range(textpage.count_chars()):
                    found = pdfium_c.FPDFText_GetTextObject(textpage, index)
                    mode = pdfium_c.FPDFTextObj_GetTextRenderMode(found) if found else None
                    if mode == pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE:
                        return True
            return False
        except pypdfium2.PdfiumError:
            return False
        finally:
            document.close()


@dataclass(frozen=True)
class TextLayer:
    """What the text layer of a PDF needs from the OCR: `unreadable`, a page's text cannot be
    read (`has_unreadable_text`); `hidden`, it has invisible text (`has_hidden_text`), only
    looked for when its text can be read."""

    unreadable: bool
    hidden: bool


def read_text_layer(path: Path) -> TextLayer:
    """The text layer of the PDF at `path`, in this process: what the child of `text_layer`
    does."""
    unreadable = has_unreadable_text(path)
    return TextLayer(unreadable=unreadable, hidden=not unreadable and has_hidden_text(path))


async def text_layer(
    path: Path, *, timeout: timedelta = DEFAULT_TIMEOUT, memory: int | None = None
) -> TextLayer:
    """The text layer of the PDF at `path`, read in a child (`child.run_child`)."""
    answer = await run_child(MODULE, "text-layer", [str(path)], timeout=timeout, memory=memory)
    if not isinstance(answer, dict):
        raise RuntimeError("text-layer gave no usable answer")
    return TextLayer(
        unreadable=answer.get("unreadable") is True, hidden=answer.get("hidden") is True
    )
