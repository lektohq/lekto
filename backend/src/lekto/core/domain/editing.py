"""Editing a document's pages (`.idea/umsetzungsplan.md`, "Fassungen, Datei ersetzen, PDF
bearbeiten"; `services.editing`): a person turns, reorders, removes and splits the pages of the
document's original, and adds the pages of files from their device. The pages make parts, each a
PDF of its own: at most one replaces the document as its next version (`VersionKind.EDITED`),
every other becomes a new document in its space (`VersionKind.SPLIT`). Without a part that
replaces it, the document is deleted once the new ones are there.

Pages of other documents make a merge ("Trennblatt und Zusammenführen"): one of the documents is
the target, the part that replaces it its next version (`VersionKind.MERGED`); the others are
deleted, their versions go to the target. A merge needs that part (Tobi, 11.11.2026): without
it, every document would go, their originals with them.

A page is picked from a source: `ORIGINAL`, the document's current original, an added file
(1, 2, … in the order they were given), then the other documents' originals in theirs. Each
page of a source goes into one part at most; a page left out is removed. An image's pages are
its frames (a TIFF may have several); every part is a PDF."""

from collections.abc import Sequence
from dataclasses import dataclass

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.json_value import JsonObject

ORIGINAL = 0
"""The source of a page from the document's own original; added files count from 1."""
ROTATIONS = (0, 90, 180, 270)
"""How far a page may be turned, clockwise, from how it is shown."""
MAX_ADDED = 20
"""Files one edit adds at most."""
MAX_MERGED = 20
"""Other documents one edit takes the pages of at most."""


@dataclass(frozen=True)
class PagePick:
    """Page `page` (from 1) of the source `source`, turned `rotate` degrees clockwise from how
    it is shown (the page's own rotation stays and adds up)."""

    source: int
    page: int
    rotate: int = 0

    def __post_init__(self) -> None:
        if self.source < ORIGINAL or self.page < 1:
            raise ValidationError("pages: a source from 0 and a page from 1")
        if self.rotate not in ROTATIONS:
            raise ValidationError("pages: rotate is 0, 90, 180 or 270")

    def to_json(self) -> JsonObject:
        return {"source": self.source, "page": self.page, "rotate": self.rotate}


@dataclass(frozen=True)
class EditPart:
    """The pages of one part in their order; `replaces`: it becomes the document's next
    version, else a new document."""

    pages: tuple[PagePick, ...]
    replaces: bool = False

    def __post_init__(self) -> None:
        if not self.pages:
            raise ValidationError("parts: every part has pages")


def check_parts(parts: Sequence[EditPart], counts: Sequence[int], *, merging: bool = False) -> None:
    """ValidationError unless `parts` edit sources of `counts` pages each (the original first):
    at least one part, at most one that replaces the document (in a merge, exactly one), every
    page one its source has and in one place only, and a change: the one part that replaces the
    document with the original's pages in their order, unturned, changes nothing (a merge
    always changes, its other documents go)."""
    if not parts:
        raise ValidationError("parts: at least one")
    replacing = sum(part.replaces for part in parts)
    if replacing > 1:
        raise ValidationError("parts: at most one replaces the document")
    if merging and replacing == 0:
        raise ValidationError("parts: one continues the target when documents are merged")
    seen: set[tuple[int, int]] = set()
    for part in parts:
        for pick in part.pages:
            if pick.source >= len(counts):
                raise ValidationError(f"pages: there is no source {pick.source}")
            if pick.page > counts[pick.source]:
                raise ValidationError(
                    f"pages: source {pick.source} has {counts[pick.source]} pages, not {pick.page}"
                )
            if (pick.source, pick.page) in seen:
                raise ValidationError(f"pages: page {pick.page} of source {pick.source} twice")
            seen.add((pick.source, pick.page))
    unchanged = tuple(PagePick(ORIGINAL, number) for number in range(1, counts[ORIGINAL] + 1))
    if not merging and len(parts) == 1 and parts[0].replaces and parts[0].pages == unchanged:
        raise ValidationError("parts: nothing changed")
