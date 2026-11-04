"""In-memory mail rule repository, on the tables of the in-memory unit of work."""

from lekto.adapters.outbound.memory.rows import MemoryRepository, _copy
from lekto.core.domain.ids import MailboxId, MailRuleId
from lekto.core.domain.mail_rules import MailRule


class MemoryMailRuleRepository(MemoryRepository[MailRuleId, MailRule]):
    async def of_mailbox(self, mailbox: MailboxId) -> list[MailRule]:
        return [rule for rule in await self.list_all() if rule.mailbox_id == mailbox]

    async def list_all(self) -> list[MailRule]:
        rows = sorted(
            self._all(),
            key=lambda rule: (str(rule.mailbox_id), -rule.priority, rule.name.casefold(), rule.id),
        )
        return [_copy(row) for row in rows]
