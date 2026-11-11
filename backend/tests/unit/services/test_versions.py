"""Versions of a document's original (`domain.versions`): the first comes with the document,
every version's file counts for duplicates, and all their originals go with the document."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.classification import FieldCheck
from lekto.core.domain.documents import Document, DocumentChanges, Sha256
from lekto.core.domain.errors import (
    DuplicateDocumentError,
    InvalidTransitionError,
    NotFoundError,
    UnsupportedMediaTypeError,
)
from lekto.core.domain.pipeline import Lane, Node, Outcome, ProcessingHistory, ProcessingStatus
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.users import Role
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.services.classification.nodes import _kept
from lekto.core.services.objects import archive_key, derivative_keys, original_key, page_key
from lekto.core.services.rules.nodes import ApplyRulesNode
from tests.builders import FAILED, TEMPLATES, Returns, incoming
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


async def test_a_new_version_takes_the_original_s_place_and_runs_anew(world: World) -> None:
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain()
    for key in derivative_keys(document.id, 3):
        await world.object_store.put(key, b"x", content_type="x")
    async with world.uow() as uow:
        stored = await uow.documents.get(document.id)
        stored.set_page_count(3, world.clock.now())
        await uow.documents.update(stored)
        await uow.commit()
    view = await world.pipeline().new_version(
        owner.id, document.id, incoming(PART), filename="november.pdf"
    )
    replaced = view.document
    assert (replaced.sha256, replaced.original_filename) == (Sha256.of(PART), "november.pdf")
    assert replaced.processing.status is ProcessingStatus.PROCESSING
    assert replaced.processing.new_version and replaced.page_count is None
    # Everything after receiving runs again: the pages run beside OCR, not after it.
    assert replaced.processing.due() == (Node.SEPARATE,)
    assert await world.object_store.get(original_key(replaced.sha256)) == PART
    # The earlier version's derivatives are gone; its original stays.
    assert not await world.object_store.exists(archive_key(document.id))
    assert not await world.object_store.exists(page_key(document.id, 3))
    assert await world.object_store.get(original_key(document.sha256)) == STACK
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(document.id)
    assert [(item.number, item.kind, item.created_by) for item in versions] == [
        (1, VersionKind.RECEIVED, owner.id),
        (2, VersionKind.REPLACED, owner.id),
    ]


async def test_a_new_version_helps_a_document_that_failed(world: World) -> None:
    owner = await world.user()
    pipeline = world.pipeline({Node.PAGES: Returns(FAILED)})
    document = await pipeline.receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain(pipeline)
    assert (await world.documents.get(owner.id, document.id)).lane is Lane.RED
    view = await world.pipeline().new_version(
        owner.id, document.id, incoming(PART), filename="november.pdf"
    )
    assert view.document.processing.due() == (Node.SEPARATE,)
    await world.drain()
    after = await world.documents.get(owner.id, document.id)
    assert after.processing.status is ProcessingStatus.COMPLETED  # the rules of the world pass


async def test_a_new_version_must_be_a_new_file_of_a_kind_a_document_has(world: World) -> None:
    owner, reader = await world.user(), await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    other = await world.pipeline().receive(owner.id, incoming(PART), filename="part.pdf")
    with pytest.raises(InvalidTransitionError):  # still processed
        await world.pipeline().new_version(
            owner.id, document.id, incoming(b"%PDF-1.7 new"), filename="new.pdf"
        )
    await world.drain()
    for file in (STACK, PART):  # its own, another document's
        with pytest.raises(DuplicateDocumentError):
            await world.pipeline().new_version(
                owner.id, document.id, incoming(file), filename="again.pdf"
            )
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    with pytest.raises(UnsupportedMediaTypeError):
        await world.pipeline().new_version(owner.id, document.id, incoming(mail), filename="m.eml")
    with pytest.raises(NotFoundError):
        await world.pipeline().new_version(
            reader.id, document.id, incoming(b"%PDF-1.7 mine"), filename="mine.pdf"
        )
    assert other.id != document.id


async def test_a_new_version_keeps_what_a_person_confirmed_and_waits_in_the_inbox(
    world: World,
) -> None:
    owner = await world.user()
    admin = await world.user(role=Role.ADMIN)
    contact = await world.master_data.create_contact(admin.id, "INTER")
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain()
    await world.documents.update_metadata(
        owner.id,
        document.id,
        DocumentChanges(contact_id=contact.id, document_date=date(2022, 11, 25)),
    )
    rules = ApplyRulesNode(
        world.uow, world.object_store, RegexPatternMatcher(0.2), TEMPLATES, max_text=200_000
    )
    pipeline = world.pipeline({Node.APPLY_RULES: rules})
    await pipeline.new_version(owner.id, document.id, incoming(PART), filename="nov.pdf")
    await world.drain(pipeline)
    after = await world.documents.get(owner.id, document.id)
    assert (after.contact_id, after.document_date) == (contact.id, date(2022, 11, 25))
    assert after.lane is Lane.YELLOW
    log = await world.documents.processing_log(owner.id, document.id)
    entry = ProcessingHistory(log).latest(Node.APPLY_RULES)
    assert entry is not None
    assert ReasonCode.NEW_VERSION in {reason.code for reason in entry.result.reasons}
    # Confirmed in the inbox, it is done: the rules ask no more.
    await pipeline.confirm(owner.id, document.id, DocumentChanges())
    await world.drain(pipeline)
    assert (await world.documents.get(owner.id, document.id)).lane is Lane.GREEN


def check_of(value: str | None, *, ok: bool = True, suggestion: str | None = None) -> FieldCheck:
    return FieldCheck(
        field="contact",
        outcome=Outcome.OK if ok else Outcome.UNCERTAIN,
        confidence=1.0 if ok else 0.4,
        value=value if ok else None,
        suggestion=suggestion,
        reasons=() if ok else (because(ReasonCode.NEW_VERSION_DIFFERS),),
    )


async def test_a_new_version_s_run_keeps_confirmed_values_and_suggests_what_differs(
    world: World,
) -> None:
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    document.confirmed_at = world.clock.now()
    document.processing.new_version = True
    same, other = check_of("c-1"), check_of("c-2")
    assert _kept(same, document, "c-1") == same
    differs = _kept(other, document, "c-1")
    assert (differs.ok, differs.value, differs.suggestion) == (False, None, "c-2")
    assert [reason.code for reason in differs.reasons] == [ReasonCode.NEW_VERSION_DIFFERS]
    unread = _kept(check_of(None, ok=False, suggestion="c-3"), document, "c-1")
    assert (unread.ok, unread.suggestion) == (False, "c-3")
    # Read the same, but uncertain (a quote missing, say): the person confirmed that value; the
    # check's own reasons stay, as remarks.
    doubted = FieldCheck(
        field="contact",
        outcome=Outcome.UNCERTAIN,
        confidence=0.4,
        suggestion="c-1",
        reasons=(because(ReasonCode.QUOTE_MISSING),),
    )
    agreed = _kept(doubted, document, "c-1")
    assert (agreed.ok, agreed.value, agreed.suggestion) == (True, "c-1", None)
    assert [reason.code for reason in agreed.reasons] == [ReasonCode.QUOTE_MISSING]
    # Nothing confirmed there, no value, or not a new version's run: as in any run.
    assert _kept(other, document, None) == other
    document.processing.new_version = False
    assert _kept(other, document, "c-1") == other
    document.processing.new_version, document.confirmed_at = True, None
    assert _kept(other, document, "c-1") == other
