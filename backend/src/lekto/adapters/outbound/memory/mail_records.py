"""In-memory mail records and mail origins, on the tables of the in-memory unit of work."""

from lekto.adapters.outbound.memory.database import DOCUMENTS
from lekto.adapters.outbound.memory.rows import MemoryRepository, _copy
from lekto.core.domain.ids import DocumentId, MailboxId, MailRecordId
from lekto.core.domain.mail_intake import MailOrigin, MailRecord


class MemoryMailRecordRepository(MemoryRepository[MailRecordId, MailRecord]):
    async def known_uids(self, mailbox: MailboxId, folder: str, uidvalidity: int) -> set[int]:
        return {
            row.uid
            for row in self._all()
            if (row.mailbox_id, row.folder, row.uidvalidity) == (mailbox, folder, uidvalidity)
        }

    async def has_message(self, message_id: str) -> bool:
        return any(row.message_id == message_id for row in self._all())

    async def recent(self, mailbox: MailboxId, *, limit: int) -> list[MailRecord]:
        rows = [row for row in self._all() if row.mailbox_id == mailbox]
        rows.sort(key=lambda row: (row.fetched_at, row.id), reverse=True)
        return [_copy(row) for row in rows[:limit]]


class MemoryMailOriginRepository(MemoryRepository[DocumentId, MailOrigin]):
    """An origin goes with its document, as the foreign key's cascade does."""

    async def find(self, document: DocumentId) -> MailOrigin | None:
        if self._uow._row(DOCUMENTS, document) is None:
            return None
        return await super().find(document)

    async def of_record(self, record: MailRecordId) -> list[MailOrigin]:
        rows = [
            row
            for row in self._all()
            if row.record_id == record and self._uow._row(DOCUMENTS, row.document_id) is not None
        ]
        rows.sort(key=lambda row: (row.letter, row.role != "cover", row.document_id))
        return [_copy(row) for row in rows]
