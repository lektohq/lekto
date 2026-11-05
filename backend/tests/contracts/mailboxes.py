"""Contract suite for `MailboxRepository` in the unit of work."""

from dataclasses import replace
from datetime import date, timedelta
from typing import Any

import pytest

from lekto.core.domain.errors import ConcurrencyError, ConflictError, NotFoundError
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    Mailbox,
    MailboxChanges,
    MailboxStatus,
    MailSecurity,
)
from lekto.core.domain.master_data import DocumentType
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests.builders import HOUR, NOW
from tests.contracts.unit_of_work import a_user


def a_mailbox(name: str = "Household", **parts: Any) -> Mailbox:
    mailbox = Mailbox.create(
        name=name,
        host="imap.example.test",
        port=993,
        security=MailSecurity.TLS,
        username="household@example.test",
        encrypted_password=b"\x00sealed",
        now=NOW,
    )
    if parts:
        mailbox.change(MailboxChanges(**parts), now=NOW)
    return mailbox


class MailboxRepositoryContract:
    async def test_a_mailbox_round_trips_with_all_its_parts(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        person = await a_user(uow_factory)
        kind = DocumentType.create(name="Mail", now=NOW)
        async with uow_factory() as uow:
            await uow.document_types.add(kind)
            await uow.commit()
        mailbox = a_mailbox(
            folders=("INBOX", "Rechnungen/Strom"),
            interval=timedelta(minutes=15),
            start=FetchStart.SINCE_DATE,
            since=date(2026, 1, 1),
            fallback=Fallback.EVERYTHING,
            fallback_user_id=person.id,
            body_type_id=kind.id,
            enabled=False,
        )
        mailbox.record(
            MailboxStatus(
                last_attempt_at=NOW + HOUR,
                last_success_at=NOW,
                error=because(ReasonCode.MAIL_FOLDER_MISSING, folder="Rechnungen/Strom"),
                mails=12,
                documents=30,
                skipped_at=NOW,
                skipped=because(ReasonCode.MAIL_TOO_LARGE, subject="Fotos", size=200, max=134),
                step_failed_at=NOW + HOUR,
                step_failed=because(
                    ReasonCode.MAIL_STEP_FAILED,
                    step="mail_step:add_keyword",
                    subject="Fotos",
                    detail="keywords are not stored",
                ),
                keywords=("$label1", "Lekto"),
                own_keywords=False,
            )
        )
        plain = a_mailbox("Plain")
        async with uow_factory() as uow:
            await uow.mailboxes.add(mailbox)
            await uow.mailboxes.add(plain)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mailboxes.get(mailbox.id) == mailbox
            assert await uow.mailboxes.get(plain.id) == plain
            assert (await uow.mailboxes.get(plain.id)).status.own_keywords is None  # not known

    async def test_names_are_unique_regardless_of_case(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        async with uow_factory() as uow:
            await uow.mailboxes.add(a_mailbox("Household"))
            await uow.commit()
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.mailboxes.add(a_mailbox("HOUSEHOLD"))
                await uow.commit()

    async def test_update_checks_the_version(self, uow_factory: UnitOfWorkFactory) -> None:
        mailbox = a_mailbox()
        async with uow_factory() as uow:
            await uow.mailboxes.add(mailbox)
            await uow.commit()
        async with uow_factory() as uow:
            stored = await uow.mailboxes.get(mailbox.id)
            stored.change(MailboxChanges(name="Renamed"), now=NOW + HOUR)
            await uow.mailboxes.update(stored)
            await uow.commit()
        async with uow_factory() as uow:
            assert (await uow.mailboxes.get(mailbox.id)).name == "Renamed"
            with pytest.raises(ConcurrencyError):
                await uow.mailboxes.update(replace(mailbox, name="Stale"))

    async def test_lists_by_name_and_removes(self, uow_factory: UnitOfWorkFactory) -> None:
        later, earlier = a_mailbox("zeta"), a_mailbox("Alpha")
        async with uow_factory() as uow:
            await uow.mailboxes.add(later)
            await uow.mailboxes.add(earlier)
            await uow.commit()
        async with uow_factory() as uow:
            assert [item.name for item in await uow.mailboxes.list_all()] == ["Alpha", "zeta"]
            await uow.mailboxes.remove(later.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.mailboxes.find(later.id) is None
            with pytest.raises(NotFoundError):
                await uow.mailboxes.remove(later.id)

    async def test_the_person_and_the_type_it_names_stay(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        person = await a_user(uow_factory)
        kind = DocumentType.create(name="Mail", now=NOW)
        async with uow_factory() as uow:
            await uow.document_types.add(kind)
            await uow.mailboxes.add(
                a_mailbox(
                    fallback=Fallback.EVERYTHING,
                    fallback_user_id=person.id,
                    body_type_id=kind.id,
                )
            )
            await uow.commit()
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.users.remove(person.id)
                await uow.commit()
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.document_types.remove(kind.id)
                await uow.commit()
