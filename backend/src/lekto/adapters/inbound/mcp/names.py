"""Contacts, document types, tags, topics and fields by name: the tools take names, not IDs (a
client has no other way to learn IDs), and give names. A name matches regardless of case; an
unknown one is an error that names similar ones, so the client need not list them first."""

import difflib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from uuid import UUID

from lekto.adapters.inbound.context import ApiContext
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.fields import FieldDefinition
from lekto.core.domain.identifiers import IdentifierKind
from lekto.core.domain.ids import ContactId, DocumentTypeId, FieldId, TagId, UserId
from lekto.core.domain.master_data import TagScope
from lekto.core.domain.sorting import sort_key
from lekto.core.domain.spaces import Space
from lekto.core.domain.validation import name_key

SIMILAR = 3
"""Names an error suggests at most."""
FORMER_ACCOUNT = "a former account"
"""How the tools name a person whose account is gone."""
_CONTAINED = 3
"""Characters a name has at least to be suggested for standing in the one asked for or it."""


@dataclass(frozen=True)
class Names:
    """The names of contacts, document types, tags and fields (visible to every user)."""

    contacts: dict[UUID, str]
    document_types: dict[UUID, str]
    tags: dict[UUID, str]
    fields: dict[FieldId, FieldDefinition]
    topics: dict[UUID, str]
    groups: dict[UUID, str] = field(default_factory=dict)  # of contacts and of types

    @classmethod
    async def load(cls, context: ApiContext, user: UserId) -> "Names":
        master = context.master_data
        tags = await master.list_tags(user)

        def of(*scopes: TagScope) -> dict[UUID, str]:
            return {tag.id: tag.name for tag in tags if tag.scope in scopes}

        return cls(
            contacts={c.id: c.name for c in await master.list_contacts(user)},
            document_types={t.id: t.name for t in await master.list_document_types(user)},
            tags=of(TagScope.DOCUMENT),
            fields={a.id: a for a in await master.list_fields(user)},
            topics=of(TagScope.TOPIC),
            groups=of(TagScope.CONTACT, TagScope.DOCUMENT_TYPE),
        )

    def contact(self, id: UUID | None) -> str | None:
        return None if id is None else self.contacts.get(id, str(id))

    def document_type(self, id: UUID | None) -> str | None:
        return None if id is None else self.document_types.get(id, str(id))

    def topic(self, id: UUID | None) -> str | None:
        return None if id is None else self.topics.get(id, str(id))

    def tag_names(self, ids: Iterable[UUID]) -> list[str]:
        return sorted((self.tags.get(i, str(i)) for i in ids), key=sort_key)

    def field_name(self, id: FieldId) -> str:
        definition = self.fields.get(id)
        return str(id) if definition is None else definition.name

    # --- name to id, for input

    def find_contact(self, name: str) -> ContactId:
        return ContactId(find("contact", name, self.contacts))

    def find_document_type(self, name: str) -> DocumentTypeId:
        return DocumentTypeId(find("document type", name, self.document_types))

    def find_tag(self, name: str) -> TagId:
        return TagId(find("tag", name, self.tags))

    def find_topic(self, name: str) -> TagId:
        return TagId(find("topic", name, self.topics))

    def find_field(self, name: str) -> FieldDefinition:
        by_name: dict[UUID, str] = {id: definition.name for id, definition in self.fields.items()}
        return self.fields[FieldId(find("field", name, by_name))]


def find(kind: str, name: str, names: dict[UUID, str]) -> UUID:
    wanted = name_key(name)
    for id, existing in names.items():
        if name_key(existing) == wanted:
            return id
    similar = similar_names(name, names.values())
    hint = f"; similar: {', '.join(similar)}" if similar else ""
    raise ValidationError(f"no {kind} named {name!r}{hint}")


def similar_names(name: str, names: Iterable[str]) -> list[str]:
    """Up to `SIMILAR` of `names` like `name`: those it stands in or that stand in it ("Stadtwerk"
    in "Stadtwerke Musterstadt"), then those spelt alike."""
    wanted = name_key(name)
    keyed = {name_key(existing): existing for existing in names}
    containing = sorted(
        (
            existing
            for key, existing in keyed.items()
            if min(len(key), len(wanted)) >= _CONTAINED and (wanted in key or key in wanted)
        ),
        key=sort_key,
    )
    alike = [keyed[key] for key in difflib.get_close_matches(wanted, keyed, n=SIMILAR)]
    return list(dict.fromkeys(containing + alike))[:SIMILAR]


def identifier_kind(name: str, what: str) -> IdentifierKind:
    """The kind of identifier `name` names; an error with similar ones for none, naming it a
    kind of `what` (a fact, an identifier): the kinds are many, their names in a tool's schema
    would cost every conversation."""
    try:
        return IdentifierKind(name.strip().lower())
    except ValueError:
        alike = similar_names(name, [kind.value for kind in IdentifierKind])
        hint = f"; similar: {', '.join(alike)}" if alike else ""
        raise ValidationError(f"no kind of {what} named '{name}'{hint}") from None


async def member_labels(
    context: ApiContext, user: UserId, spaces: Iterable[Space]
) -> dict[UserId, str]:
    """How the caller reads the members of `spaces`, by their ids."""
    members = await context.spaces.members(user, list(spaces))
    return {id: person.label for id, person in members.items()}


def space_label(space: Space, people: Mapping[UserId, str]) -> str:
    """How the caller reads a space: a personal one by its person's name (`member_labels`)."""
    if space.personal_of is not None and space.personal_of in people:
        return people[space.personal_of]
    return space.name
