"""Editing a document's pages (`domain.editing`; `.idea/umsetzungsplan.md`, "Fassungen, Datei
ersetzen, PDF bearbeiten"): the parts are put together from the document's original and the
files a person adds, and stored in one transaction. The part that replaces the document becomes
its next version (as `PipelineService.new_version`); every other part becomes a new document in
its space, with the uploader, channel and receipt of the document it was split off; without a
part that replaces it, the document is deleted (as `DocumentService.delete`). Each of them runs
anew and waits in the inbox (`Processing.new_version`).

With the pages of other documents, the edit merges them (Umsetzungsplan "Trennblatt und
Zusammenführen"): one of them, the target, gets the part that replaces it as its next version
(`VersionKind.MERGED`). Every other document goes: its versions become the target's (numbered
after the target's, with where they came from), its relations name the target (one with the
target, or with another of them, goes; one the target has already stays the target's), and it
is deleted as `DocumentService.delete` does. Its files stay, as versions of the target.

The parts' files are stored before the transaction. Every one is new (the composer makes each
file unique), so no other document names it and the removal of a deleted document's files never
takes one; if the transaction fails, they are removed again.
"""

import asyncio
import logging
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from lekto.core.domain import media_types
from lekto.core.domain.documents import Document, Sha256
from lekto.core.domain.editing import MAX_ADDED, MAX_MERGED, EditPart, check_parts
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
    ProcessingStatus,
)
from lekto.core.domain.reasons import Action, ReasonCode, because
from lekto.core.domain.users import User
from lekto.core.domain.versions import VersionKind
from lekto.core.ports.clock import Clock
from lekto.core.ports.composer import PageComposer, PageSource
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.pages import PageRenderer
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import access_to, controllable_document, load_actor
from lekto.core.services._intake import delete_derivatives, store_new_version, store_part
from lekto.core.services.documents import DocumentView, delete_document
from lekto.core.services.nodes import work_directory
from lekto.core.services.objects import original_key
from lekto.core.services.pipeline import VERSION_MEDIA_TYPES, IncomingFile

log = logging.getLogger(__name__)

MOVED = "moved"
"""Key of where a version of a merged document came from (its document, title and number
there), in its detail at the target."""


@dataclass(frozen=True)
class AddedFile:
    """A file a person adds to an edit, in a local temporary location, with its name."""

    file: IncomingFile
    filename: str


