"""Mailboxes: only admins set them up, the password is kept encrypted, a connection is tested
with the folders as its answer."""

from datetime import date, timedelta
from typing import Any

import pytest

from lekto.core.domain.errors import ConflictError, PermissionDeniedError, ValidationError
from lekto.core.domain.ids import DocumentTypeId, new_id
from lekto.core.domain.mail import (
    Fallback,
    FetchStart,
    Mailbox,
    MailboxChanges,
    MailLogin,
    MailSecurity,
    password_context,
)
from lekto.core.domain.master_data import DocumentType
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.users import Role, User
from tests.builders import NOW
from tests.unit.services.support import World

SERVER = MailLogin(
    host="imap.example.test",
    port=993,
    security=MailSecurity.TLS,
    username="household@example.test",
    password="right",
)


async def _admin(world: World) -> User:
    return await world.user(role=Role.ADMIN)


async def _create(world: World, admin: User, name: str = "Household", **changes: Any) -> Mailbox:
    return await world.mailboxes.create(
        admin.id,
        name=name,
        host=SERVER.host,
        port=SERVER.port,
        security=SERVER.security,
        username=SERVER.username,
        password=SERVER.password,
        changes=MailboxChanges(**changes) if changes else None,
    )


async def test_only_admins_see_and_change_mailboxes(world: World) -> None:
    admin, user = await _admin(world), await world.user()
    mailbox = await _create(world, admin)
    with pytest.raises(PermissionDeniedError) as caught:
        await world.mailboxes.list_mailboxes(user.id)
    assert caught.value.reason.code is ReasonCode.ADMINS_ONLY
    for attempt in (
        world.mailboxes.get(user.id, mailbox.id),
        world.mailboxes.change(user.id, mailbox.id, MailboxChanges(name="mine")),
        world.mailboxes.delete(user.id, mailbox.id),
        world.mailboxes.test_connection(
            user.id, host="h", port=1, security=MailSecurity.NONE, username="u", password="p"
        ),
    ):
        with pytest.raises(PermissionDeniedError):
            await attempt
    assert [item.name for item in await world.mailboxes.list_mailboxes(admin.id)] == ["Household"]


async def test_the_password_is_encrypted_for_its_mailbox(world: World) -> None:
    admin = await _admin(world)
    mailbox = await _create(world, admin)
    assert b"right" not in mailbox.encrypted_password
    plain = world.cipher.decrypt(mailbox.encrypted_password, context=password_context(mailbox.id))
    assert plain == b"right"


async def test_a_change_without_a_password_keeps_it(world: World) -> None:
    admin = await _admin(world)
    mailbox = await _create(world, admin)
    changed = await world.mailboxes.change(admin.id, mailbox.id, MailboxChanges(name="Renamed"))
    assert changed.encrypted_password == mailbox.encrypted_password
    renewed = await world.mailboxes.change(admin.id, mailbox.id, MailboxChanges(), password="new")
    assert (
        world.cipher.decrypt(renewed.encrypted_password, context=password_context(mailbox.id))
        == b"new"
    )


async def test_settings_are_checked(world: World) -> None:
    admin, person = await _admin(world), await world.user()
    kind = DocumentType.create(name="Mail", now=NOW)
    async with world.uow() as uow:
        await uow.document_types.add(kind)
        await uow.commit()
    mailbox = await _create(
        world,
        admin,
        folders=("INBOX", "Rechnungen"),
        interval=timedelta(minutes=10),
        start=FetchStart.SINCE_DATE,
        since=date(2026, 1, 1),
        fallback=Fallback.EVERYTHING,
        fallback_user_id=person.id,
        body_type_id=kind.id,
    )
    assert (mailbox.folders, mailbox.fallback_user_id, mailbox.body_type_id) == (
        ("INBOX", "Rechnungen"),
        person.id,
        kind.id,
    )
    for bad in (
        MailboxChanges(since=None),  # no day
        MailboxChanges(interval=timedelta(seconds=10)),
        MailboxChanges(folders=()),
        MailboxChanges(fallback=Fallback.EVERYTHING, fallback_user_id=admin.id, port=0),
        MailboxChanges(body_type_id=DocumentTypeId(new_id())),  # no such type
    ):
        with pytest.raises(ValidationError):
            await world.mailboxes.change(admin.id, mailbox.id, bad)
    with pytest.raises(ValidationError):
        await world.mailboxes.create(
            admin.id,
            name="No password",
            host="h",
            port=143,
            security=MailSecurity.NONE,
            username="u",
            password="",
        )
    with pytest.raises(ConflictError):
        await _create(world, admin, "HOUSEHOLD")


async def test_testing_a_connection_lists_the_folders_or_says_why_not(world: World) -> None:
    admin = await _admin(world)
    world.mail_server.add_account(SERVER).folders.append("Rechnungen")
    found = await world.mailboxes.test_connection(
        admin.id,
        host=SERVER.host,
        port=SERVER.port,
        security=SERVER.security,
        username=SERVER.username,
        password="right",
    )
    assert (found.folders, found.error) == (("INBOX", "Rechnungen"), None)
    refused = await world.mailboxes.test_connection(
        admin.id,
        host=SERVER.host,
        port=SERVER.port,
        security=SERVER.security,
        username=SERVER.username,
        password="wrong",
    )
    assert refused.error is not None
    assert refused.error.code is ReasonCode.MAIL_LOGIN_FAILED


async def test_a_mailbox_is_tested_with_its_stored_password(world: World) -> None:
    admin = await _admin(world)
    world.mail_server.add_account(SERVER)
    mailbox = await _create(world, admin)
    found = await world.mailboxes.test_connection(
        admin.id,
        host=SERVER.host,
        port=SERVER.port,
        security=SERVER.security,
        username=SERVER.username,
        mailbox_id=mailbox.id,
    )
    assert found.folders == ("INBOX",)
    with pytest.raises(ValidationError):
        await world.mailboxes.test_connection(
            admin.id, host="h", port=1, security=MailSecurity.NONE, username="u"
        )


async def test_an_unreadable_password_says_so(world: World) -> None:
    admin = await _admin(world)
    mailbox = await _create(world, admin)
    async with world.uow() as uow:
        stored = await uow.mailboxes.get(mailbox.id)
        stored.set_password(b"garbage", now=NOW)
        await uow.mailboxes.update(stored)
        await uow.commit()
    found = await world.mailboxes.test_connection(
        admin.id,
        host=SERVER.host,
        port=SERVER.port,
        security=SERVER.security,
        username=SERVER.username,
        mailbox_id=mailbox.id,
    )
    assert found.error is not None
    assert found.error.code is ReasonCode.MAIL_PASSWORD_UNREADABLE
