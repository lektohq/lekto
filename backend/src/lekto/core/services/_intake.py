"""How a document, or a new version of its original, comes in, whichever way it does
(`PipelineService` receives a file and replaces one, `EditingService` splits a document's pages
off and merges documents, `services.separating` splits a stack at its sheets): one place for
each, so that a change of how a document comes in reaches every way."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime

from lekto.core.domain import media_types
from lekto.core.domain.documents import Document, Sha256
from lekto.core.domain.identity import ViaToken
from lekto.core.domain.ids import UserId
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.pipeline import TRIGGER_UPLOAD, Node, NodeResult, NodeRun, Outcome
from lekto.core.domain.versions import DocumentVersion, VersionKind
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.unit_of_work import UnitOfWork
from lekto.core.services._jobs import enqueue_nodes
from lekto.core.services.objects import derivative_keys
from lekto.core.services.rules.running import space_choice
from lekto.core.services.tasks.settling import cancel_tasks

SPLIT_FROM = "split_from"
"""Key of the document a part was split off, in the output of its receive node."""


async def store_received(
    uow: UnitOfWork,
    document: Document,
    version: DocumentVersion,
    result: NodeResult,
    *,
    pipeline_version: str,
    started: datetime,
    now: datetime,
    chooser: UserId | None = None,
    trigger: str = TRIGGER_UPLOAD,
    via: ViaToken | None = None,
) -> None:
    """Store `document`, which came in (`Document.receive` with the receive node's `result`,
    begun at `started`), with its first `version`: the receive in its log, where a person chose
    its space the choice of `chooser` (through `trigger`, the API token `via`), the jobs of its
    first run and its events."""
    await uow.documents.add(document)
    await uow.document_versions.add(version)
    await uow.processing_log.append(
        NodeRun(
            document_id=document.id,
            node=Node.RECEIVE,
            run=1,
            result=result,
            pipeline_version=pipeline_version,
            started_at=started,
            duration=now - started,
        )
    )
    if chooser is not None:
        await uow.processing_log.append(
            space_choice(
                document,
                node=Node.RECEIVE,
                actor=chooser,
                trigger=trigger,
                version=pipeline_version,
                now=now,
                via=via,
            )
        )
    await enqueue_nodes(uow, document, document.processing.due(), now)
    await uow.outbox.add(document.pull_events())


async def store_part(
    uow: UnitOfWork,
    source: Document,
    sha256: Sha256,
    size: int,
    *,
    number: int,
    detail: JsonObject,
    created_by: UserId | None,
    chooser: UserId | None,
    trigger: str,
    edited: bool,
    pipeline_version: str,
    now: datetime,
) -> Document:
    """A new document of pages split off `source`, its file a PDF (`sha256`, `size`) named after
    the source's as its part `number`: as the source came in (its uploader, space, channel,
    receipt, and the mail it came with), its version 1 `split` with `detail`, by `created_by`.
    `chooser`: who chose its space, the source's (through `trigger`); none where rules may.
    `edited`: a person put its pages together, and its run ends in the inbox."""
    result = NodeResult(
        outcome=Outcome.OK,
        output={
            "sha256": sha256.hex,
            "size": size,
            "media_type": media_types.PDF,
            SPLIT_FROM: str(source.id),
        },
    )
    document = Document.receive(
        uploaded_by=source.uploaded_by,
        space_id=source.space_id,
        sha256=sha256,
        original_filename=f"{source.file_title} ({number}).pdf",
        media_type=media_types.PDF,
        result=result,
        now=now,
        channel=source.channel,
        received=source.created_at,
        space_chosen=chooser is not None,
        edited=edited,
    )
    version = DocumentVersion(
        document_id=document.id,
        number=1,
        sha256=sha256,
        original_filename=document.original_filename,
        media_type=media_types.PDF,
        kind=VersionKind.SPLIT,
        created_at=now,
        created_by=created_by,
        detail=detail,
    )
    await store_received(
        uow,
        document,
        version,
        result,
        pipeline_version=pipeline_version,
        started=now,
        now=now,
        chooser=chooser,
        trigger=trigger,
    )
    mail = await uow.mail_origins.find(source.id)
    if mail is not None:
        await uow.mail_origins.add(replace(mail, document_id=document.id))
    return document


async def store_new_version(
    uow: UnitOfWork,
    document: Document,
    sha256: Sha256,
    *,
    filename: str,
    media_type: str,
    kind: VersionKind,
    created_by: UserId,
    detail: JsonObject,
    now: datetime,
) -> list[str]:
    """Make the file `sha256` the document's original as its next version, numbered after its
    last (`Document.new_version`), and start its run anew: the tasks of the runs before end.

    Returns the keys of the earlier version's derivatives. The caller deletes them
    (`delete_derivatives`) when nothing but the commit is left to fail: before, a failed
    transaction would leave the document as it was without its archive, text and pages; after,
    the new run's jobs would be seen, and page images beyond the new page count stay."""
    versions = await uow.document_versions.of_document(document.id)
    pages = document.page_count
    document.new_version(sha256, filename, media_type, now)
    await uow.document_versions.add(
        DocumentVersion(
            document_id=document.id,
            number=max((version.number for version in versions), default=0) + 1,
            sha256=sha256,
            original_filename=document.original_filename,
            media_type=media_type,
            kind=kind,
            created_at=now,
            created_by=created_by,
            detail=detail,
        )
    )
    await cancel_tasks(uow, document.id, now)
    await uow.documents.update(document)
    await enqueue_nodes(uow, document, document.processing.due(), now)
    await uow.outbox.add(document.pull_events())
    return derivative_keys(document.id, pages)


async def delete_derivatives(store: ObjectStore, keys: Sequence[str]) -> None:
    """Delete the derivatives `store_new_version` returned."""
    for key in keys:
        await store.delete(key)
