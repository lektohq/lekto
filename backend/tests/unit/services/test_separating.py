"""The node `separate` (`services.separating`, `domain.separating`): a stack that comes in is
split at its separator sheets; the stack stays version 1, the first part becomes version 2 and
every other part a new document as the stack came in, each processed as any new one."""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from lekto.adapters.outbound.memory import FakeCodeReader, fake_pdf
from lekto.core.domain.codes import Code
from lekto.core.domain.documents import Channel, Document
from lekto.core.domain.editing import EditPart, PagePick
from lekto.core.domain.errors import InvalidTransitionError
from lekto.core.domain.ids import DocumentId, MailboxId, MailRecordId, new_id
from lekto.core.domain.json_value import JsonObject, JsonValue
from lekto.core.domain.locations import Box
from lekto.core.domain.mail_intake import MailOrigin, OriginRole
from lekto.core.domain.pipeline import (
    PERSON_SPACE,
    Lane,
    Node,
    NodeResult,
    Outcome,
    ProcessingStatus,
)
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.separating import separated_parts, separator_pages
from lekto.core.domain.users import Role, User
from lekto.core.domain.versions import VersionKind
from lekto.core.services._intake import SPLIT_FROM
from lekto.core.services.objects import original_key
from lekto.core.services.pipeline import PipelineService
from lekto.core.services.separating import NOT_LOOKED, SeparateNode, Separation
from tests.builders import NOW, incoming
from tests.unit.services.support import World

STACK = fake_pdf(8, "two payslips and a letter")
BOX = Box.clamped(0.1, 0.1, 0.9, 0.3)


def sheets(*pages: int, text: str = "PATCHT") -> FakeCodeReader:
    return FakeCodeReader(
        [Code(page=page, format="Code 128", text=text, box=BOX) for page in pages]
    )


def pages_of(detail: JsonObject) -> list[JsonValue]:
    """The pages a version was made of, of the stack."""
    picks = detail["pages"]
    assert isinstance(picks, list)
    return [pick["page"] for pick in picks if isinstance(pick, dict)]


def separating(
    world: World, reader: FakeCodeReader, separators: Sequence[str] = ("PATCHT",)
) -> PipelineService:
    node = SeparateNode(
        world.uow,
        world.object_store,
        reader,
        world.composer,
        separators=separators,
        pipeline_version="test",
    )
    return world.pipeline(executors={Node.SEPARATE: node})


async def received(
    world: World,
    reader: FakeCodeReader,
    data: bytes = STACK,
    *,
    separators: Sequence[str] = ("PATCHT",),
    **options: object,
) -> tuple[User, Document]:
    owner = await world.user(role=Role.ADMIN)
    pipeline = separating(world, reader, separators)
    document = await pipeline.receive(
        owner.id,
        incoming(data),
        filename="scan_2026-11-10.pdf",
        **options,  # type: ignore[arg-type]
    )
    await world.drain(pipeline)
    return owner, document


async def separation(world: World, id: DocumentId) -> JsonObject:
    """What the node said in the document's last run."""
    async with world.uow() as uow:
        log = await uow.processing_log.list_for(id)
    *_, separate = [entry for entry in log if entry.node is Node.SEPARATE]
    return separate.result.output


async def not_looked(world: World, id: DocumentId) -> JsonValue:
    """Why the node did not look for sheets in the document's last run (`NOT_LOOKED`)."""
    return (await separation(world, id)).get(NOT_LOOKED)


async def documents(world: World) -> list[Document]:
    async with world.uow() as uow:
        return sorted(await uow.documents.list_all(), key=lambda item: item.file_title)


def test_a_sheet_is_a_page_with_a_code_of_its_whole_text_in_any_case() -> None:
    codes = [(4, "patcht"), (2, "PATCHT-1"), (8, "PATCHT"), (4, "PATCHT"), (6, "other")]
    assert separator_pages(codes, ["PATCHT"]) == [4, 8]
    assert separator_pages(codes, ["PATCHT", "other"]) == [4, 6, 8]


def test_no_part_is_empty_and_the_sheets_are_left_out() -> None:
    assert separated_parts(8, [3, 6]) == [(1, 2), (4, 5), (7, 8)]
    assert separated_parts(6, [1, 3, 4, 6]) == [(2,), (5,)]
    assert separated_parts(3, []) == [(1, 2, 3)]
    assert separated_parts(2, [1, 2]) == []


