"""What the tests of the facts at the contacts share (`open_identifiers`, `holder_evaluation`):
a fact a pattern found, and where a document showed it."""

from datetime import date

from lekto.core.domain.document_facts import DocumentFact, FactOrigin, Holder, role_of
from lekto.core.domain.identifiers import IdentifierKind
from lekto.core.domain.ids import ContactId, DocumentId, UserId, new_id
from lekto.core.domain.open_identifiers import Sighting


def fact(
    key: tuple[IdentifierKind, str], written: str | None = None, holder: Holder | None = None
) -> DocumentFact:
    kind, value = key
    return DocumentFact(
        kind=kind,
        value=value,
        role=role_of(kind),
        origins=frozenset({FactOrigin.PATTERN}),
        written=written,
        position=0,
        holder=holder,
    )


def seen(
    contact: ContactId,
    key: tuple[IdentifierKind, str],
    day: int,
    *,
    written: str | None = None,
    holder: Holder | None = None,
    owner: UserId | None = None,
) -> Sighting:
    """`key` in a document of `contact` on that day of October 2026."""
    return Sighting(
        DocumentId(new_id()), contact, date(2026, 10, day), fact(key, written, holder), owner
    )
