"""Limits the services check before anything else (RA-03, RB-09)."""

import pytest

from lekto.core.domain.documents import MAX_TAGS, DocumentChanges
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.fields import MAX_TYPE_FIELDS
from lekto.core.domain.identifiers import IdentifierKind
from lekto.core.domain.ids import DocumentId, FieldId, TagId, new_id
from lekto.core.domain.open_identifiers import MAX_DECISIONS
from lekto.core.domain.rights import Actor
from lekto.core.domain.users import Role
from lekto.core.services.open_identifiers import OpenAction, OpenDecision
from tests.unit.services.support import World


async def test_a_change_sets_at_most_its_tags(world: World) -> None:
    user = await world.account()
    many = DocumentChanges(tag_ids=frozenset(TagId(new_id()) for _ in range(MAX_TAGS + 1)))
    with pytest.raises(ValidationError):
        await world.documents.change_metadata(Actor(user.id), DocumentId(new_id()), many)


async def test_a_type_has_at_most_its_fields(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    kind = await world.master_data.create_document_type(Actor(admin.id), "Invoice")
    fields = {FieldId(new_id()): False for _ in range(MAX_TYPE_FIELDS + 1)}
    with pytest.raises(ValidationError):
        await world.master_data.assign_fields(Actor(admin.id), kind.id, fields)


async def test_one_call_makes_at_most_its_decisions(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    decision = OpenDecision(
        kind=IdentifierKind.CUSTOMER_NUMBER, value="12345", action=OpenAction.REJECT
    )
    with pytest.raises(ValidationError):
        await world.open_identifiers.decide(Actor(admin.id), [decision] * (MAX_DECISIONS + 1))
