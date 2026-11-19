"""PDFium (pypdfium2): the text of the archive as it is set (the parser), page images (Pillow
reads images and encodes WebP) and the places of quotes in a PDF's text layer. What reads the
pages of a PDF runs in a child (`child`)."""

from lekto.adapters.outbound.pdfium.child import DEFAULT_TIMEOUT as PDF_TIMEOUT
from lekto.adapters.outbound.pdfium.layout import LayoutParser
from lekto.adapters.outbound.pdfium.library import (
    TextLayer,
    count_pages,
    has_hidden_text,
    has_unreadable_text,
    text_layer,
)
from lekto.adapters.outbound.pdfium.locator import PdfiumTextLocator
from lekto.adapters.outbound.pdfium.pages import PdfiumPageRenderer

__all__ = [
    "PDF_TIMEOUT",
    "LayoutParser",
    "PdfiumPageRenderer",
    "PdfiumTextLocator",
    "TextLayer",
    "count_pages",
    "has_hidden_text",
    "has_unreadable_text",
    "text_layer",
]
