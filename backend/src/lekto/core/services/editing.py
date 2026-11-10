"""Editing a document's pages (`domain.editing`; `.idea/umsetzungsplan.md`, "Fassungen, Datei
ersetzen, PDF bearbeiten"): the parts are put together from the document's original and the
files a person adds, and stored in one transaction. The part that replaces the document becomes
its next version (as `PipelineService.add_version`); every other part becomes a new document in
its space, with the uploader, channel and receipt of the document it was split off; without a
part that replaces it, the document is deleted (as `DocumentService.delete`). Each of them runs
anew and waits in the inbox (`Processing.new_version`).

The parts' files are stored before the transaction. Every one is new (the composer makes each
file unique), so no other document names it and the removal of a deleted document's files never
takes one; if the transaction fails, they are removed again.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lekto.core.domain import media_types
from lekto.core.domain.documents import Document, Sha256, file_title
from lekto.core.domain.editing import MAX_ADDED, EditPart, check_parts
from lekto.core.domain.errors import (
    ConcurrencyError,
    InvalidTransitionError,
    UnsupportedMediaTypeError,
    ValidationError,
)
from lekto.core.domain.ids import DocumentId, UserId
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.pipeline import (
    TRIGGER_EDIT,
    Node,
    NodeResult,
    NodeRun,
    Outcome,
    ProcessingStatus,
)
from lekto.core.domain.reasons import Action, ReasonCode, because
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.ports.clock import Clock
from lekto.core.ports.composer import PageComposer, PageSource
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.pages import PageRenderer
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import access_to, controllable_document, load_actor
from lekto.core.services._jobs import enqueue_nodes
from lekto.core.services.documents import DocumentView, delete_document
from lekto.core.services.nodes import work_directory
from lekto.core.services.objects import derivative_keys, original_key
from lekto.core.services.pipeline import VERSION_MEDIA_TYPES, IncomingFile
from lekto.core.services.rules.running import space_choice
from lekto.core.services.tasks.settling import cancel_tasks

log = logging.getLogger(__name__)

SPLIT_FROM = "split_from"
"""Key of the document a part was split off, in the output of its receive node."""


@dataclass(frozen=True)
class AddedFile:
    """A file a person adds to an edit, in a local temporary location, with its name."""

    file: IncomingFile
    filename: str


@dataclass(frozen=True)
class EditResult:
    """The documents an edit leaves, in the order of the parts: the edited one where a part
    replaces it, a new one for each other part. `deleted`: no part replaced the document, and
    it is gone."""

    documents: tuple[DocumentView, ...]
    deleted: bool


@dataclass(frozen=True)
class _Part:
    part: EditPart
    file: IncomingFile


class EditingService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        clock: Clock,
        object_store: ObjectStore,
        composer: PageComposer,
        thumbnails: PageRenderer,
        *,
        pipeline_version: str,
    ) -> None:
        """`thumbnails`: renders the small pages of a file a person is about to add."""
        self._uow = uow
        self._clock = clock
        self._store = object_store
        self._composer = composer
        self._thumbnails = thumbnails
        self._version = pipeline_version

    async def preview(self, actor: UserId, id: DocumentId, file: IncomingFile) -> list[bytes]:
        """Editors and admins, before they add `file` to an edit of the document: its pages as
        small WebP images, in their order; nothing is stored. UnsupportedMediaTypeError unless
        a PDF or an image; UnprocessableDocumentError if its pages cannot be read."""
        kind = await _kind(file.path)
        async with self._uow() as uow:
            user = await load_actor(uow, actor)
            await controllable_document(uow, user, id, Action.EDIT_PAGES)
        async with work_directory() as work:
            target = work / "pages"
            await asyncio.to_thread(target.mkdir)
            rendered = await self._thumbnails.render_pages(
                file.path, media_type=kind, target=target
            )
            return [
                await asyncio.to_thread((target / f"{number}.webp").read_bytes)
                for number in range(1, rendered.pages + 1)
            ]

    async def edit(
        self,
        actor: UserId,
        id: DocumentId,
        parts: Sequence[EditPart],
        added: Sequence[AddedFile] = (),
    ) -> EditResult:
        """Editors and admins: make `parts` of the document's pages and the pages of `added`
        (sources 1, 2, … in their order), and store them (see the module). ValidationError for
        parts that do not fit the pages (`check_parts`) or more than `MAX_ADDED` files;
        UnsupportedMediaTypeError for an added file that is no PDF or image, and for a mail,
        whose pages are not a file; UnprocessableDocumentError for a file whose pages cannot
        be read; InvalidTransitionError while the document is processed; ConcurrencyError if
        its file changed meanwhile."""
        if len(added) > MAX_ADDED:
            raise ValidationError(f"files: at most {MAX_ADDED}")
        kinds = [await _kind(item.file.path) for item in added]
        async with self._uow() as uow:
            user = await load_actor(uow, actor)
            document, _ = await controllable_document(uow, user, id, Action.EDIT_PAGES)
            _require_editable(document)
        async with work_directory() as work:
            original = work / "original"
            await self._store.download(original_key(document.sha256), original)
            sources = [
                PageSource(original, document.media_type),
                *(
                    PageSource(item.file.path, kind)
                    for item, kind in zip(added, kinds, strict=True)
                ),
            ]
            counts = [await self._composer.count_pages(source) for source in sources]
            check_parts(parts, counts)
            made = []
            for number, part in enumerate(parts, start=1):
                target = work / f"part-{number}.pdf"
                await self._composer.compose(sources, part.pages, target)
                made.append(_Part(part, await asyncio.to_thread(IncomingFile.of, target)))
            for item in made:
                key = original_key(item.file.sha256)
                await self._store.upload(key, item.file.path, content_type=media_types.PDF)
            try:
                result = await self._store_parts(
                    actor, id, document.sha256, made, [item.filename for item in added]
                )
            except BaseException:
                # Not committed: no document names the parts' files.
                for item in made:
                    await asyncio.shield(self._store.delete(original_key(item.file.sha256)))
                raise
        log.info(
            "pages edited",
            extra={
                "document_id": str(id),
                "parts": len(parts),
                "new_documents": len(parts) - (0 if result.deleted else 1),
                "deleted": result.deleted,
            },
        )
        return result

    async def _store_parts(
        self,
        actor: UserId,
        id: DocumentId,
        sha256: Sha256,
        parts: Sequence[_Part],
        added: Sequence[str],
    ) -> EditResult:
        now = self._clock.now()
        async with self._uow() as uow:
            # Check again: rights, its file or its processing may have changed meanwhile.
            user = await load_actor(uow, actor)
            document, _ = await controllable_document(uow, user, id, Action.EDIT_PAGES)
            if document.sha256 != sha256:
                raise ConcurrencyError("the document's file changed while its pages were edited")
            _require_editable(document)
            versions = await uow.document_versions.of_document(id)
            current = max((version.number for version in versions), default=1)
            created: list[Document] = []
            for number, item in enumerate(parts, start=1):
                if not item.part.replaces:
                    created.append(
                        await self._split_off(uow, actor, document, item, number, current, added)
                    )
            replacing = next((item for item in parts if item.part.replaces), None)
            if replacing is None:
                await delete_document(uow, document, now)
            else:
                detail: JsonObject = {
                    **_pages(replacing.part, added),
                    "from": current,
                    "split_off": [str(new.id) for new in created],
                }
                await self._replace(uow, actor, document, replacing, current, detail, now)
            remaining = iter(created)
            documents = [document if item.part.replaces else next(remaining) for item in parts]
            views = tuple(
                [DocumentView(item, await access_to(uow, user, item)) for item in documents]
            )
            await uow.commit()
        return EditResult(documents=views, deleted=replacing is None)

    async def _split_off(
        self,
        uow: UnitOfWork,
        actor: UserId,
        source: Document,
        item: _Part,
        number: int,
        current: int,
        added: Sequence[str],
    ) -> Document:
        """A new document of the part `number`, in the source's space; a person chose that."""
        now = self._clock.now()
        file = item.file
        result = NodeResult(
            outcome=Outcome.OK,
            output={
                "sha256": file.sha256.hex,
                "size": file.size,
                "media_type": media_types.PDF,
                SPLIT_FROM: str(source.id),
            },
        )
        document = Document.receive(
            uploaded_by=source.uploaded_by,
            space_id=source.space_id,
            sha256=file.sha256,
            original_filename=f"{file_title(source.original_filename)} ({number}).pdf",
            media_type=media_types.PDF,
            result=result,
            now=now,
            channel=source.channel,
            received=source.created_at,
            space_chosen=True,
            edited=True,
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
                created_by=actor,
                detail={
                    **_pages(item.part, added),
                    "document": str(source.id),
                    "title": source.title,
                    "version": current,
                },
            )
        )
        await uow.processing_log.append(
            NodeRun(
                document_id=document.id,
                node=Node.RECEIVE,
                run=1,
                result=result,
                pipeline_version=self._version,
                started_at=now,
                duration=now - now,
            )
        )
        await uow.processing_log.append(
            space_choice(
                document,
                node=Node.RECEIVE,
                actor=actor,
                trigger=TRIGGER_EDIT,
                version=self._version,
                now=now,
            )
        )
        await enqueue_nodes(uow, document, document.processing.due(), now)
        await uow.outbox.add(document.pull_events())
        return document

    async def _replace(
        self,
        uow: UnitOfWork,
        actor: UserId,
        document: Document,
        item: _Part,
        current: int,
        detail: JsonObject,
        now: datetime,
    ) -> None:
        """The part as the document's next version (as `PipelineService.add_version`)."""
        pages = document.page_count
        filename = f"{file_title(document.original_filename)}.pdf"
        document.new_version(item.file.sha256, filename, media_types.PDF, now)
        await uow.document_versions.add(
            DocumentVersion(
                document_id=document.id,
                number=current + 1,
                sha256=item.file.sha256,
                original_filename=document.original_filename,
                media_type=media_types.PDF,
                kind=VersionKind.EDITED,
                created_at=now,
                created_by=actor,
                detail=detail,
            )
        )
        for derivative in derivative_keys(document.id, pages):
            await self._store.delete(derivative)
        await cancel_tasks(uow, document.id, now)
        await uow.documents.update(document)
        await enqueue_nodes(uow, document, document.processing.due(), now)
        await uow.outbox.add(document.pull_events())


