"""In-memory mailbox repository, on the tables of the in-memory unit of work."""

from lekto.adapters.outbound.memory.rows import MemoryRepository, _copy
from lekto.core.domain.ids import MailboxId
from lekto.core.domain.mail import Mailbox
from lekto.core.domain.validation import name_key


class MemoryMailboxRepository(MemoryRepository[MailboxId, Mailbox]):
    async def list_all(self) -> list[Mailbox]:
        return [_copy(row) for row in sorted(self._all(), key=lambda row: name_key(row.name))]