@dataclass(frozen=True)
class EditResult:
    """The documents an edit leaves, in the order of the parts: the edited one (the target of a
    merge) where a part replaces it, a new one for each other part. `deleted`: no part replaced
    the document, and it is gone. `merged`: the other documents of a merge, gone, their
    versions the target's."""

    documents: tuple[DocumentView, ...]
    deleted: bool
    merged: tuple[DocumentId, ...] = ()


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
        documents: Sequence[DocumentId] = (),
        target: DocumentId | None = None,
    ) -> EditResult:
        """Editors and admins: make `parts` of the document's pages, the pages of `added`
        (sources 1, 2, … in their order) and those of `documents` (the sources after them),
        and store them (see the module). With `documents`, the part that replaces makes the
        next version of `target`, the document or one of them (the document by default).
        ValidationError for parts that do not fit the pages (`check_parts`; a merge needs a
        part that replaces and a page of every document), more than `MAX_ADDED` files or
        `MAX_MERGED` documents, a document twice (or the document among `documents`), or a
        target that is none of them;
        UnsupportedMediaTypeError for an added file that is no PDF or image, and for a mail,
        whose pages are not a file; UnprocessableDocumentError for a file whose pages cannot
        be read; InvalidTransitionError while one of them is processed; ConcurrencyError if a
        file changed meanwhile. Each document needs the caller's right to edit its pages."""
        if len(added) > MAX_ADDED:
            raise ValidationError(f"files: at most {MAX_ADDED}")
        if len(documents) > MAX_MERGED:
            raise ValidationError(f"documents: at most {MAX_MERGED}")
        involved = (id, *documents)
        if len(set(involved)) != len(involved):
            raise ValidationError("documents: each once, and not the document edited")
        goal = id if target is None else target
        if goal not in involved:
            raise ValidationError("target: the document edited or one of `documents`")
        kinds = [await _kind(item.file.path) for item in added]
        async with self._uow() as uow:
            user = await load_actor(uow, actor)
            found = [await _editable(uow, user, each) for each in involved]
        async with work_directory() as work:
            originals = []
            for number, document in enumerate(found):
                path = work / f"original-{number}"
                await self._store.download(original_key(document.sha256), path)
                originals.append(PageSource(path, document.media_type))
            sources = [
                originals[0],
                *(
                    PageSource(item.file.path, kind)
                    for item, kind in zip(added, kinds, strict=True)
                ),
                *originals[1:],
            ]
            counts = [await self._composer.count_pages(source) for source in sources]
            check_parts(parts, counts, merged=len(documents))
            made = []
            for number, part in enumerate(parts, start=1):
                target_file = work / f"part-{number}.pdf"
                await self._composer.compose(sources, part.pages, target_file)
                made.append(_Part(part, await asyncio.to_thread(IncomingFile.of, target_file)))
            for item in made:
                key = original_key(item.file.sha256)
                await self._store.upload(key, item.file.path, content_type=media_types.PDF)
            try:
                result = await self._store_parts(
                    actor,
                    {document.id: document.sha256 for document in found},
                    goal,
                    made,
                    [item.filename for item in added],
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
                "merged": len(result.merged),
            },
        )
        return result

    async def _store_parts(
        self,
        actor: UserId,
        files: dict[DocumentId, Sha256],
        goal: DocumentId,
        parts: Sequence[_Part],
        added: Sequence[str],
    ) -> EditResult:
        """`files`: the documents edited, the first the one whose pages were edited, each with
        its file then; `goal`: the one the part that replaces makes the next version of."""
        now = self._clock.now()
        async with self._uow() as uow:
            # Check again: rights, their files or their processing may have changed meanwhile.
            user = await load_actor(uow, actor)
            found = []
            for each, sha256 in files.items():
                document, _ = await controllable_document(uow, user, each, Action.EDIT_PAGES)
                if document.sha256 != sha256:
                    raise ConcurrencyError(
                        "the document's file changed while its pages were edited"
                    )
                _require_editable(document)
                found.append(document)
            document = next(item for item in found if item.id == goal)
            others = [item for item in found if item.id != goal]
            versions = await uow.document_versions.of_document(document.id)
            current = max((version.number for version in versions), default=1)
            created: list[Document] = []
            for number, item in enumerate(parts, start=1):
                if not item.part.replaces:
                    created.append(
                        await self._split_off(uow, actor, document, item, number, current, added)
                    )
            replacing = next((item for item in parts if item.part.replaces), None)
            stale: list[str] = []
            if replacing is None:  # not in a merge (`check_parts`)
                await delete_document(uow, document, now)
            else:
                detail: JsonObject = {
                    **_pages(replacing.part, added),
                    "from": current,
                    "split_off": [str(new.id) for new in created],
                }
                if others:
                    taken = await self._take_versions(uow, document, others, current)
                    detail["documents"] = [
                        {
                            "document": str(item.id),
                            "title": item.title,
                            "version": current if item.id == goal else taken[item.sha256],
                        }
                        for item in found
                    ]
                kind = VersionKind.MERGED if others else VersionKind.EDITED
                stale = await self._replace(uow, actor, document, replacing, kind, detail, now)
                going = {item.id for item in others}
                for other in others:
                    await _move_relations(uow, other.id, document.id, going)
                    await delete_document(uow, other, now)
            remaining = iter(created)
            documents = [document if item.part.replaces else next(remaining) for item in parts]
            views = tuple(
                [DocumentView(item, await access_to(uow, user, item)) for item in documents]
            )
            await delete_derivatives(self._store, stale)
            await uow.commit()
        return EditResult(
            documents=views,
            deleted=replacing is None,
            merged=tuple(item.id for item in others),
        )

    async def _take_versions(
        self, uow: UnitOfWork, target: Document, others: Sequence[Document], current: int
    ) -> dict[Sha256, int]:
        """Make the versions of `others` the target's, numbered after `current` in their order;
        returns the number each one's current file has at the target."""
        number = current
        taken: dict[Sha256, int] = {}
        for other in others:
            for version in await uow.document_versions.of_document(other.id):
                number += 1
                moved: JsonObject = {
                    "document": str(other.id),
                    "title": other.title,
                    "version": version.number,
                }
                await uow.document_versions.move(
                    version,
                    replace(
                        version,
                        document_id=target.id,
                        number=number,
                        detail={**version.detail, MOVED: moved},
                    ),
                )
                taken[version.sha256] = number
        return taken

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
        return await store_part(
            uow,
            source,
            item.file.sha256,
            item.file.size,
            number=number,
            detail={
                **_pages(item.part, added),
                "document": str(source.id),
                "title": source.title,
                "version": current,
            },
            created_by=actor,
            chooser=actor,
            trigger=TRIGGER_EDIT,
            edited=True,
            pipeline_version=self._version,
            now=self._clock.now(),
        )

    async def _replace(
        self,
        uow: UnitOfWork,
        actor: UserId,
        document: Document,
        item: _Part,
        kind: VersionKind,
        detail: JsonObject,
        now: datetime,
    ) -> list[str]:
        """The part as the document's next version (as `PipelineService.new_version`); returns
        the keys of the earlier version's derivatives (`store_new_version`)."""
        return await store_new_version(
            uow,
            document,
            item.file.sha256,
            filename=f"{document.file_title}.pdf",
            media_type=media_types.PDF,
            kind=kind,
            created_by=actor,
            detail=detail,
            now=now,
        )


async def _editable(uow: UnitOfWork, user: User, id: DocumentId) -> Document:
    """The document whose pages the user may edit now (`_require_editable`)."""
    document, _ = await controllable_document(uow, user, id, Action.EDIT_PAGES)
    _require_editable(document)
    return document


async def _move_relations(
    uow: UnitOfWork, source: DocumentId, target: DocumentId, going: Collection[DocumentId]
) -> None:
    """The relations of `source`, merged into `target`, name the target from now on, in the
    same direction. One with the target or with another document of the merge (`going`) goes;
    one the target has with the same document already stays the target's."""
    relations = uow.document_relations
    for relation in await relations.of_document(source):
        await relations.remove(relation.newer, relation.older)
        other = relation.other(source)
        if other == target or other in going:
            continue
        if await relations.find(target, other) or await relations.find(other, target):
            continue
        newer, older = (target, other) if relation.newer == source else (other, target)
        await relations.put(replace(relation, newer=newer, older=older))


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
