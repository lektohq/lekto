"""Making PDFs of the pages of files: what editing a document's pages writes
(`domain.editing`)."""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lekto.core.domain.editing import PagePick


@dataclass(frozen=True)
class PageSource:
    """A file whose pages are picked: a PDF, or an image (`media_types`: JPEG, PNG, TIFF)."""

    path: Path
    media_type: str


class PageComposer(Protocol):
    """Counts the pages of PDFs and images and puts pages of them together as a new PDF.
    First adapter: pikepdf and Pillow.

    A PDF's pages are taken over as they are, without rendering them again; an image's become
    pages of their own, the right way up as its EXIF orientation says, sized by its resolution
    as for OCR. Work runs outside the event loop (adapters use a thread)."""

    async def count_pages(self, source: PageSource) -> int:
        """The pages of `source`: a PDF's, an image's frames. UnprocessableDocumentError if it
        cannot be read (damaged, encrypted, of no supported kind)."""
        ...

    async def compose(
        self, sources: Sequence[PageSource], pages: Sequence[PagePick], target: Path
    ) -> None:
        """Write a PDF of `pages` in their order to `target`: page `page` of `sources[source]`,
        turned `rotate` degrees clockwise beyond its own rotation. The PDF is new every time,
        so two of the same pages are two files. UnprocessableDocumentError if a source cannot
        be read; ValueError for a page it does not have."""
        ...
