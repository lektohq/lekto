"""Mailbox repository on SQL tables."""

from datetime import timedelta
from typing import Any

from sqlalchemy import Row, select

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.repositories import SqlRepository, Values
from lekto.core.domain.ids import DocumentTypeId, MailboxId, UserId
from lekto.core.domain.mail import Fallback, FetchStart, Mailbox, MailboxStatus, MailSecurity
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import name_key


class SqlMailboxRepository(SqlRepository[MailboxId, Mailbox]):
    kind = "mailbox"
    table = t.mailboxes

    async def list_all(self) -> list[Mailbox]:
        rows = await self._tx.read(select(self.table).order_by(self.table.c.name_key))
        return [self._entity(row) for row in rows]

    def _entity(self, row: Row[Any]) -> Mailbox:
        return Mailbox(
            id=MailboxId(row.id),
            name=row.name,
            host=row.host,
            port=row.port,
            security=MailSecurity(row.security),
            username=row.username,
            encrypted_password=bytes(row.password),
            folders=tuple(row.folders),
            interval=timedelta(seconds=row.interval_seconds),
            start=FetchStart(row.start),
            since=row.since,
            fallback=Fallback(row.fallback),
            fallback_user_id=None if row.fallback_user_id is None else UserId(row.fallback_user_id),
            body_type_id=None if row.body_type_id is None else DocumentTypeId(row.body_type_id),
            enabled=row.enabled,
            status=MailboxStatus(
                last_attempt_at=row.last_attempt_at,
                last_success_at=row.last_success_at,
                error=None if row.error is None else Reason.from_json(row.error),
                mails=row.mails,
                documents=row.documents,
            ),
            created_at=row.created_at,
            updated_at=row.updated_at,
            version=row.version,
        )

    def _values(self, entity: Mailbox) -> Values:
        status = entity.status
        return {
            "id": entity.id,
            "name": entity.name,
            "name_key": name_key(entity.name),
            "host": entity.host,
            "port": entity.port,
            "security": entity.security.value,
            "username": entity.username,
            "password": entity.encrypted_password,
            "folders": list(entity.folders),
            "interval_seconds": int(entity.interval.total_seconds()),
            "start": entity.start.value,
            "since": entity.since,
            "fallback": entity.fallback.value,
            "fallback_user_id": entity.fallback_user_id,
            "body_type_id": entity.body_type_id,
            "enabled": entity.enabled,
            "last_attempt_at": status.last_attempt_at,
            "last_success_at": status.last_success_at,
            "error": None if status.error is None else status.error.to_json(),
            "mails": status.mails,
            "documents": status.documents,
            "created_at": entity.created_at,
            "updated_at": entity.updated_at,
            "version": entity.version,
        }
