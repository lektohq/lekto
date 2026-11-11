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
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import datetime

from lekto.core.domain import media_types
from lekto.core.domain.codes import Code
from lekto.core.domain.documents import Channel, Document
from lekto.core.domain.editing import ORIGINAL, PagePick
from lekto.core.domain.ids import UserId
from lekto.core.domain.json_value import JsonObject, JsonValue
from lekto.core.domain.pipeline import (
    TRIGGER_UPLOAD,
    NodeResult,
    Outcome,
    ProcessingHistory,
)
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.separating import is_separator, separated_parts, separator_pages
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.ports.codes import CodeReader
from lekto.core.ports.composer import PageComposer, PageSource
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._intake import store_part
from lekto.core.services.nodes import ORIGINAL_FILE, work_directory
from lekto.core.services.objects import original_key
from lekto.core.services.pipeline import VERSION_MEDIA_TYPES, IncomingFile

log = logging.getLogger(__name__)

SHEETS = "sheets"
"""Key of the pages that were separator sheets, in the node's output and the detail of the
versions it made."""
SPLIT_OFF = "split_off"
"""Key of the documents made of the parts after the first, in the node's output and the detail
of the stack's version 2 (as `EditingService` writes it)."""
SEPARATORS = "separators"
"""Key of the separator codes looked for, in the node's output."""
CODES = "codes"
"""Key of the codes read on the pages, in the node's output: each with its `page`, `format` and
whether it is a separator sheet's (`separator`), once per page and format; not their text, which
may be anything (a payment's QR code)."""
STACK_PAGES = "stack_pages"
"""Key of how many pages the stack had, in the detail of a part's version and in the output of
its run."""
NOT_LOOKED = "not_looked"
"""Key of why the node did not look for sheets, in its output: `off` (no separator codes), `mail`
(an e-mail), `migration`, `new_version` (with the `version` and its `kind`), `part` (a part of a
stack split at its sheets: `from` and `title` name the stack, `pages` are its pages there, with
the stack's `sheets` and `stack_pages`) or `split` (pages a person split off another document:
`from` and `title`)."""


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
            return NodeResult(outcome=Outcome.OK, output=not_looked)
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
            found: JsonObject = {
                SHEETS: list(sheets),
                "pages": pages,
                SEPARATORS: [code for code in sorted(self._separators)],
                CODES: _codes(reading.codes, self._separators),
            }
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
                found=found,
            )
            try:
                for part in parts:
                    key = original_key(part.file.sha256)
                    await self._store.upload(key, part.file.path, content_type=media_types.PDF)
            except BaseException:
                await asyncio.shield(separation.discard())
                raise
        return separation

    async def _not_looked(self, document: Document) -> JsonObject | None:
        """Why the node does not look for sheets in the document, as its output (`NOT_LOOKED`);
        None for a stack that came in as it is (see the module)."""
        if not self._separators:
            return {NOT_LOOKED: "off"}
        if document.media_type not in VERSION_MEDIA_TYPES:
            return {NOT_LOOKED: "mail"}
        if document.channel is Channel.MIGRATION:
            return {NOT_LOOKED: "migration"}
        async with self._uow() as uow:
            versions = await uow.document_versions.of_document(document.id)
        if versions and versions[0].kind is VersionKind.SPLIT:
            return _split_from(versions[0].detail)
        if document.processing.new_version or [item.kind for item in versions] != [
            VersionKind.RECEIVED
        ]:
            last = versions[-1] if versions else None
            if last is None:
                return {NOT_LOOKED: "new_version"}
            return {NOT_LOOKED: "new_version", "version": last.number, "kind": last.kind.value}
        return None


def _split_from(detail: JsonObject) -> JsonObject:
    """What the node says of pages split off another document (`NOT_LOOKED`), from the detail of
    their first version: a part of a stack, or pages a person split off."""
    if SHEETS not in detail:
        return {NOT_LOOKED: "split", "from": detail.get("document"), "title": detail.get("title")}
    picks = detail.get("pages")
    pages = (
        [pick.get("page") for pick in picks if isinstance(pick, dict)]
        if isinstance(picks, list)
        else []
    )
    return {
        NOT_LOOKED: "part",
        "from": detail.get("document"),
        "title": detail.get("title"),
        "pages": pages,
        SHEETS: detail.get(SHEETS),
        STACK_PAGES: detail.get(STACK_PAGES),
    }


def _codes(codes: Iterable[Code], separators: Collection[str]) -> list[JsonValue]:
    """The codes read (`CODES`), by page."""
    seen = sorted({(code.page, code.format, is_separator(code.text, separators)) for code in codes})
    return [{"page": page, "format": kind, "separator": sheet} for page, kind, sheet in seen]


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
    # What the node found (`SHEETS`, `SEPARATORS`, `CODES`), for its output.
    found: JsonObject

    async def apply(self, uow: UnitOfWork, document: Document, now: datetime) -> NodeResult:
        first, *others = self.parts
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
                **self.found,
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
        """A new document of the part `number`, as the stack came in (`store_part`), its space
        chosen by `chooser`, if a person chose it."""
        return await store_part(
            uow,
            stack,
            part.file.sha256,
            part.file.size,
            number=number,
            detail={
                "pages": [pick.to_json() for pick in part.picks()],
                "added": [],
                "document": str(stack.id),
                "title": stack.title,
                "version": 1,
                SHEETS: list(self.sheets),
                STACK_PAGES: self.pages,
            },
            created_by=None,
            chooser=chooser,
            trigger=TRIGGER_UPLOAD,
            edited=False,
            pipeline_version=self.pipeline_version,
            now=now,
        )
