"""Mail records and mail origins on SQL tables."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Row, insert, select, update

from lekto.adapters.outbound.sql import tables as t
from lekto.adapters.outbound.sql.transaction import Transaction
from lekto.core.domain.ids import DocumentId, DocumentTypeId, MailboxId, MailRecordId
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.mail_intake import MailOrigin, MailOutcome, MailRecord, OriginRole
from lekto.core.domain.mail_message import Address
from lekto.core.domain.mail_traits import FlagColor, Importance, MailMarks
from lekto.core.domain.reasons import Reason

_records, _origins = t.mail_records, t.mail_origins


class SqlMailRecordRepository:
    def __init__(self, transaction: Transaction) -> None:
        self._tx = transaction

    async def add(self, record: MailRecord) -> None:
        await self._tx.write(
            insert(_records).values(
                id=record.id,
                mailbox_id=record.mailbox_id,
                folder=record.folder,
                uidvalidity=record.uidvalidity,
                uid=record.uid,
                message_id=record.message_id,
                sender=record.sender,
                subject=record.subject,
                sent_at=record.sent_at,
                arrived_at=record.arrived_at,
                size=record.size,
                outcome=record.outcome.value,
                reason=None if record.reason is None else record.reason.to_json(),
                rule=record.rule,
                documents=record.documents,
                fetched_at=record.fetched_at,
                senders=list(record.senders),
                recipients=list(record.recipients),
                attachments=list(record.attachments),
                to_texts=list(record.to),
                cc_texts=list(record.cc),
                importance=None if record.importance is None else record.importance.value,
                **marks_values(record.marks),
                forgotten_at=record.forgotten_at,
            )
        )

    async def known_uids(self, mailbox: MailboxId, folder: str, uidvalidity: int) -> set[int]:
        rows = await self._tx.read(
            select(_records.c.uid).where(
                _records.c.mailbox_id == mailbox,
                _records.c.folder == folder,
                _records.c.uidvalidity == uidvalidity,
            )
        )
        return {int(row.uid) for row in rows}

    async def has_message(self, message_id: str) -> bool:
        found = await self._tx.read(
            select(_records.c.id).where(_records.c.message_id == message_id).limit(1)
        )
        return found.first() is not None

    async def recent(self, mailbox: MailboxId, *, limit: int) -> list[MailRecord]:
        rows = await self._tx.read(
            select(_records)
            .where(_records.c.mailbox_id == mailbox)
            .order_by(_records.c.fetched_at.desc(), _records.c.id.desc())
            .limit(limit)
        )
        return [_record(row) for row in rows]

    async def forget_beyond(self, mailbox: MailboxId, *, keep: int, now: datetime) -> int:
        latest = (
            select(_records.c.id)
            .where(_records.c.mailbox_id == mailbox)
            .order_by(_records.c.fetched_at.desc(), _records.c.id.desc())
            .limit(keep)
        )
        result = await self._tx.write(
            update(_records)
            .where(
                _records.c.mailbox_id == mailbox,
                _records.c.forgotten_at.is_(None),
                _records.c.id.not_in(latest),
            )
            .values(
                sender="",
                subject="",
                reason=None,
                senders=[],
                recipients=[],
                attachments=[],
                to_texts=[],
                cc_texts=[],
                importance=None,
                keywords=None,
                flag=None,
                forgotten_at=now,
            )
        )
        return int(result.rowcount)


def _record(row: Row[Any]) -> MailRecord:
    return MailRecord(
        id=MailRecordId(row.id),
        mailbox_id=MailboxId(row.mailbox_id),
        folder=row.folder,
        uidvalidity=int(row.uidvalidity),
        uid=int(row.uid),
        message_id=row.message_id,
        sender=row.sender,
        subject=row.subject,
        sent_at=row.sent_at,
        arrived_at=row.arrived_at,
        size=int(row.size),
        outcome=MailOutcome(row.outcome),
        reason=None if row.reason is None else Reason.from_json(row.reason),
        rule=row.rule,
        documents=row.documents,
        fetched_at=row.fetched_at,
        senders=tuple(row.senders),
        recipients=tuple(row.recipients),
        attachments=tuple(row.attachments),
        to=tuple(row.to_texts),
        cc=tuple(row.cc_texts),
        importance=None if row.importance is None else Importance(row.importance),
        marks=marks_of(row.keywords, row.flag),
        forgotten_at=row.forgotten_at,
    )


class SqlMailOriginRepository:
    def __init__(self, transaction: Transaction) -> None:
        self._tx = transaction

    async def add(self, origin: MailOrigin) -> None:
        await self._tx.write(
            insert(_origins).values(
                document_id=origin.document_id,
                record_id=origin.record_id,
                mailbox_id=origin.mailbox_id,
                mailbox=origin.mailbox,
                rule=origin.rule,
                role=origin.role.value,
                letter=origin.letter,
                outer=origin.outer,
                message_id=origin.message_id,
                sender=addresses_json(origin.sender),
                recipients=addresses_json(origin.to),
                copies=addresses_json(origin.cc),
                subject=origin.subject,
                sent_at=origin.sent_at,
                arrived_at=origin.arrived_at,
                forwarded_by=addresses_json(origin.forwarded_by),
                filename=origin.filename,
                related=[str(id) for id in origin.related],
                body_type_id=origin.body_type_id,
                importance=None if origin.importance is None else origin.importance.value,
                **marks_values(origin.marks),
            )
        )

    async def find(self, document: DocumentId) -> MailOrigin | None:
        rows = await self._tx.read(select(_origins).where(_origins.c.document_id == document))
        row = rows.first()
        return None if row is None else _origin(row)

    async def of_record(self, record: MailRecordId) -> list[MailOrigin]:
        rows = await self._tx.read(
            select(_origins)
            .where(_origins.c.record_id == record)
            .order_by(_origins.c.letter, _origins.c.role.desc(), _origins.c.document_id)
        )
        return [_origin(row) for row in rows]


def marks_values(marks: MailMarks | None) -> dict[str, Any]:
    """The columns of a mail's marks: keywords NULL when they are not known."""
    if marks is None:
        return {"keywords": None, "flag": None}
    return {
        "keywords": list(marks.keywords),
        "flag": None if marks.flag is None else marks.flag.value,
    }


