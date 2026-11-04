"""Contract suite for `MailRecordRepository` and `MailOriginRepository` in the unit of work."""

import pytest

from lekto.core.domain.errors import ConflictError
from lekto.core.domain.ids import DocumentId, MailRecordId, new_id
from lekto.core.domain.mail import Mailbox, MailSecurity
from lekto.core.domain.mail_intake import MailOrigin, MailOutcome, MailRecord, OriginRole
from lekto.core.domain.mail_message import Address
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests import builders
from tests.builders import HOUR, NOW
from tests.contracts.unit_of_work import owner_with_space


async def a_mailbox(uow_factory: UnitOfWorkFactory, name: str = "Household") -> Mailbox:
    mailbox = Mailbox.create(
        name=name,
        host="imap.example.test",
        port=993,
        security=MailSecurity.TLS,
        username="u",
        encrypted_password=b"x",
        now=NOW,
    )
    async with uow_factory() as uow:
        await uow.mailboxes.add(mailbox)
        await uow.commit()
    return mailbox


def a_record(mailbox: Mailbox, uid: int, **parts: object) -> MailRecord:
    values: dict[str, object] = {
        "id": MailRecordId(new_id()),
        "mailbox_id": mailbox.id,
        "folder": "INBOX",
        "uidvalidity": 7,
        "uid": uid,
        "message_id": f"m{uid}@example.test",
        "sender": "Stadtwerke <rechnung@stadtwerke.example>",
        "subject": "Rechnung",
        "sent_at": NOW,
        "arrived_at": NOW,
        "size": 1234,
        "outcome": MailOutcome.TAKEN,
        "documents": 2,
        "fetched_at": NOW + uid * HOUR,
    }
    values.update(parts)
    return MailRecord(**values)  # type: ignore[arg-type]


class MailRecordRepositoryContract:
    async def test_records_tell_what_was_fetched(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = await a_mailbox(uow_factory)
        failed = a_record(
            mailbox,
            2,
            outcome=MailOutcome.FAILED,
            reason=because(ReasonCode.MAIL_SERVER_ERROR, detail="broken"),
            rule="Strom",
            message_id=None,
            sent_at=None,
        )
        async with uow_factory() as uow:
            await uow.mail_records.add(a_record(mailbox, 1))
            await uow.mail_records.add(failed)
            await uow.mail_records.add(a_record(mailbox, 1, uidvalidity=8))
            await uow.mail_records.add(a_record(mailbox, 3, folder="Archiv"))
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_records.known_uids(mailbox.id, "INBOX", 7) == {1, 2}
            assert await uow.mail_records.known_uids(mailbox.id, "INBOX", 8) == {1}
            assert await uow.mail_records.has_message("m3@example.test")
            assert not await uow.mail_records.has_message("m9@example.test")
            recent = await uow.mail_records.recent(mailbox.id, limit=2)
            assert [record.uid for record in recent] == [3, 2]
            assert recent[1] == failed

    async def test_a_uid_is_recorded_once(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = await a_mailbox(uow_factory)
        async with uow_factory() as uow:
            await uow.mail_records.add(a_record(mailbox, 1))
            await uow.commit()
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.mail_records.add(a_record(mailbox, 1))
                await uow.commit()

    async def test_records_go_with_their_mailbox(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = await a_mailbox(uow_factory)
        async with uow_factory() as uow:
            await uow.mail_records.add(a_record(mailbox, 1))
            await uow.commit()
        async with uow_factory() as uow:
            await uow.mailboxes.remove(mailbox.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_records.known_uids(mailbox.id, "INBOX", 7) == set()


class MailOriginRepositoryContract:
    async def test_origins_by_document_and_by_mail(self, uow_factory: UnitOfWorkFactory) -> None:
        owner, space = await owner_with_space(uow_factory)
        cover, attachment = builders.document(owner, space), builders.document(owner, space)
        other = builders.document(owner, space)
        record = MailRecordId(new_id())
        mailbox = await a_mailbox(uow_factory)

        def origin(document: DocumentId, role: OriginRole, **parts: object) -> MailOrigin:
            values: dict[str, object] = {
                "document_id": document,
                "record_id": record,
                "mailbox_id": mailbox.id,
                "mailbox": "Household",
                "rule": None,
                "role": role,
                "letter": 0,
                "message_id": "m1@example.test",
                "sender": (Address("Stadtwerke", "rechnung@stadtwerke.example"),),
                "to": (Address("", "anna@example.test"),),
                "cc": (),
                "subject": "Rechnung",
                "sent_at": NOW - HOUR,
                "arrived_at": NOW,
            }
            values.update(parts)
            return MailOrigin(**values)  # type: ignore[arg-type]

        full = origin(
            cover.id,
            OriginRole.COVER,
            rule="Strom",
            outer=True,
            forwarded_by=(Address("Ben", "ben@example.test"), Address("", "c@example.test")),
            related=(other.id,),
        )
        attached = origin(
            attachment.id, OriginRole.ATTACHMENT, filename="Rechnung.pdf", sent_at=None
        )
        async with uow_factory() as uow:
            for document in (cover, attachment, other):
                await uow.documents.add(document)
            await uow.mail_origins.add(attached)
            await uow.mail_origins.add(full)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_origins.find(cover.id) == full
            assert await uow.mail_origins.find(other.id) is None
            assert [item.document_id for item in await uow.mail_origins.of_record(record)] == [
                cover.id,
                attachment.id,
            ]
        async with uow_factory() as uow:
            await uow.documents.remove(attachment.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_origins.find(attachment.id) is None
            assert len(await uow.mail_origins.of_record(record)) == 1
