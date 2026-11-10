"""The versions of each document's original, in `document_versions`."""

from typing import Any

from sqlalchemy import Row, insert, select

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.transaction import Transaction
from lekto.core.domain.documents import Sha256
from lekto.core.domain.ids import DocumentId, UserId
from lekto.core.domain.versions import DocumentVersion, VersionKind


class SqlDocumentVersionRepository:
    def __init__(self, transaction: Transaction) -> None:
        self._tx = transaction

    async def add(self, version: DocumentVersion) -> None:
        # A number or file taken already: the transaction's ConflictError.
        await self._tx.write(insert(t.document_versions), [_row(version)])

    async def of_document(self, document: DocumentId) -> list[DocumentVersion]:
        table = t.document_versions
        rows = await self._tx.read(
            select(table).where(table.c.document_id == document).order_by(table.c.number)
        )
        return [_version(row) for row in rows]

    async def find_by_sha256(self, sha256: Sha256) -> DocumentVersion | None:
        table = t.document_versions
        rows = list(await self._tx.read(select(table).where(table.c.sha256 == sha256.hex)))
        return _version(rows[0]) if rows else None


def _row(version: DocumentVersion) -> dict[str, Any]:
    return {
        "document_id": version.document_id,
        "number": version.number,
        "sha256": version.sha256.hex,
        "original_filename": version.original_filename,
        "media_type": version.media_type,
        "kind": version.kind.value,
        "created_at": version.created_at,
        "created_by": version.created_by,
        "detail": dict(version.detail),
    }


def _version(row: Row[Any]) -> DocumentVersion:
    return DocumentVersion(
        document_id=DocumentId(row.document_id),
        number=row.number,
        sha256=Sha256(row.sha256),
        original_filename=row.original_filename,
        media_type=row.media_type,
        kind=VersionKind(row.kind),
        created_at=row.created_at,
        created_by=None if row.created_by is None else UserId(row.created_by),
        detail=dict(row.detail or {}),
    )