def marks_of(keywords: Any, flag: str | None) -> MailMarks | None:
    if keywords is None:
        return None
    return MailMarks(keywords=tuple(keywords), flag=None if flag is None else FlagColor(flag))


def addresses_json(addresses: tuple[Address, ...]) -> list[JsonValue]:
    return [{"name": item.name, "address": item.address} for item in addresses]


def addresses_of(data: Any) -> tuple[Address, ...]:
    return tuple(Address(str(item["name"]), str(item["address"])) for item in data or ())


def _origin(row: Row[Any]) -> MailOrigin:
    return MailOrigin(
        document_id=DocumentId(row.document_id),
        record_id=MailRecordId(row.record_id),
        mailbox_id=MailboxId(row.mailbox_id),
        mailbox=row.mailbox,
        rule=row.rule,
        role=OriginRole(row.role),
        letter=row.letter,
        outer=row.outer,
        message_id=row.message_id,
        sender=addresses_of(row.sender),
        to=addresses_of(row.recipients),
        cc=addresses_of(row.copies),
        subject=row.subject,
        sent_at=row.sent_at,
        arrived_at=row.arrived_at,
        forwarded_by=addresses_of(row.forwarded_by),
        filename=row.filename,
        related=tuple(DocumentId(UUID(id)) for id in row.related),
        body_type_id=None if row.body_type_id is None else DocumentTypeId(row.body_type_id),
        importance=None if row.importance is None else Importance(row.importance),
        marks=marks_of(row.keywords, row.flag),
    )
