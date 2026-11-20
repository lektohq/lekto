"""The contact a number of a document is a contact's by, as the reader may see it (XA-01): in
the facts and in the processing log, another user's number, one learned in a space not theirs
and one rejected show as unknown; admins see every one
(`.knowledge/decisions/2026-10-24-private-identifiers.md`)."""

from datetime import timedelta
from typing import Any

from lekto.adapters.outbound.memory import FakeCodeReader
from lekto.core.domain.identifiers import Identifier, IdentifierKind, IdentifierSource
from lekto.core.domain.master_data import Contact
from lekto.core.domain.pipeline import Node, NodeRun
from lekto.core.domain.rights import Actor
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import Role
from lekto.core.services.classification.signals import FactsSignal
from tests import builders
from tests.unit.services.classification_support import contacts, stored
from tests.unit.services.support import World

K = IdentifierKind.CUSTOMER_NUMBER
PUBLIC, ERIKAS, LEARNED, REJECTED = "77770001", "77770002", "77770003", "77770004"
TEXT = "".join(f"Kundennummer {number}\n" for number in (PUBLIC, ERIKAS, LEARNED, REJECTED))


async def _scene(world: World) -> tuple[Any, Any, Any, Any, Contact]:
    """John's letter in a space he shares with Bert, who edits it; the bank has a number entered
    by hand, one that names Erika, one learned in Erika's personal space and one rejected. The
    facts signal ran and is in the processing log."""
    john, bert, erika = await world.user(), await world.user(), await world.user()
    admin = await world.user(role=Role.ADMIN)
    shared = await world.spaces.create(Actor(john.id), "Shared")
    await world.spaces.set_member(Actor(john.id), shared.id, bert.id, SpaceRole.EDIT)
    erikas = await world.personal_space(erika)
    bank = Contact.create(name="Muster Bank", now=builders.NOW)
    bank.set_identifiers(
        [Identifier(K, PUBLIC), Identifier(K, ERIKAS, user_id=erika.id)],
        rejected=[Identifier(K, REJECTED)],
    )
    bank.set_learned(
        [Identifier(K, LEARNED, IdentifierSource.LEARNED, learned_in=frozenset({erikas.id}))]
    )
    await contacts(world, bank)
    document = await stored(world, john, TEXT)
    async with world.uow() as uow:
        moved = await uow.documents.get(document.id)
        moved.space_id = shared.id
        await uow.documents.update(moved)
        await uow.commit()
    result = await FactsSignal(world.uow, world.object_store, FakeCodeReader([])).run(moved)
    async with world.uow() as uow:
        applied = await result.apply(uow, await uow.documents.get(document.id), builders.NOW)  # type: ignore[union-attr]
        await uow.processing_log.append(
            NodeRun(
                document_id=document.id,
                node=Node.SIGNAL_FACTS,
                run=1,
                result=applied,
                pipeline_version="1",
                started_at=builders.NOW,
                duration=timedelta(seconds=1),
            )
        )
        await uow.commit()
    return bert, erika, admin, document, bank


async def _facts(world: World, user: Any, document: Any) -> dict[str, tuple[Any, Any]]:
    facts = await world.documents.facts(Actor(user.id), document.id)
    return {
        item.value: (item.contact_id, item.rejected_at)
        for item in facts.facts.identifiers
        if item.kind is K
    }


def _logged(log: Any) -> tuple[set[str], set[str]]:
    (run,) = [run for run in log if run.node is Node.SIGNAL_FACTS]
    output = run.result.output
    return (
        {item["value"] for item in output.get("identifiers", [])},
        {item["value"] for item in output.get("unknown_identifiers", [])},
    )


async def test_a_reader_sees_the_contact_of_the_numbers_they_may_see_alone(world: World) -> None:
    bert, _, _, document, bank = await _scene(world)
    assert await _facts(world, bert, document) == {
        PUBLIC: (bank.id, None),
        ERIKAS: (None, None),
        LEARNED: (None, None),
        REJECTED: (None, None),
    }
    # The signal leaves out a rejected one: no evidence of any contact.
    assert _logged(await world.documents.processing_log(Actor(bert.id), document.id)) == (
        {PUBLIC},
        {ERIKAS, LEARNED},
    )


async def test_admins_see_every_contact_and_rejection(world: World) -> None:
    _, _, admin, document, bank = await _scene(world)
    assert await _facts(world, admin, document) == {
        PUBLIC: (bank.id, None),
        ERIKAS: (bank.id, None),
        LEARNED: (bank.id, None),
        REJECTED: (None, bank.id),
    }
    assert _logged(await world.documents.processing_log(Actor(admin.id), document.id)) == (
        {PUBLIC, ERIKAS, LEARNED},
        set(),
    )
