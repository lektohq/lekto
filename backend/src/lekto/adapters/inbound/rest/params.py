"""Query parameters that routes share: the filter of documents (`GET /documents`,
`POST /documents/search`), the switches to every user's documents and rules (`all_users`), and
document counts; and how their descriptions say who may call them."""

from dataclasses import replace
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from fastapi.exceptions import RequestValidationError

from lekto.adapters.inbound.lanes import LANES, LaneFilter
from lekto.adapters.inbound.limits import MAX_SELECTED
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.schemas.refs import opened
from lekto.core.domain.document_facts import FactCriterion, FactRole
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.identifiers import IdentifierKind
from lekto.core.domain.ids import ContactId, DocumentTypeId, FieldId, SpaceId, TagId, id_reference
from lekto.core.domain.lenses import MAX_FILTER_FACTS, MAX_FILTER_VALUES
from lekto.core.domain.periods import Period
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.identity import RefCipher
from lekto.core.ports.repository import DocumentFilter

ADMINS_ONLY = "Admins only."
SESSION_ONLY_NOTE = " Needs a session; API tokens are refused (403)."

MAX_IDS = MAX_FILTER_VALUES
"""Ids of one kind a filter names at most: as many as a lens holds."""
MAX_FACTS = MAX_FILTER_FACTS
"""Facts a filter names at most: as many as a lens holds."""


type Ids = Annotated[list[UUID] | None, Query(max_length=MAX_IDS)]


def document_filter(
    contact_id: Ids = None,
    document_type_id: Ids = None,
    tag_id: Ids = None,
    space_id: Ids = None,
    lane: Annotated[list[LaneFilter] | None, Query(max_length=len(LaneFilter))] = None,
    field_id: UUID | None = None,
    contact_group_id: Ids = None,
    document_type_group_id: Ids = None,
    topic_id: Ids = None,
    document_date_from: date | None = None,
    document_date_to: date | None = None,
    fact: Annotated[
        list[str] | None,
        Query(
            max_length=MAX_FACTS,
            description=(
                "A fact the document has (none a person rejected), as `kind:ref:role`: the "
                "value by its reference (`ref`, from `POST /identifiers/refs` or an answer that "
                "names the value; it needs its kind), never as written, so it stays out of "
                "logs and histories; any part empty for any (`invoice_number:<ref>:`, "
                "`contract_number::`, `::refers`). Several: all of them. A person's facts (the "
                "kinds that are a person's alone, the role `person`) only for admins (403); 422 "
                "for one that is none or a reference that names no value of the kind."
            ),
        ),
    ] = None,
    *,
    context: Context,
) -> DocumentFilter:
    """The query parameters of the document list as a filter (the search takes the same).
    Several contacts, types, spaces, contact groups, type groups or topics: one of them (each
    kind one set). Each tag is a set of its own: all of them. The service adds the tags below
    them. `document_date_from`, `document_date_to`: the document date lies between them, both
    days included (either end may stay open)."""

    chosen = DocumentFilter.chosen(
        contacts=(ContactId(id) for id in contact_id or ()),
        document_types=(DocumentTypeId(id) for id in document_type_id or ()),
        tags=(TagId(id) for id in tag_id or ()),
        contact_groups=(TagId(id) for id in contact_group_id or ()),
        document_type_groups=(TagId(id) for id in document_type_group_id or ()),
        topics=(TagId(id) for id in topic_id or ()),
        spaces=(SpaceId(id) for id in space_id or ()),
        field=None if field_id is None else FieldId(field_id),
        document_dates=_dates(document_date_from, document_date_to),
        facts=(_fact(item, context.refs) for item in dict.fromkeys(fact or ())),
    )
    return replace(chosen, lanes=frozenset(LANES[item] for item in lane) if lane else None)


def _fact(written: str, refs: RefCipher) -> FactCriterion:
    """A fact of the filter as `kind:ref:role`, the value by its reference (base64url, no
    colon). 422 with the reason for one that is none."""
    parts = [part.strip() for part in written.split(":")]
    if len(parts) != 3:
        raise ValidationError(because(ReasonCode.FACT_CRITERION_EMPTY))
    kind, ref, role = parts
    if kind and kind not in IdentifierKind:
        raise ValidationError(because(ReasonCode.FACT_KIND_UNKNOWN, kind=kind))
    if role and role not in FactRole:
        raise ValidationError(because(ReasonCode.FACT_KIND_UNKNOWN, kind=role))
    if ref and not kind:
        raise ValidationError(because(ReasonCode.FACT_CRITERION_EMPTY))
    return FactCriterion.written(
        IdentifierKind(kind) if kind else None,
        opened(refs, IdentifierKind(kind), ref) if ref else None,
        FactRole(role) if role else None,
    )


def _dates(start: date | None, end: date | None) -> Period | None:
    """The period of the document dates; an end before the start is a 422 at its place."""
    if start is not None and end is not None and end < start:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "document_date_to"),
                    "msg": "the end of the period lies before its start",
                    "input": end.isoformat(),
                }
            ]
        )
    return Period.between(start, end)


Filter = Annotated[DocumentFilter, Depends(document_filter)]


def listed_filter(
    filter: Filter,
    ids: Annotated[
        list[str] | None,
        Query(
            max_length=MAX_SELECTED,
            description=(
                "Documents by id: the whole id, or its end of at least 8 characters (a short "
                "id, as MCP names documents; an end several documents share finds each). "
                "Several: any of them. The list, its count, its facets and an action on many "
                "take it; the search does not (the search index knows no ids)."
            ),
        ),
    ] = None,
) -> DocumentFilter:
    """The filter of the list (`document_filter`) with the documents it names by id."""
    if not ids:
        return filter
    references = {id_reference(item) for item in ids}
    if None in references:
        raise RequestValidationError(
            [
                {
                    "type": "value_error",
                    "loc": ("query", "ids"),
                    "msg": "an id is the whole id or its end of at least 8 hex characters",
                    "input": next(item for item in ids if id_reference(item) is None),
                }
            ]
        )
    return replace(filter, ids=frozenset(item for item in references if item is not None))


Listed = Annotated[DocumentFilter, Depends(listed_filter)]
InInbox = Annotated[
    bool | None,
    Query(
        description=(
            "Only the documents that stand open in the caller's inbox (true) or those that do "
            "not (false), as `in_inbox` marks them and `GET /inbox/summary` counts them: in "
            "processing, to review, to intervene, or new and not seen by the caller since; in "
            "the spaces the caller edits, with `all_users` in every user's inbox (with the "
            "caller's own seen). The list, its count and its facets take it; an action on many "
            "and the search do not."
        )
    ),
]
AllDocuments = Annotated[
    bool, Query(description="Every user's documents instead of the caller's reach (admins).")
]
CountAll = Annotated[
    bool, Query(description="Count every user's documents instead of the caller's reach (admins).")
]
AllInboxes = Annotated[
    bool,
    Query(
        description="Every user's inbox instead of the caller's, with the caller's seen (admins)."
    ),
]
AllRules = Annotated[
    bool, Query(description="The rules of every space instead of the caller's (admins).")
]
AllSpaces = Annotated[bool, Query(description="Every space instead of the caller's (admins).")]
DocumentCounts = Annotated[
    bool, Query(description="Count the documents of each (`document_count`).")
]