async def test_a_stack_is_split_at_its_sheets(world: World) -> None:
    reader = sheets(3, 6)
    owner, stack = await received(world, reader)
    first, second, third = await documents(world)
    assert first.id == stack.id
    assert first.sha256 != stack.sha256 and first.original_filename == "scan_2026-11-10.pdf"
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(stack.id)
        log = await uow.processing_log.list_for(stack.id)
        (split,) = await uow.document_versions.of_document(second.id)
        received_log = await uow.processing_log.list_for(second.id)
    assert [(version.number, version.kind) for version in versions] == [
        (1, VersionKind.RECEIVED),
        (2, VersionKind.SEPARATED),
    ]
    assert versions[0].sha256 == stack.sha256 and versions[1].sha256 == first.sha256
    assert versions[1].created_by is None
    assert versions[1].detail["sheets"] == [3, 6]
    assert versions[1].detail["split_off"] == [str(second.id), str(third.id)]
    assert pages_of(versions[1].detail) == [1, 2]
    (separate,) = [entry for entry in log if entry.node is Node.SEPARATE]
    assert separate.result.output == {
        "sheets": [3, 6],
        "pages": 8,
        "separators": ["PATCHT"],
        "codes": [
            {"page": 3, "format": "Code 128", "separator": True},
            {"page": 6, "format": "Code 128", "separator": True},
        ],
        "parts": 3,
        "version": 2,
        "split_off": [str(second.id), str(third.id)],
    }
    assert separate.result.model_version == "fake-codes 1"
    # The other parts came in as the stack did.
    for number, new in ((2, second), (3, third)):
        assert new.original_filename == f"scan_2026-11-10 ({number}).pdf"
        assert (new.uploaded_by, new.space_id, new.channel, new.created_at) == (
            owner.id,
            stack.space_id,
            stack.channel,
            stack.created_at,
        )
        assert new.space_confirmed_at is None
    assert split.kind is VersionKind.SPLIT and split.created_by is None
    assert (split.detail["document"], split.detail["title"], split.detail["version"]) == (
        str(stack.id),
        "scan_2026-11-10",
        1,
    )
    assert pages_of(split.detail) == [4, 5]
    assert split.detail["stack_pages"] == 8
    assert received_log[0].result.output[SPLIT_FROM] == str(stack.id)
    # Each is processed as any new one, green where all is sure: no inbox for a new version.
    for document in (first, second, third):
        assert document.processing.status is ProcessingStatus.COMPLETED
        assert not document.processing.new_version and document.lane is Lane.GREEN
    # The parts are not looked through again, and say so.
    assert reader.calls and len(reader.calls) == 1
    assert await separation(world, third.id) == {
        "not_looked": "part",
        "from": str(stack.id),
        "title": "scan_2026-11-10",
        "pages": [7, 8],
        "sheets": [3, 6],
        "stack_pages": 8,
    }
    assert await not_looked(world, second.id) == "part"


async def test_the_parts_keep_the_space_a_person_chose(world: World) -> None:
    owner = await world.user(role=Role.ADMIN)
    space = await world.spaces.create(owner.id, "Office")
    pipeline = separating(world, sheets(5))
    stack = await pipeline.receive(
        owner.id, incoming(STACK), filename="scan_2026-11-10.pdf", space=space.id
    )
    await world.drain(pipeline)
    _, part = await documents(world)
    assert part.space_id == space.id and part.space_confirmed_at is not None
    async with world.uow() as uow:
        log = await uow.processing_log.list_for(part.id)
    (choice,) = [entry for entry in log if entry.result.model_version == PERSON_SPACE]
    assert choice.result.input["actor"] == str(stack.uploaded_by)


async def test_the_parts_of_a_mailed_stack_keep_its_mail(world: World) -> None:
    owner = await world.user()
    pipeline = separating(world, sheets(4))
    stack = await pipeline.receive(
        owner.id, incoming(STACK), filename="scans.pdf", channel=Channel.MAIL
    )
    origin = MailOrigin(
        document_id=stack.id,
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
        filename="scans.pdf",
    )
    async with world.uow() as uow:
        await uow.mail_origins.add(origin)
        await uow.commit()
    await world.drain(pipeline)
    _, part = await documents(world)
    assert part.channel is Channel.MAIL
    async with world.uow() as uow:
        assert await uow.mail_origins.find(part.id) == replace(origin, document_id=part.id)


async def test_a_stack_without_a_sheet_stays_as_it_is(world: World) -> None:
    reader = sheets(3, text="K-20047718")
    _, stack = await received(world, reader)
    (document,) = await documents(world)
    assert document.sha256 == stack.sha256
    async with world.uow() as uow:
        (version,) = await uow.document_versions.of_document(stack.id)
        log = await uow.processing_log.list_for(stack.id)
    assert version.kind is VersionKind.RECEIVED
    (separate,) = [entry for entry in log if entry.node is Node.SEPARATE]
    assert separate.result.outcome is Outcome.OK
    assert separate.result.output == {
        "sheets": [],
        "pages": 8,
        "separators": ["PATCHT"],
        "codes": [{"page": 3, "format": "Code 128", "separator": False}],
    }


