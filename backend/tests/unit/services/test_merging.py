"""Merging documents (`EditingService` with `documents`, `domain.editing`): the part that
replaces makes the next version of the target; the other documents go, their versions become
the target's, their relations name it; a merge without that part is refused (Tobi, 11.11.2026)."""

import pytest

from lekto.adapters.outbound.memory import fake_pdf
from lekto.core.domain.documents import Document
from lekto.core.domain.editing import MAX_MERGED
from lekto.core.domain.errors import (
    DuplicateDocumentError,
    InvalidTransitionError,
    NotFoundError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from lekto.core.domain.ids import DocumentId
from lekto.core.domain.pipeline import Node
from lekto.core.domain.relations import Relation, RelationOrigin, RelationState
from lekto.core.domain.users import User
from lekto.core.domain.versions import VersionKind
from lekto.core.services.editing import MOVED
from lekto.core.services.objects import original_key, page_key
from tests.builders import HOUR, NOW, incoming
from tests.unit.services.support import World
from tests.unit.services.test_editing import STACK, part, received
from tests.unit.services.test_maintenance import maintenance

SCAN = fake_pdf(2, "the forgotten page and its blank back")


async def two(world: World) -> tuple[User, Document, Document]:
    """A user's stack of three pages and their scan of two, both processed."""
    owner, stack = await received(world)
    scan = await world.pipeline().receive(owner.id, incoming(SCAN), filename="scan_0412.pdf")
    await world.drain()
    return owner, stack, scan


async def relation(world: World, newer: Document, older: Document) -> None:
    async with world.uow() as uow:
        await uow.document_relations.put(
            Relation(
                newer=newer.id,
                older=older.id,
                origin=RelationOrigin.PERSON,
                state=RelationState.SET,
                created_at=NOW,
            )
        )
        await uow.commit()


async def test_merging_makes_one_document_of_two(world: World) -> None:
    owner, stack, scan = await two(world)
    world.clock.advance(HOUR)
    # The scan is source 1: two pages of the stack, the scan's first; the rest goes.
    result = await world.editing.edit(
        owner.id, stack.id, [part(1, 2, (1, 1), replaces=True)], documents=[scan.id]
    )
    assert not result.deleted and result.merged == (scan.id,)
    (merged,) = (view.document for view in result.documents)
    assert merged.id == stack.id
    assert merged.processing.new_version and merged.processing.due() == (Node.SEPARATE,)
    with pytest.raises(NotFoundError):
        await world.documents.get(owner.id, scan.id)
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(stack.id)
    assert [(version.number, version.kind) for version in versions] == [
        (1, VersionKind.RECEIVED),
        (2, VersionKind.RECEIVED),
        (3, VersionKind.MERGED),
    ]
    moved, made = versions[1], versions[2]
    assert moved.sha256 == scan.sha256 and moved.original_filename == "scan_0412.pdf"
    assert moved.detail[MOVED] == {"document": str(scan.id), "title": "scan_0412", "version": 1}
    assert made.sha256 == merged.sha256 and made.created_by == owner.id
    assert made.detail["from"] == 1
    assert made.detail["documents"] == [
        {"document": str(stack.id), "title": "stack", "version": 1},
        {"document": str(scan.id), "title": "scan_0412", "version": 2},
    ]
    # The scan's derivatives go, its original stays: a version of the stack now.
    service = maintenance(world)
    while await service.run_next_job():
        pass
    assert await world.object_store.exists(original_key(scan.sha256))
    assert not await world.object_store.exists(page_key(scan.id, 1))
    with pytest.raises(DuplicateDocumentError) as duplicate:
        await world.pipeline().receive(owner.id, incoming(SCAN), filename="again.pdf")
    assert (duplicate.value.existing, duplicate.value.version) == (stack.id, 2)


async def test_the_target_may_be_another_of_them(world: World) -> None:
    owner, stack, scan = await two(world)
    result = await world.editing.edit(
        owner.id,
        stack.id,
        [part((1, 1), 1, 2, 3, replaces=True), part((1, 2))],
        documents=[scan.id],
        target=scan.id,
    )
    assert result.merged == (stack.id,)
    target, split = (view.document for view in result.documents)
    assert target.id == scan.id and split.id not in (stack.id, scan.id)
    with pytest.raises(NotFoundError):
        await world.documents.get(owner.id, stack.id)
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(scan.id)
    assert [(version.number, version.kind) for version in versions] == [
        (1, VersionKind.RECEIVED),
        (2, VersionKind.RECEIVED),
        (3, VersionKind.MERGED),
    ]
    assert versions[1].sha256 == stack.sha256
    assert versions[2].detail["documents"] == [
        {"document": str(stack.id), "title": "stack", "version": 2},
        {"document": str(scan.id), "title": "scan_0412", "version": 1},
    ]


async def test_a_merge_needs_a_part_that_continues_the_target(world: World) -> None:
    """Without it, both documents would go, their originals with them."""
    owner, stack, scan = await two(world)
    before = world.object_store.keys()
    with pytest.raises(ValidationError, match="continues the target"):
        await world.editing.edit(
            owner.id, stack.id, [part(1, 2, 3), part((1, 1), (1, 2))], documents=[scan.id]
        )
    assert world.object_store.keys() == before
    for document in (stack, scan):
        assert (await world.documents.get(owner.id, document.id)).sha256 == document.sha256


async def test_the_relations_of_a_merged_document_name_the_target(world: World) -> None:
    owner, stack, scan = await two(world)
    pipeline = world.pipeline()
    letter = await pipeline.receive(owner.id, incoming(fake_pdf(1, "letter")), filename="l.pdf")
    reply = await pipeline.receive(owner.id, incoming(fake_pdf(1, "reply")), filename="r.pdf")
    await world.drain()
    await relation(world, scan, stack)  # between the two: goes
    await relation(world, reply, scan)  # moves, in its direction
    await relation(world, scan, letter)  # the stack has it already: stays once
    await relation(world, stack, letter)
    await world.editing.edit(
        owner.id, stack.id, [part(1, 2, 3, (1, 1), (1, 2), replaces=True)], documents=[scan.id]
    )
    async with world.uow() as uow:
        found = await uow.document_relations.of_document(stack.id)
    assert sorted((item.newer, item.older) for item in found) == sorted(
        [(reply.id, stack.id), (stack.id, letter.id)]
    )


async def test_who_may_merge_and_what(world: World) -> None:
    owner, stack, scan = await two(world)
    stranger = await world.user()
    theirs = await world.pipeline().receive(
        stranger.id, incoming(fake_pdf(1, "theirs")), filename="theirs.pdf"
    )
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    letter = await world.pipeline().receive(owner.id, incoming(mail), filename="m.eml")
    await world.drain()
    merge = [part(1, (1, 1), replaces=True)]
    with pytest.raises(NotFoundError):  # every document needs the right to edit its pages
        await world.editing.edit(owner.id, stack.id, merge, documents=[theirs.id])
    with pytest.raises(UnsupportedMediaTypeError, match="mail"):
        await world.editing.edit(owner.id, stack.id, merge, documents=[letter.id])
    with pytest.raises(ValidationError, match="each once"):
        await world.editing.edit(owner.id, stack.id, merge, documents=[scan.id, scan.id])
    with pytest.raises(ValidationError, match="each once"):
        await world.editing.edit(owner.id, stack.id, merge, documents=[stack.id])
    with pytest.raises(ValidationError, match="target"):
        await world.editing.edit(owner.id, stack.id, merge, documents=[scan.id], target=theirs.id)
    many = [DocumentId(scan.id)] * (MAX_MERGED + 1)
    with pytest.raises(ValidationError, match=f"at most {MAX_MERGED}"):
        await world.editing.edit(owner.id, stack.id, merge, documents=many)
    fresh = await world.pipeline().receive(owner.id, incoming(STACK + b"%"), filename="new.pdf")
    with pytest.raises(InvalidTransitionError):  # still processed
        await world.editing.edit(owner.id, stack.id, merge, documents=[fresh.id])
    for document in (stack, scan):
        assert (await world.documents.get(owner.id, document.id)).sha256 == document.sha256
