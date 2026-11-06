"""In-memory mail records and mail origins, on the tables of the in-memory unit of work."""

import copy
from datetime import datetime

from lekto.adapters.outbound.memory.database import DOCUMENTS, MAILBOXES
from lekto.adapters.outbound.memory.rows import MemoryRows, _copy
from lekto.core.domain.errors import ConflictError, NotFoundError
from lekto.core.domain.ids import DocumentId, MailboxId, MailRecordId
from lekto.core.domain.mail_intake import SETTLED, MailOrigin, MailRecord


class MemoryMailRecordRepository(MemoryRows[MailRecordId, MailRecord]):
    async def add(self, record: MailRecord) -> None:
        if self._uow._row(MAILBOXES, record.mailbox_id) is None:
            raise ConflictError("mail record: no such mailbox")  # as the foreign key
        await super().add(record)

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

    async def waiting(self, mailbox: MailboxId) -> list[MailRecord]:
        rows = [row for row in self._all() if row.mailbox_id == mailbox and row.waiting]
        rows.sort(key=lambda row: (row.fetched_at, row.id), reverse=True)
        return [_copy(row) for row in rows]

    async def settle(self, record: MailRecord) -> None:
        self._uow._check_open()
        current = self._uow._row(self._table, record.id)
        if current is None:
            raise NotFoundError(self._table.name, record.id)
        changed = _copy(current)
        for name in SETTLED:
            setattr(changed, name, copy.deepcopy(getattr(record, name)))
        self._uow._write(self._table, record.id, changed)

    async def forget_beyond(self, mailbox: MailboxId, *, keep: int, now: datetime) -> int:
        rows = [row for row in self._all() if row.mailbox_id == mailbox]
        rows.sort(key=lambda row: (row.fetched_at, row.id), reverse=True)
        forgotten = 0
        for row in rows[keep:]:
            if row.forgotten_at is None:
                record = _copy(row)
                record.forget(now=now)
                self._uow._write(self._table, record.id, record)
                forgotten += 1
        return forgotten


class MemoryMailOriginRepository(MemoryRows[DocumentId, MailOrigin]):
    """An origin goes with its document, as the foreign key's cascade does."""

    async def add(self, origin: MailOrigin) -> None:
        if self._uow._row(DOCUMENTS, origin.document_id) is None:
            raise ConflictError("mail origin: no such document")  # as the foreign key
        await super().add(origin)

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