def _require_editable(document: Document) -> None:
    """InvalidTransitionError while the document is processed; UnsupportedMediaTypeError for a
    mail, whose pages are set from it, not a file of pages."""
    if document.processing.status is ProcessingStatus.PROCESSING:
        raise InvalidTransitionError(because(ReasonCode.BEING_PROCESSED, id=str(document.id)))
    if document.media_type not in VERSION_MEDIA_TYPES:
        raise UnsupportedMediaTypeError("the pages of a mail cannot be edited")


async def _kind(path: Path) -> str:
    """The media type of an added file; UnsupportedMediaTypeError unless a PDF or an image."""
    head = await asyncio.to_thread(_head, path)
    kind = media_types.detect(head)
    if kind is None or kind not in VERSION_MEDIA_TYPES:
        raise UnsupportedMediaTypeError(
            f"unsupported file type; supported: {', '.join(VERSION_MEDIA_TYPES)}"
        )
    return kind


def _head(path: Path) -> bytes:
    with path.open("rb") as file:
        return file.read(media_types.SNIFF_SIZE)


def _pages(part: EditPart, added: Sequence[str]) -> JsonObject:
    """What a version's detail says of the pages it was made of: each page's source (0 the
    edited version, 1, 2, … the files in `added`), page and turn."""
    return {"pages": [pick.to_json() for pick in part.pages], "added": list(added)}
