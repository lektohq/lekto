"""Lenses: a user's saved looks at the documents (Tobi, 20.10.2026: "Lens" in German and English,
like "Space"; a space is where documents lie, a lens how one looks at them).

A lens holds the filters, the words of a search, the sort, the grouping, the layout, up to three
fields its cards show and the date field that is their deadline. It contains nothing: a document
stands in many lenses at once. Only its owner sees and changes it. Lenses are settings: no
events, no webhooks.

Master data a lens names may be deleted after; the services drop what is gone when they hand a
lens out, so a lens never fails for it.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Self

from lekto.core.domain.changes import UNSET, Unset, apply_changes
from lekto.core.domain.document_facts import FactCriterion
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import (
    ContactId,
    DocumentTypeId,
    FieldId,
    LensId,
    SpaceId,
    TagId,
    UserId,
    new_id,
)
from lekto.core.domain.periods import Period
from lekto.core.domain.validation import require_name, require_utc

MAX_NAME_LENGTH = 100
MAX_CARD_FIELDS = 3
MAX_QUERY_LENGTH = 500  # as the search takes it
MAX_FILTER_FACTS = 5
"""Facts a lens's filter names at most."""
MAX_FILTER_VALUES = 50
"""Values of one kind (contacts, types, tags, spaces) a filter names at most: the documents list
takes them as query parameters (`rest.params`, the MCP tools), and 200 ids would burst the 8 KiB
nginx allows the request line. A lens holds no more (`Lens.change`); one stored with more before
is read as it is, to be shortened."""


class Grouping(StrEnum):
    """What the documents of a lens stand under: nothing, the month of their document date, how
    soon their deadline is due, their type or their contact."""

    NONE = "none"
    MONTH = "month"
    DUE = "due"
    DOCUMENT_TYPE = "document_type"
    CONTACT = "contact"


class Layout(StrEnum):
    GRID = "grid"
    LIST = "list"
    STREAM = "stream"  # the documents in lanes (#145, `services.stream`)


class RelativePeriod(StrEnum):
    """A period that moves with the day the lens is opened (the quick picks of the filters)."""

    THIS_YEAR = "this_year"
    LAST_12_MONTHS = "last_12_months"
    LAST_YEAR = "last_year"

    def period(self, today: date) -> Period:
        """The days of the period as of `today`, as the web UI reckons them (`filters.ts`):
        this or last year, or the twelve months up to today."""
        match self:
            case RelativePeriod.THIS_YEAR:
                return Period.year(today.year)
            case RelativePeriod.LAST_YEAR:
                return Period.year(today.year - 1)
            case RelativePeriod.LAST_12_MONTHS:
                return Period(_a_year_before(today) + timedelta(days=1), date.max)


def _a_year_before(day: date) -> date:
    """The same day a year before; the 28th of February for the 29th."""
    try:
        return day.replace(year=day.year - 1)
    except ValueError:
        return day.replace(year=day.year - 1, day=28)


class LensSort(StrEnum):
    """The sort of a lens: by relevance (only with words), or a key of the documents list,
    descending with a `-`; `field` sorts by `Lens.sort_field_id` (not with words: the search
    index holds no field values)."""

    RELEVANCE = "relevance"
    CREATED = "created_at"
    CREATED_DESC = "-created_at"
    DOCUMENT_DATE = "document_date"
    DOCUMENT_DATE_DESC = "-document_date"
    TITLE = "title"
    TITLE_DESC = "-title"
    FIELD = "field"
    FIELD_DESC = "-field"

    @property
    def by_field(self) -> bool:
        return self in {LensSort.FIELD, LensSort.FIELD_DESC}


