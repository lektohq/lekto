"""Editing a document's pages (`EditingService`, `domain.editing`): the part that replaces the
document is its next version, every other part a new document in its space, the document gone
without one; added files bring their pages but are no originals of their own; all of it in one
transaction, and every result waits in the inbox."""

import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from lekto.adapters.outbound.memory import FakePageComposer, fake_pdf
from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.documents import Channel, Document, DocumentChanges, Sha256
from lekto.core.domain.editing import MAX_ADDED, EditPart, PagePick
from lekto.core.domain.errors import (
    ConcurrencyError,
    InvalidTransitionError,
    NotFoundError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from lekto.core.domain.ids import MailboxId, MailRecordId, new_id
from lekto.core.domain.mail_intake import MailOrigin, OriginRole
from lekto.core.domain.pipeline import Lane, Node, ProcessingHistory
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.users import Role, User
from lekto.core.domain.versions import VersionKind
from lekto.core.ports.composer import PageSource
from lekto.core.services._intake import SPLIT_FROM
from lekto.core.services.editing import AddedFile
from lekto.core.services.objects import original_key, page_key
from lekto.core.services.rules.nodes import ApplyRulesNode
from tests.builders import HOUR, NOW, TEMPLATES, incoming
from tests.unit.services.support import World
from tests.unit.services.test_maintenance import maintenance

STACK = fake_pdf(3, "three payslips")
FORGOTTEN = fake_pdf(2, "forgotten pages")
MEANWHILE = fake_pdf(1, "put in its place meanwhile")


def part(*pages: int | tuple[int, int] | tuple[int, int, int], replaces: bool = False) -> EditPart:
    """A part of pages of the original (a number), or of a source (source, page[, turn])."""
    picks = []
    for page in pages:
        if isinstance(page, int):
            picks.append(PagePick(0, page))
        else:
            picks.append(PagePick(*page))
    return EditPart(tuple(picks), replaces=replaces)


def added(data: bytes, name: str = "forgotten.pdf") -> AddedFile:
    return AddedFile(incoming(data), name)


async def received(world: World) -> tuple[User, Document]:
    """A user and their document of three pages, processed."""
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain()
    return owner, document


async def test_a_part_replaces_the_document_and_the_others_become_new_documents(
    world: World,
) -> None:
    owner, document = await received(world)
    world.clock.advance(HOUR)
    result = await world.editing.edit(
        owner.id, document.id, [part(1, 2, replaces=True), part((0, 3, 90))]
    )
    assert not result.deleted
    edited, new = (view.document for view in result.documents)
    assert edited.id == document.id
    assert edited.sha256 != document.sha256 and edited.original_filename == "stack.pdf"
    assert edited.processing.new_version and edited.processing.due() == (Node.SEPARATE,)
    # The new one lies in the same space, came in as the document did, and a person chose
    # its space; it runs from the start and ends in the inbox too.
    assert (new.space_id, new.uploaded_by, new.channel) == (
        document.space_id,
        owner.id,
        document.channel,
    )
    assert new.created_at == document.created_at and new.space_confirmed_at is not None
    assert new.original_filename == "stack (2).pdf" and new.processing.new_version
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(document.id)
        (first,) = await uow.document_versions.of_document(new.id)
        log = await uow.processing_log.list_for(new.id)
    assert [(item.number, item.kind) for item in versions] == [
        (1, VersionKind.RECEIVED),
        (2, VersionKind.EDITED),
    ]
    assert versions[1].detail == {
        "from": 1,
        "pages": [
            {"source": 0, "page": 1, "rotate": 0},
            {"source": 0, "page": 2, "rotate": 0},
        ],
        "added": [],
        "split_off": [str(new.id)],
    }
    assert (first.kind, first.created_by, first.sha256) == (VersionKind.SPLIT, owner.id, new.sha256)
    assert first.detail == {
        "pages": [{"source": 0, "page": 3, "rotate": 90}],
        "added": [],
        "document": str(document.id),
        "title": document.title,
        "version": 1,
    }
    receive = ProcessingHistory(log).latest(Node.RECEIVE)
    assert receive is not None and receive.result.output[SPLIT_FROM] == str(document.id)
    # Each part is a file of its own pages; the original of version 1 stays.
    turned = await world.object_store.get(original_key(new.sha256))
    assert turned.count(b"% fake page") == 1 and turned.rstrip().endswith(b"%%EOF")
    assert b" 3 90\n" in turned
    assert await world.object_store.get(original_key(document.sha256)) == STACK
    assert not await world.object_store.exists(page_key(document.id, 1))


async def test_pages_split_off_a_mailed_document_keep_its_mail(world: World) -> None:
    """As the parts of a stack do (`_intake.store_part`)."""
    owner = await world.user()
    document = await world.pipeline().receive(
        owner.id, incoming(STACK), filename="stack.pdf", channel=Channel.MAIL
    )
    origin = MailOrigin(
        document_id=document.id,
        record_id=MailRecordId(new_id()),
        mailbox_id=MailboxId(new_id()),
        mailbox="Post",
        rule="Scans",
        role=OriginRole.ATTACHMENT,
        letter=1,
        message_id="<scans@example.org>",
        sender=(),
        to=(),
        cc=(),
        subject="Scans",
        sent_at=None,
        arrived_at=NOW,
        filename="stack.pdf",
    )
    async with world.uow() as uow:
        await uow.mail_origins.add(origin)
        await uow.commit()
    await world.drain()
    result = await world.editing.edit(owner.id, document.id, [part(1, 2, replaces=True), part(3)])
    _, new = (view.document for view in result.documents)
    assert new.channel is Channel.MAIL
    async with world.uow() as uow:
        assert await uow.mail_origins.find(new.id) == replace(origin, document_id=new.id)


async def test_without_a_part_that_replaces_it_the_document_is_deleted(world: World) -> None:
    owner, document = await received(world)
    result = await world.editing.edit(owner.id, document.id, [part(1), part(2, 3)])
    assert result.deleted
    first, second = (view.document for view in result.documents)
    assert document.id not in (first.id, second.id)
    with pytest.raises(NotFoundError):
        await world.documents.get(owner.id, document.id)
    assert "document.deleted" in world.event_types()
    service = maintenance(world)
    while await service.run_next_job():
        pass
    # Its original goes; the parts are originals of their own.
    assert not await world.object_store.exists(original_key(document.sha256))
    for new in (first, second):
        assert await world.object_store.exists(original_key(new.sha256))
        async with world.uow() as uow:
            (version,) = await uow.document_versions.of_document(new.id)
        assert version.detail["document"] == str(document.id)


async def test_added_files_bring_their_pages_but_are_no_originals(world: World) -> None:
    owner, document = await received(world)
    forgotten = added(FORGOTTEN)
    result = await world.editing.edit(
        owner.id,
        document.id,
        [part(1, (1, 1), (1, 2, 180), 2, 3, replaces=True)],
        [forgotten],
    )
    (edited,) = (view.document for view in result.documents)
    stored = await world.object_store.get(original_key(edited.sha256))
    assert stored.count(b"% fake page") == 5
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(document.id)
        assert await uow.document_versions.find_by_sha256(forgotten.file.sha256) is None
    assert versions[-1].detail["added"] == ["forgotten.pdf"]
    assert not await world.object_store.exists(original_key(forgotten.file.sha256))
    # The added file may come in as a document of its own.
    await world.pipeline().receive(owner.id, incoming(FORGOTTEN), filename="forgotten.pdf")


@pytest.mark.parametrize(
    ("parts", "files", "message"),
    [
        ([], 0, "at least one"),
        ([part(1, 2, 3, replaces=True)], 0, "nothing changed"),
        ([part(1, replaces=True), part(2, replaces=True)], 0, "at most one replaces"),
        ([part(1, 2), part(2)], 0, "page 2 of source 0 twice"),
        ([part(4)], 0, "source 0 has 3 pages, not 4"),
        ([part((2, 1))], 1, "no source 2"),
        ([part(1)], MAX_ADDED + 1, f"at most {MAX_ADDED}"),
    ],
)
async def test_parts_must_fit_the_pages(
    world: World, parts: list[EditPart], files: int, message: str
) -> None:
    owner, document = await received(world)
    before = world.object_store.keys()
    extra = [added(fake_pdf(1, f"file {number}")) for number in range(files)]
    with pytest.raises(ValidationError, match=message):
        await world.editing.edit(owner.id, document.id, parts, extra)
    assert world.object_store.keys() == before
    assert (await world.documents.get(owner.id, document.id)).sha256 == document.sha256


async def test_who_may_edit_and_what(world: World) -> None:
    owner, stranger = await world.user(), await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    with pytest.raises(InvalidTransitionError):  # still processed
        await world.editing.edit(owner.id, document.id, [part(1, replaces=True)])
    await world.drain()
    with pytest.raises(NotFoundError):
        await world.editing.edit(stranger.id, document.id, [part(1, replaces=True)])
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    with pytest.raises(UnsupportedMediaTypeError):
        await world.editing.edit(
            owner.id, document.id, [part(1, (1, 1), replaces=True)], [added(mail, "m.eml")]
        )
    letter = await world.pipeline().receive(owner.id, incoming(mail), filename="m.eml")
    await world.drain()
    with pytest.raises(UnsupportedMediaTypeError, match="mail"):
        await world.editing.edit(owner.id, letter.id, [part(1)])


class Meddling(FakePageComposer):
    """Puts another file in the document's place while it makes the first part."""

    def __init__(self, world: World, owner: User, document: Document) -> None:
        super().__init__()
        self.world, self.owner, self.document = world, owner, document

    async def compose(
        self, sources: Sequence[PageSource], pages: Sequence[PagePick], target: Path
    ) -> None:
        await super().compose(sources, pages, target)
        if len(self.calls) == 1:
            await self.world.pipeline().new_version(
                self.owner.id, self.document.id, incoming(MEANWHILE), filename="meanwhile.pdf"
            )


async def test_a_file_changed_meanwhile_stops_the_edit_and_leaves_nothing(world: World) -> None:
    owner, document = await received(world)
    world.composer = Meddling(world, owner, document)
    originals = world.object_store.keys("originals/")
    with pytest.raises(ConcurrencyError):
        await world.editing.edit(owner.id, document.id, [part(1), part(2, 3, replaces=True)])
    # Only the file put in its place meanwhile is new; no part is left, no document made.
    assert world.object_store.keys("originals/") == sorted(
        [*originals, original_key(Sha256.of(MEANWHILE))]
    )
    async with world.uow() as uow:
        assert await uow.documents.count_all() == 1


async def test_every_result_waits_in_the_inbox_and_what_was_confirmed_stays(
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
    result = await world.editing.edit(owner.id, document.id, [part(3, replaces=True), part(1, 2)])
    await world.drain(pipeline)
    edited, new = [
        await world.documents.get(owner.id, view.document.id) for view in result.documents
    ]
    assert (edited.contact_id, edited.document_date) == (contact.id, date(2022, 11, 25))
    assert new.contact_id is None
    for item in (edited, new):
        assert item.lane is Lane.YELLOW
        log = await world.documents.processing_log(owner.id, item.id)
        entry = ProcessingHistory(log).latest(Node.APPLY_RULES)
        assert entry is not None
        assert ReasonCode.NEW_VERSION in {reason.code for reason in entry.result.reasons}
    assert new.channel is Channel.API


async def test_the_pages_of_a_file_to_add_are_shown_before(world: World) -> None:
    owner, document = await received(world)
    stranger = await world.user()
    before = world.object_store.keys()
    pages = await world.editing.preview(owner.id, document.id, incoming(FORGOTTEN))
    assert len(pages) == 2 and all(page.startswith(b"RIFF") for page in pages)
    assert world.object_store.keys() == before
    with pytest.raises(NotFoundError):
        await world.editing.preview(stranger.id, document.id, incoming(FORGOTTEN))
    with pytest.raises(UnsupportedMediaTypeError):
        await world.editing.preview(owner.id, document.id, incoming(b"From: a@b.c\r\n\r\nx"))


async def test_an_edit_is_logged(world: World, caplog: pytest.LogCaptureFixture) -> None:
    """With the level of the service (the tests run quieter), the record is made."""
    owner, document = await received(world)
    caplog.set_level(logging.INFO, logger="lekto.core.services.editing")
    await world.editing.edit(owner.id, document.id, [part(1), part(2, 3, replaces=True)])
    (record,) = [item for item in caplog.records if item.getMessage() == "pages edited"]
    assert (record.new_documents, record.deleted) == (1, False)  # type: ignore[attr-defined]
