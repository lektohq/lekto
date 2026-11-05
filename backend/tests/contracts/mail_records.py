"""Contract suite for `MailRecordRepository` and `MailOriginRepository` in the unit of work."""

from dataclasses import replace

import pytest

from lekto.core.domain.condition_tree import Group
from lekto.core.domain.errors import ConcurrencyError, ConflictError, NotFoundError
from lekto.core.domain.ids import (
    DocumentId,
    DocumentTypeId,
    MailboxId,
    MailRecordId,
    SpaceId,
    UserId,
    new_id,
)
from lekto.core.domain.mail import MailAction, Mailbox, MailStep
from lekto.core.domain.mail_intake import (
    MailOrigin,
    MailOutcome,
    MailParts,
    MailRecord,
    OriginRole,
)
from lekto.core.domain.mail_message import Address
from lekto.core.domain.mail_rules import (
    MailCondition,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
)
from lekto.core.domain.mail_traits import FlagColor, Importance, MailMarks
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests import builders
from tests.builders import HOUR, NOW
from tests.contracts.mailboxes import a_mailbox as mailbox_entity
from tests.contracts.unit_of_work import owner_with_space


async def a_mailbox(uow_factory: UnitOfWorkFactory, name: str = "Household") -> Mailbox:
    """A mailbox as the mailbox contract builds it, stored."""
    mailbox = mailbox_entity(name)
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
        "senders": ("rechnung@stadtwerke.example", "Stadtwerke"),
        "recipients": ("anna@example.test",),
        "attachments": ("Rechnung.pdf", ""),
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
            to=("anna@example.test",),
            cc=("ben@example.test", "Ben"),
            importance=Importance.HIGH,
            marks=MailMarks(keywords=("Lekto", "$label1"), flag=FlagColor.GREEN),
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
            recent = await uow.mail_records.recent(mailbox.id, limit=4)
            assert [record.uid for record in recent[:2]] == [3, 2]
            # The two fetched at the same time stand by id, the later id first.
            assert [record.uid for record in recent[2:]] == [1, 1]
            assert [record.id for record in recent[2:]] == sorted(
                (record.id for record in recent[2:]), reverse=True
            )
            assert recent[1] == failed
            assert (recent[0].importance, recent[0].marks) == (None, None)  # not known

    async def test_old_records_let_go_of_what_the_mail_said(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        mailbox = await a_mailbox(uow_factory)
        async with uow_factory() as uow:
            for uid in (1, 2, 3):
                await uow.mail_records.add(
                    a_record(
                        mailbox,
                        uid,
                        to=("anna@example.test",),
                        cc=("Ben",),
                        importance=Importance.HIGH,
                        marks=MailMarks(keywords=("Lekto",), flag=FlagColor.RED),
                        reason=because(ReasonCode.MAIL_TOO_LARGE, subject="Fotos", size=3, max=2),
                    )
                )
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_records.forget_beyond(mailbox.id, keep=2, now=NOW + 5 * HOUR) == 1
            assert await uow.mail_records.forget_beyond(mailbox.id, keep=2, now=NOW + 6 * HOUR) == 0
            await uow.commit()
        async with uow_factory() as uow:
            three, two, one = await uow.mail_records.recent(mailbox.id, limit=3)
            assert one.forgotten_at == NOW + 5 * HOUR
            assert (one.sender, one.subject, one.reason, one.importance, one.marks) == (
                "",
                "",
                None,
                None,
                None,
            )
            assert (one.senders, one.recipients, one.to, one.cc, one.attachments) == (
                (),
                (),
                (),
                (),
                (),
            )
            assert (one.uid, one.message_id, one.outcome, one.documents, one.fetched_at) == (
                1,
                "m1@example.test",
                MailOutcome.TAKEN,
                2,
                NOW + HOUR,
            )
            assert two.forgotten_at is None and three.forgotten_at is None
            assert two.subject == "Rechnung" and two.marks is not None and two.reason is not None
            assert await uow.mail_records.known_uids(mailbox.id, "INBOX", 7) == {1, 2, 3}
            assert await uow.mail_records.has_message("m1@example.test")

    async def test_a_record_needs_its_mailbox(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = await a_mailbox(uow_factory)
        gone = replace(mailbox, id=MailboxId(new_id()))
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.mail_records.add(a_record(gone, 1))
                await uow.commit()

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
    async def test_an_origin_needs_its_document(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = await a_mailbox(uow_factory)
        origin = MailOrigin(
            document_id=DocumentId(new_id()),
            record_id=MailRecordId(new_id()),
            mailbox_id=mailbox.id,
            mailbox="Household",
            rule=None,
            role=OriginRole.COVER,
            letter=0,
            message_id=None,
            sender=(),
            to=(),
            cc=(),
            subject="Rechnung",
            sent_at=None,
            arrived_at=NOW,
        )
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.mail_origins.add(origin)
                await uow.commit()

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
            body_type_id=DocumentTypeId(new_id()),
            importance=Importance.LOW,
            marks=MailMarks(keywords=(), flag=FlagColor.RED),
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


class MailRuleRepositoryContract:
    async def test_update_checks_the_version_and_a_rule_goes_once(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        mailbox = await a_mailbox(uow_factory)
        rule = MailRule.create(
            mailbox_id=mailbox.id,
            changes=MailRuleChanges(name="Strom", user_id=UserId(new_id())),
            now=NOW,
        )
        async with uow_factory() as uow:
            await uow.mail_rules.add(rule)
            await uow.commit()
        async with uow_factory() as uow:
            stored = await uow.mail_rules.get(rule.id)
            stored.change(MailRuleChanges(name="Gas"), now=NOW + HOUR)
            await uow.mail_rules.update(stored)
            await uow.commit()
        with pytest.raises(ConcurrencyError):
            async with uow_factory() as uow:
                rule.change(MailRuleChanges(name="Wasser"), now=NOW + HOUR)
                await uow.mail_rules.update(rule)
                await uow.commit()
        async with uow_factory() as uow:
            await uow.mail_rules.remove(rule.id)
            await uow.commit()
        with pytest.raises(NotFoundError):
            async with uow_factory() as uow:
                await uow.mail_rules.remove(rule.id)

    async def test_rules_by_mailbox_priority_and_name(self, uow_factory: UnitOfWorkFactory) -> None:
        first, second = await a_mailbox(uow_factory, "A"), await a_mailbox(uow_factory, "B")
        person = UserId(new_id())

        def rule(mailbox: Mailbox, name: str, priority: int, **changes: object) -> MailRule:
            values: dict[str, object] = {"name": name, "priority": priority, "user_id": person}
            values.update(changes)
            return MailRule.create(
                mailbox_id=mailbox.id,
                changes=MailRuleChanges(**values),  # type: ignore[arg-type]
                now=NOW,
            )

        full = rule(
            first,
            "Strom",
            1,
            conditions=Group(
                mode="any",
                items=(
                    MailCondition(MailField.SENDER, MailOperator.ENDS_WITH, "@stadtwerke.example"),
                    Group(
                        mode="all",
                        items=(MailCondition(MailField.ATTACHMENTS, MailOperator.PRESENT),),
                        negate=True,
                    ),
                ),
            ),
            space_id=SpaceId(new_id()),
            text_type_id=DocumentTypeId(new_id()),
            after=(
                MailStep(MailAction.FLAG, "green"),
                MailStep(MailAction.ADD_KEYWORD, "Lekto"),
                MailStep(MailAction.MOVE, "Lekto/Erledigt"),
            ),
        )
        full.pause(because(ReasonCode.MAIL_RULE_TYPE_GONE), now=NOW + HOUR)
        later, earlier = rule(first, "b", 5), rule(first, "A", 5)
        other = rule(
            second, "Other", 0, parts=MailParts.NOTHING, after=(MailStep(MailAction.TRASH),)
        )
        async with uow_factory() as uow:
            for item in (later, other, full, earlier):
                await uow.mail_rules.add(item)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_rules.get(full.id) == full
            assert [item.name for item in await uow.mail_rules.of_mailbox(first.id)] == [
                "A",
                "b",
                "Strom",
            ]
            assert len(await uow.mail_rules.list_all()) == 4
            stored = await uow.mail_rules.get(other.id)
            stored.change(MailRuleChanges(name="Renamed"), now=NOW + HOUR)
            await uow.mail_rules.update(stored)
            await uow.commit()
        async with uow_factory() as uow:
            assert (await uow.mail_rules.get(other.id)).name == "Renamed"
            await uow.mailboxes.remove(first.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_rules.of_mailbox(first.id) == []
            await uow.mail_rules.remove(other.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mail_rules.list_all() == []
