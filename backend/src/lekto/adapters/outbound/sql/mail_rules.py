"""Mail rule repository on SQL tables."""

from typing import Any

from sqlalchemy import Row, func, select

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.repositories import SqlRepository, Values
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, MailRuleId, SpaceId, UserId
from lekto.core.domain.mail_intake import MailParts
from lekto.core.domain.mail_rules import (
    MailRule,
    conditions_from_json,
    conditions_to_json,
    steps_from_json,
    steps_to_json,
)
from lekto.core.domain.reasons import Reason, ReasonCode, because


class SqlMailRuleRepository(SqlRepository[MailRuleId, MailRule]):
    kind = "mail rule"
    table = t.mail_rules

    async def of_mailbox(self, mailbox: MailboxId) -> list[MailRule]:
        return await self._ordered(self.table.c.mailbox_id == mailbox)

    async def list_all(self) -> list[MailRule]:
        return await self._ordered(None)

    async def _ordered(self, where: Any) -> list[MailRule]:
        table = self.table
        query = select(table).order_by(
            table.c.mailbox_id, table.c.priority.desc(), func.lower(table.c.name), table.c.id
        )
        if where is not None:
            query = query.where(where)
        return [self._entity(row) for row in await self._tx.read(query)]

    def _entity(self, row: Row[Any]) -> MailRule:
        enabled: bool = row.enabled
        reason = None if row.disabled_reason is None else Reason.from_json(row.disabled_reason)
        try:
            conditions = conditions_from_json(row.conditions)
            after = steps_from_json(row.steps)
        except ValidationError as error:
            # A limit tightened without a revision, or a row written by hand: the rule comes
            # paused and without what cannot be read; it takes a change only with both anew.
            conditions, after = None, ()
            enabled, reason = False, because(ReasonCode.MAIL_RULE_UNREADABLE, detail=str(error))
        return MailRule(
            id=MailRuleId(row.id),
            mailbox_id=MailboxId(row.mailbox_id),
            name=row.name,
            priority=row.priority,
            conditions=conditions,
            parts=MailParts(row.parts),
            user_id=None if row.user_id is None else UserId(row.user_id),
            space_id=None if row.space_id is None else SpaceId(row.space_id),
            text_type_id=None if row.text_type_id is None else DocumentTypeId(row.text_type_id),
            after=after,
            enabled=enabled,
            disabled_reason=reason,
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )

    def _values(self, entity: MailRule) -> Values:
        return {
            "id": entity.id,
            "mailbox_id": entity.mailbox_id,
            "name": entity.name,
            "priority": entity.priority,
            "conditions": conditions_to_json(entity.conditions),
            "parts": entity.parts.value,
            "user_id": entity.user_id,
            "space_id": entity.space_id,
            "text_type_id": entity.text_type_id,
            "steps": steps_to_json(entity.after),
            "enabled": entity.enabled,
            "disabled_reason": (
                None if entity.disabled_reason is None else entity.disabled_reason.to_json()
            ),
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
            "version": entity.version,
        }
