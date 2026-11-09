"""Every document, or those a filter matches, a page at a time: for work over all documents
without holding them in memory at once or one transaction open."""

from collections.abc import AsyncIterator

from lekto.core.domain.documents import Document
from lekto.core.domain.ids import UserId
from lekto.core.ports.repository import DocumentFilter, DocumentPosition
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

PAGE = 500
"""Documents read in one transaction."""


async def document_pages(
    uow: UnitOfWorkFactory, filter: DocumentFilter | None = None, *, size: int = PAGE
) -> AsyncIterator[list[Document]]:
    """The documents `filter` matches (all without one), newest first, `size` at a time; each
    page is read in a transaction of its own."""
    after: DocumentPosition | None = None
    while True:
        async with uow() as unit:
            page = await unit.documents.query(filter or DocumentFilter(), after=after, limit=size)
        if page:
            yield page
        if len(page) < size:
            return
        after = DocumentPosition.after(page[-1].id)


async def documents_in(
    uow: UnitOfWork,
    filter: DocumentFilter,
    *,
    visible_to: UserId | None = None,
    size: int = PAGE,
) -> list[Document]:
    """Every document `filter` matches (of those `visible_to` may read; None: all), read a page
    at a time within the open unit of work `uow`, newest first."""
    found: list[Document] = []
    after: DocumentPosition | None = None
    while True:
        if visible_to is None:
            page = await uow.documents.query(filter, after=after, limit=size)
        else:
            page = await uow.documents.query_visible(visible_to, filter, after=after, limit=size)
        found += page
        if len(page) < size:
            return found
        after = DocumentPosition.after(page[-1].id)
