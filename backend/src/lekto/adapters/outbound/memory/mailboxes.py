"""In-memory mailbox repository, on the tables of the in-memory unit of work."""

from lekto.adapters.outbound.memory.database import MAIL_RECORDS
from lekto.adapters.outbound.memory.rows import _REMOVED, MemoryRepository, _copy
from lekto.core.domain.ids import MailboxId
from lekto.core.domain.mail import Mailbox
from lekto.core.domain.validation import name_key


class MemoryMailboxRepository(MemoryRepository[MailboxId, Mailbox]):
    async def list_all(self) -> list[Mailbox]:
        return [_copy(row) for row in sorted(self._all(), key=lambda row: name_key(row.name))]

    async def remove(self, id: MailboxId) -> None:
        """Its records go with it, as the foreign key's cascade does."""
        await super().remove(id)
        for record in self._uow._rows(MAIL_RECORDS):
            if record.mailbox_id == id:
                self._uow._write(MAIL_RECORDS, record.id, _REMOVED)