@dataclass(frozen=True, kw_only=True)
class LensFilter:
    """The filters of a lens, as the documents list takes them: one of the contacts, types,
    groups, topics and spaces each, all of the tags, a value for `field_id`, the document
    date either between `date_from` and `date_to` (both included, either open) or in
    `relative_period`, and each of the `facts`."""

    contact_ids: tuple[ContactId, ...] = ()
    document_type_ids: tuple[DocumentTypeId, ...] = ()
    contact_group_ids: tuple[TagId, ...] = ()
    document_type_group_ids: tuple[TagId, ...] = ()
    topic_ids: tuple[TagId, ...] = ()
    tag_ids: tuple[TagId, ...] = ()
    space_ids: tuple[SpaceId, ...] = ()
    field_id: FieldId | None = None
    date_from: date | None = None
    date_to: date | None = None
    relative_period: RelativePeriod | None = None
    facts: tuple[FactCriterion, ...] = ()

    _KINDS = (
        "contact_ids",
        "document_type_ids",
        "contact_group_ids",
        "document_type_group_ids",
        "topic_ids",
        "tag_ids",
        "space_ids",
    )

    def __post_init__(self) -> None:
        facts = tuple(dict.fromkeys(self.facts))
        if len(facts) > MAX_FILTER_FACTS:
            raise ValidationError(f"facts: at most {MAX_FILTER_FACTS}")
        object.__setattr__(self, "facts", facts)
        for name in self._KINDS:
            values = tuple(dict.fromkeys(getattr(self, name)))  # once each, in order
            object.__setattr__(self, name, values)
        if self.relative_period is not None and (
            self.date_from is not None or self.date_to is not None
        ):
            raise ValidationError("document_period: not together with document_date_from or _to")
        if (
            self.date_from is not None
            and self.date_to is not None
            and self.date_from > self.date_to
        ):
            raise ValidationError("document_date_from: after document_date_to")

    def check_values(self) -> None:
        """ValidationError if it names more than `MAX_FILTER_VALUES` of a kind: checked when a
        lens takes the filter, not when one is read."""
        for name in self._KINDS:
            if len(getattr(self, name)) > MAX_FILTER_VALUES:
                raise ValidationError(f"{name}: at most {MAX_FILTER_VALUES}")


@dataclass(kw_only=True)
class Lens:
    """A user's saved look at the documents; see the module. `position` orders a user's lenses
    (ascending). Names are unique per owner regardless of case."""

    id: LensId
    owner_id: UserId
    name: str
    position: int = 0
    filter: LensFilter = field(default_factory=LensFilter)
    query: str | None = None
    sort: LensSort | None = None  # None: as the list or the search sorts by default
    sort_field_id: FieldId | None = None
    grouping: Grouping = Grouping.NONE
    layout: Layout = Layout.GRID
    card_field_ids: tuple[FieldId, ...] = ()
    due_field_id: FieldId | None = None
    created_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        self.name = require_name(self.name, "lens name", max_length=MAX_NAME_LENGTH)
        self.query = _query(self.query)
        self.card_field_ids = tuple(dict.fromkeys(self.card_field_ids))
        self.created_at = require_utc(self.created_at, "created_at")
        self.updated_at = require_utc(self.updated_at, "updated_at")
        self.check()

    @classmethod
    def create(cls, *, owner_id: UserId, name: str, position: int, now: datetime) -> Self:
        return cls(
            id=LensId(new_id()),
            owner_id=owner_id,
            name=name,
            position=position,
            created_at=now,
            updated_at=now,
        )

    def check(self) -> None:
        """ValidationError if the parts do not fit together."""
        if len(self.card_field_ids) > MAX_CARD_FIELDS:
            raise ValidationError(f"card_field_ids: at most {MAX_CARD_FIELDS}")
        by_field = self.sort is not None and self.sort.by_field
        if by_field != (self.sort_field_id is not None):
            raise ValidationError("sort_field_id: needed to sort by a field, and only then")
        if by_field and self.query is not None:
            raise ValidationError("sort: a lens with words cannot sort by a field")
        if self.sort is LensSort.RELEVANCE and self.query is None:
            raise ValidationError("sort: by relevance only with words")
        if self.grouping is Grouping.DUE and self.due_field_id is None:
            raise ValidationError("grouping: by when it is due only with a due_field_id")

    def change(self, changes: "LensChanges", *, now: datetime) -> None:
        """Apply what `changes` sets, normalised as a new lens is (`apply_changes`, DB-07);
        ValidationError (and nothing changed) if the result does not fit together, or a filter
        it sets names too many values (`check_values`)."""
        if not isinstance(changes.filter, Unset):
            changes.filter.check_values()
        apply_changes(self, changes, self.__post_init__)
        self.updated_at = now


@dataclass(frozen=True, kw_only=True)
class LensChanges:
    """A change of a lens; parts left UNSET stay as they are."""

    name: str | Unset = UNSET
    filter: LensFilter | Unset = UNSET
    query: str | Unset | None = UNSET
    sort: LensSort | Unset | None = UNSET
    sort_field_id: FieldId | Unset | None = UNSET
    grouping: Grouping | Unset = UNSET
    layout: Layout | Unset = UNSET
    card_field_ids: tuple[FieldId, ...] | Unset = UNSET
    due_field_id: FieldId | Unset | None = UNSET


def _query(text: str | None) -> str | None:
    """Words stripped; none (empty) is None."""
    if text is None or not text.strip():
        return None
    words = text.strip()
    if len(words) > MAX_QUERY_LENGTH:
        raise ValidationError(f"query: at most {MAX_QUERY_LENGTH} characters")
    return words
