"""Versions of a document's original (`domain.versions`): the first comes with the document,
every version's file counts for duplicates, and all their originals go with the document."""

from dataclasses import replace
from pathlib import Path

import pytest

from lekto.core.domain.documents import Document, Sha256
from lekto.core.domain.errors import DuplicateDocumentError, NotFoundError
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.services.objects import original_key
from tests.builders import incoming
from tests.unit.services.support import World
from tests.unit.services.test_maintenance import maintenance

STACK = b"%PDF-1.7 three payslips"
PART = b"%PDF-1.7 november only"


async def with_earlier_version(world: World, document: Document) -> DocumentVersion:
    """A second version beside the document's first, its file in the store (as a replaced
    file will add it)."""
    async with world.uow() as uow:
        first = (await uow.document_versions.of_document(document.id))[0]
        second = replace(
            first,
            number=2,
            sha256=Sha256.of(PART),
            original_filename="november.pdf",
            kind=VersionKind.EDITED,
            created_at=world.clock.now(),
            detail={"from": 1, "pages": [5, 6]},
        )
        await uow.document_versions.add(second)
        await uow.commit()
    await world.object_store.put(original_key(second.sha256), PART, content_type="application/pdf")
    return second


async def test_a_document_comes_in_as_its_first_version(world: World) -> None:
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    async with world.uow() as uow:
        assert await uow.document_versions.of_document(document.id) == [
            DocumentVersion(
                document_id=document.id,
                number=1,
                sha256=Sha256.of(STACK),
                original_filename="stack.pdf",
                media_type="application/pdf",
                kind=VersionKind.RECEIVED,
                created_at=document.created_at,
                created_by=owner.id,
            )
        ]


async def test_the_file_of_any_version_is_a_duplicate(world: World) -> None:
    """Every file exists once, an earlier version's too (Tobi, 10.11.2026): the error names
    the document and the version to who may read it."""
    owner, stranger = await world.user(), await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await with_earlier_version(world, document)
    with pytest.raises(DuplicateDocumentError) as info:
        await world.pipeline().receive(owner.id, incoming(PART), filename="again.pdf")
    assert (info.value.existing, info.value.version) == (document.id, 2)
    assert str(info.value) == f"duplicate of version 2 of document {document.id}"
    with pytest.raises(DuplicateDocumentError) as info:
        await world.pipeline().receive(stranger.id, incoming(PART), filename="mine.pdf")
    assert (info.value.existing, info.value.version) == (None, None)


async def test_deleting_a_document_removes_the_originals_of_all_its_versions(
    world: World,
) -> None:
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    second = await with_earlier_version(world, document)
    await world.drain()
    await world.documents.delete(owner.id, document.id)
    service = maintenance(world)
    while await service.run_next_job():
        pass
    assert not await world.object_store.exists(original_key(document.sha256))
    assert not await world.object_store.exists(original_key(second.sha256))
    # Its files may come in again.
    again = await world.pipeline().receive(owner.id, incoming(PART), filename="part.pdf")
    async with world.uow() as uow:
        assert [item.number for item in await uow.document_versions.of_document(again.id)] == [1]


async def test_the_files_name_the_versions_and_give_an_earlier_one(
    world: World, tmp_path: Path
) -> None:
    owner, stranger = await world.user(), await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    second = await with_earlier_version(world, document)
    files = await world.documents.files(owner.id, document.id)
    assert [version.number for version in files.versions] == [1, 2]
    target = tmp_path / "version"
    info = await world.documents.download_version(owner.id, document.id, 2, target)
    assert (info.media_type, info.filename) == (second.media_type, "november.pdf")
    assert target.read_bytes() == PART
    for actor, number in ((owner.id, 3), (stranger.id, 1)):
        with pytest.raises(NotFoundError):
            await world.documents.download_version(actor, document.id, number, target)