async def test_a_stack_of_nothing_but_sheets_waits_in_the_inbox(world: World) -> None:
    _, stack = await received(world, sheets(1, 2), fake_pdf(2, "two sheets"))
    (document,) = await documents(world)
    assert document.sha256 == stack.sha256
    assert document.processing.outcome(Node.SEPARATE) is Outcome.UNCERTAIN
    assert document.processing.status is ProcessingStatus.REVIEW
    async with world.uow() as uow:
        log = await uow.processing_log.list_for(stack.id)
    (separate,) = [entry for entry in log if entry.node is Node.SEPARATE]
    assert [reason.code for reason in separate.result.reasons] == [ReasonCode.ONLY_SEPARATOR_SHEETS]


async def test_no_sheets_are_looked_for_without_codes_or_in_a_migration(world: World) -> None:
    reader = sheets(3)
    _, off = await received(world, reader, separators=())
    _, taken = await received(world, reader, fake_pdf(4, "taken over"), channel=Channel.MIGRATION)
    assert reader.calls == []
    assert all(len(document.processing.outcomes) for document in await documents(world))
    assert [await not_looked(world, item.id) for item in (off, taken)] == ["off", "migration"]


async def test_a_new_version_is_not_split(world: World) -> None:
    reader = sheets(3)
    owner, stack = await received(world, reader, separators=())
    pipeline = separating(world, reader)
    await pipeline.new_version(owner.id, stack.id, incoming(fake_pdf(5, "new")), filename="new.pdf")
    await world.drain(pipeline)
    assert reader.calls == []
    async with world.uow() as uow:
        versions = await uow.document_versions.of_document(stack.id)
    assert [version.kind for version in versions] == [VersionKind.RECEIVED, VersionKind.REPLACED]
    assert await not_looked(world, stack.id) == "new_version"


async def test_pages_a_person_split_off_and_a_mail_are_not_looked_through(world: World) -> None:
    reader = sheets(1)
    owner, stack = await received(world, reader, fake_pdf(3, "three pages"), separators=())
    pipeline = separating(world, reader)
    result = await world.editing.edit(
        owner.id,
        stack.id,
        [EditPart((PagePick(0, 1),), replaces=True), EditPart((PagePick(0, 2), PagePick(0, 3)))],
    )
    mail = b"From: a@example.org\r\nSubject: Hi\r\n\r\nHello\r\n"
    letter = await pipeline.receive(owner.id, incoming(mail), filename="m.eml")
    await world.drain(pipeline)
    assert reader.calls == []
    edited, split = result.documents
    assert await separation(world, edited.document.id) == {
        "not_looked": "new_version",
        "version": 2,
        "kind": "edited",
    }
    assert await separation(world, split.document.id) == {
        "not_looked": "split",
        "from": str(stack.id),
        "title": stack.title,
    }
    assert await not_looked(world, letter.id) == "mail"


async def test_separating_is_not_processed_again(world: World) -> None:
    owner, stack = await received(world, sheets(3), separators=())
    with pytest.raises(InvalidTransitionError) as raised:
        await world.pipeline().reprocess_from(owner.id, stack.id, Node.SEPARATE)
    assert raised.value.reason.code is ReasonCode.SEPARATE_NOT_REPEATABLE


class DeletedMeanwhile:
    """Separates, then the stack is deleted before the result is stored."""

    def __init__(self, world: World, node: SeparateNode, actor: User) -> None:
        self._world, self._node, self._actor = world, node, actor
        self.parts: list[str] = []

    async def run(self, document: Document) -> NodeResult | Separation:
        result = await self._node.run(document)
        assert isinstance(result, Separation)
        self.parts = [original_key(part.file.sha256) for part in result.parts]
        await self._world.documents.delete(self._actor.id, document.id)
        return result


async def test_the_parts_files_go_if_the_stack_is_deleted_first(world: World) -> None:
    owner = await world.user(role=Role.ADMIN)
    node = SeparateNode(
        world.uow,
        world.object_store,
        sheets(4),
        world.composer,
        separators=("PATCHT",),
        pipeline_version="test",
    )
    deleting = DeletedMeanwhile(world, node, owner)
    pipeline = world.pipeline(executors={Node.SEPARATE: deleting})
    await pipeline.receive(owner.id, incoming(STACK), filename="scan.pdf")
    await world.drain(pipeline)
    assert len(deleting.parts) == 2
    for key in deleting.parts:
        assert not await world.object_store.exists(key)
    assert await documents(world) == []
