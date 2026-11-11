"""The node `separate` (`domain.separating`; `.idea/umsetzungsplan.md`, "Trennblatt und
Zusammenführen"): a scanned stack is split at its separator sheets when it comes in, before OCR
and the page images read it.

It looks for sheets only in a document that came in as it is, in the run it came in with: not
one taken over from another system (the migration splits before), not after a new version (the
node runs again then, as every node after receiving, and is done at once), not pages split off
another document, and not a mail. A person cannot process it again (`Document.reprocess_from`),
but a retry after it failed runs it again. It reads the codes of every page of the original (an
image's frames put together as a PDF first). Without a sheet it is done.

Otherwise the parts are put together as PDFs (as `EditingService` does) and their files stored;
when the node's result is stored, so is the rest: the document keeps the stack as version 1 and
gets the first part as version 2 (`VersionKind.SEPARATED`), and every other part becomes a new
document with the uploader, space, channel, receipt and mail of the stack (`VersionKind.SPLIT`),
processed as any new one. A stack of nothing but sheets stays as it is, and the document waits
in the inbox. If the stack is deleted before the result is stored, the parts' files go again.
"""

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass, replace
from datetime import datetime

from lekto.core.domain import media_types
from lekto.core.domain.documents import Channel, Document
from lekto.core.domain.editing import ORIGINAL, PagePick
from lekto.core.domain.ids import UserId
from lekto.core.domain.json_value import JsonObject, JsonValue
from lekto.core.domain.pipeline import (
    TRIGGER_UPLOAD,
    Node,
    NodeResult,
    NodeRun,
    Outcome,
    ProcessingHistory,
)
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.separating import separated_parts, separator_pages
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.ports.codes import CodeReader
from lekto.core.ports.composer import PageComposer, PageSource
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._jobs import enqueue_nodes
from lekto.core.services.editing import SPLIT_FROM
from lekto.core.services.nodes import ORIGINAL_FILE, work_directory
from lekto.core.services.objects import original_key
from lekto.core.services.pipeline import VERSION_MEDIA_TYPES, IncomingFile
from lekto.core.services.rules.running import space_choice

log = logging.getLogger(__name__)

SHEETS = "sheets"
"""Key of the pages that were separator sheets, in the node's output and the detail of the
versions it made."""
SPLIT_OFF = "split_off"
"""Key of the documents made of the parts after the first, in the node's output and the detail
of the stack's version 2 (as `EditingService` writes it)."""
NOT_LOOKED = "not_looked"
"""Key of why the node did not look for sheets, in its output: `off` (no separator codes), `mail`
(an e-mail), `migration`, `new_version`, `part` (a part of a stack split at its sheets) or
`split` (pages a person split off another document)."""


@dataclass(frozen=True)
class _Part:
    pages: tuple[int, ...]
    file: IncomingFile

    def picks(self) -> list[PagePick]:
        return [PagePick(ORIGINAL, page) for page in self.pages]


class SeparateNode:
    """Looks for separator sheets with the codes `separators` (none: it never looks)."""

    def __init__(
        self,
        uow: UnitOfWorkFactory,
        store: ObjectStore,
        codes: CodeReader,
        composer: PageComposer,
        *,
        separators: Collection[str],
        pipeline_version: str,
    ) -> None:
        self._uow = uow
        self._store = store
        self._codes = codes
        self._composer = composer
        self._separators = frozenset(separators)
        self._version = pipeline_version

    async def run(self, document: Document) -> "NodeResult | Separation":
        not_looked = await self._not_looked(document)
        if not_looked is not None:
            return NodeResult(outcome=Outcome.OK, output={NOT_LOOKED: not_looked})
        async with work_directory() as work:
            original = work / ORIGINAL_FILE
            await self._store.download(original_key(document.sha256), original)
            source = PageSource(original, document.media_type)
            pages = await self._composer.count_pages(source)
            stack = original
            if document.media_type != media_types.PDF:
                stack = work / "stack.pdf"
                every = [PagePick(ORIGINAL, page) for page in range(1, pages + 1)]
                await self._composer.compose([source], every, stack)
            reading = await self._codes.read_codes(stack, every_page=True)
            sheets = separator_pages(
                ((code.page, code.text) for code in reading.codes), self._separators
            )
            found: JsonObject = {SHEETS: list(sheets), "pages": pages}
            if not sheets:
                return NodeResult(outcome=Outcome.OK, model_version=reading.reader, output=found)
            pieces = separated_parts(pages, sheets)
            if not pieces:
                return NodeResult(
                    outcome=Outcome.UNCERTAIN,
                    reasons=(because(ReasonCode.ONLY_SEPARATOR_SHEETS),),
                    model_version=reading.reader,
                    output=found,
                )
            parts = []
            for number, piece in enumerate(pieces, start=1):
                target = work / f"part-{number}.pdf"
                picks = [PagePick(ORIGINAL, page) for page in piece]
                await self._composer.compose([source], picks, target)
                parts.append(_Part(piece, await asyncio.to_thread(IncomingFile.of, target)))
            separation = Separation(
                store=self._store,
                pipeline_version=self._version,
                reader=reading.reader,
                sheets=tuple(sheets),
                pages=pages,
                parts=tuple(parts),
            )
            try:
                for part in parts:
                    key = original_key(part.file.sha256)
                    await self._store.upload(key, part.file.path, content_type=media_types.PDF)
            except BaseException:
                await asyncio.shield(separation.discard())
                raise
        return separation

    async def _not_looked(self, document: Document) -> str | None:
        """Why the node does not look for sheets in the document (`NOT_LOOKED`); None for a
        stack that came in as it is (see the module)."""
        if not self._separators:
            return "off"
        if document.media_type not in VERSION_MEDIA_TYPES:
            return "mail"
        if document.channel is Channel.MIGRATION:
            return "migration"
        async with self._uow() as uow:
            versions = await uow.document_versions.of_document(document.id)
        first = versions[0] if versions else None
        if first is not None and first.kind is VersionKind.SPLIT:
            return "part" if SHEETS in first.detail else "split"
        kinds = [version.kind for version in versions]
        if document.processing.new_version or kinds != [VersionKind.RECEIVED]:
            return "new_version"
        return None


