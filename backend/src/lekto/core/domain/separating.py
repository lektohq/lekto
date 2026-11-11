"""Separator sheets (`.idea/umsetzungsplan.md`, "Trennblatt und Zusammenführen";
`services.separating`): a scanned stack holds several documents, each after a sheet with a code
that says "a new one starts here". When the stack comes in, it is split at those sheets, and the
sheets are left out.

A sheet is a page with a code whose whole text is one of the separator codes, in any case
(`PATCHT` by default, as Paperless prints it). Pages between two sheets make a part; no part is
empty (two sheets in a row, one at the start or end).
"""

from collections.abc import Collection, Iterable


def is_separator(text: str, separators: Collection[str]) -> bool:
    """Whether a code's whole `text` is one of the separator codes, in any case."""
    return text.casefold() in {separator.casefold() for separator in separators}


def separator_pages(codes: Iterable[tuple[int, str]], separators: Collection[str]) -> list[int]:
    """The pages (from 1, in order) that carry a separator code, of `codes` (page, text)."""
    return sorted({page for page, text in codes if is_separator(text, separators)})


def separated_parts(pages: int, sheets: Collection[int]) -> list[tuple[int, ...]]:
    """The pages of each part of a stack of `pages` pages split at the pages `sheets`, which are
    left out; none where every page is a sheet."""
    parts: list[tuple[int, ...]] = []
    current: list[int] = []
    for page in range(1, pages + 1):
        if page in sheets:
            if current:
                parts.append(tuple(current))
            current = []
        else:
            current.append(page)
    if current:
        parts.append(tuple(current))
    return parts