@dataclass(frozen=True, kw_only=True)
class Separation:
    """The parts of a stack, their files stored: the rest is stored with the node's result
    (`DeferredResult`), or their files go again if that never happens (`Discardable`)."""

    store: ObjectStore
    pipeline_version: str
    reader: str
    sheets: tuple[int, ...]
    pages: int
    parts: tuple[_Part, ...]

    async def apply(self, uow: UnitOfWork, document: Document, now: datetime) -> NodeResult:
        first, *others = self.parts
        mail = await uow.mail_origins.find(document.id)
        history = ProcessingHistory(await uow.processing_log.list_for(document.id))
        # Rules leave the space a person chose on upload; the parts' too.
        chosen = (
            None
            if document.space_confirmed_at is None
            else history.space_chooser(document.space_id)
        )
        chooser = None if chosen is None else UserId(chosen)
        created = [
            await self._split_off(uow, document, part, number, chooser, now)
            for number, part in enumerate(others, start=2)
        ]
        if mail is not None:
            for new in created:
                await uow.mail_origins.add(replace(mail, document_id=new.id))
        versions = await uow.document_versions.of_document(document.id)
        current = max(version.number for version in versions)
        split_off: list[JsonValue] = [str(new.id) for new in created]
        filename = f"{document.file_title}.pdf"
        await uow.document_versions.add(
            DocumentVersion(
                document_id=document.id,
                number=current + 1,
                sha256=first.file.sha256,
                original_filename=filename,
                media_type=media_types.PDF,
                kind=VersionKind.SEPARATED,
                created_at=now,
                detail={
                    "pages": [pick.to_json() for pick in first.picks()],
                    "from": current,
                    SHEETS: list(self.sheets),
                    SPLIT_OFF: split_off,
                },
            )
        )
        document.separate(first.file.sha256, filename, now)
        log.info(
            "stack separated",
            extra={
                "document_id": str(document.id),
                "sheets": len(self.sheets),
                "parts": len(self.parts),
            },
        )
        return NodeResult(
            outcome=Outcome.OK,
            model_version=self.reader,
            output={
                SHEETS: list(self.sheets),
                "pages": self.pages,
                "parts": len(self.parts),
                "version": current + 1,
                SPLIT_OFF: split_off,
            },
        )

    async def discard(self) -> None:
        """Remove the parts' files: no document names them (each is new)."""
        for part in self.parts:
            await self.store.delete(original_key(part.file.sha256))

    async def _split_off(
        self,
        uow: UnitOfWork,
        stack: Document,
        part: _Part,
        number: int,
        chooser: UserId | None,
        now: datetime,
    ) -> Document:
        """A new document of the part `number`, as the stack came in: in its space (chosen by
        `chooser`, if a person chose it), from its uploader, channel and receipt."""
        file = part.file
        result = NodeResult(
            outcome=Outcome.OK,
            output={
                "sha256": file.sha256.hex,
                "size": file.size,
                "media_type": media_types.PDF,
                SPLIT_FROM: str(stack.id),
            },
        )
        document = Document.receive(
            uploaded_by=stack.uploaded_by,
            space_id=stack.space_id,
            sha256=file.sha256,
            original_filename=f"{stack.file_title} ({number}).pdf",
            media_type=media_types.PDF,
            result=result,
            now=now,
            channel=stack.channel,
            received=stack.created_at,
            space_chosen=chooser is not None,
        )
        await uow.documents.add(document)
        await uow.document_versions.add(
            DocumentVersion(
                document_id=document.id,
                number=1,
                sha256=file.sha256,
                original_filename=document.original_filename,
                media_type=media_types.PDF,
                kind=VersionKind.SPLIT,
                created_at=now,
                detail={
                    "pages": [pick.to_json() for pick in part.picks()],
                    "added": [],
                    "document": str(stack.id),
                    "title": stack.title,
                    "version": 1,
                    SHEETS: list(self.sheets),
                },
            )
        )
        await uow.processing_log.append(
            NodeRun(
                document_id=document.id,
                node=Node.RECEIVE,
                run=1,
                result=result,
                pipeline_version=self.pipeline_version,
                started_at=now,
                duration=now - now,
            )
        )
        if chooser is not None:
            await uow.processing_log.append(
                space_choice(
                    document,
                    node=Node.RECEIVE,
                    actor=chooser,
                    trigger=TRIGGER_UPLOAD,
                    version=self.pipeline_version,
                    now=now,
                )
            )
        await enqueue_nodes(uow, document, document.processing.due(), now)
        await uow.outbox.add(document.pull_events())
        return document
