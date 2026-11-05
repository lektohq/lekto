"""Setting up the mailboxes Lekto fetches from (umsetzungsplan "Eingangskanal Mail").

Only admins see and change mailboxes (Tobi, 04.11.2026: System, Eingangskanäle, Mail). The
password is encrypted at once, bound to the mailbox, and never shown again; a change without a
password keeps the stored one. Testing a connection signs in with what the form holds (for a
mailbox being changed, the stored password unless a new one is given) and lists the folders, so
an admin picks them instead of typing them.
"""

from dataclasses import dataclass

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, UserId
from lekto.core.domain.mail import (
    Mailbox,
    MailboxChanges,
    MailLogin,
    MailSecurity,
    password_context,
)
from lekto.core.domain.reasons import Action, Reason, ReasonCode, because
from lekto.core.ports.clock import Clock
from lekto.core.ports.identity import DecryptionError, SecretCipher
from lekto.core.ports.mail_server import MailServer, MailServerError
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import require_admin
from lekto.core.services.mail_intake import schedule_fetch

MAX_PASSWORD = 1000


@dataclass(frozen=True, kw_only=True)
class ConnectionTest:
    """What a test of a connection found: the folders, the keywords of the inbox and whether
    the server stores keywords of Lekto's own; or why it failed."""

    folders: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    own_keywords: bool = False
    error: Reason | None = None


class MailboxService:
    def __init__(
        self, uow: UnitOfWorkFactory, clock: Clock, cipher: SecretCipher, server: MailServer
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._cipher = cipher
        self._server = server

    async def list_mailboxes(self, actor: UserId) -> list[Mailbox]:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            return await uow.mailboxes.list_all()

    async def get(self, actor: UserId, id: MailboxId) -> Mailbox:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            return await uow.mailboxes.get(id)

    async def create(
        self,
        actor: UserId,
        *,
        name: str,
        host: str,
        port: int,
        security: MailSecurity,
        username: str,
        password: str,
        changes: MailboxChanges | None = None,
    ) -> Mailbox:
        """A new mailbox with the defaults of `Mailbox.create`, then `changes` (folders, interval,
        from when on, fallback, type of the mail text, enabled)."""
        _check_password(password)
        now = self._clock.now()
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            mailbox = Mailbox.create(
                name=name,
                host=host,
                port=port,
                security=security,
                username=username,
                encrypted_password=b"",
                now=now,
            )
            mailbox.set_password(self._encrypt(mailbox.id, password), now=now)
            if changes is not None:
                mailbox.change(changes, now=now)
            await _check_references(uow, mailbox)
            await uow.mailboxes.add(mailbox)
            if mailbox.enabled:
                await schedule_fetch(uow, mailbox, now)
            await uow.commit()
            return mailbox

    async def change(
        self,
        actor: UserId,
        id: MailboxId,
        changes: MailboxChanges,
        *,
        password: str | None = None,
    ) -> Mailbox:
        """`password` None keeps the stored one."""
        if password is not None:
            _check_password(password)
        now = self._clock.now()
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            mailbox = await uow.mailboxes.get(id)
            mailbox.change(changes, now=now)
            if password is not None:
                mailbox.set_password(self._encrypt(id, password), now=now)
            await _check_references(uow, mailbox)
            await uow.mailboxes.update(mailbox)
            if mailbox.enabled:
                await schedule_fetch(uow, mailbox, now)  # what changed counts at once
            await uow.commit()
            return mailbox

    async def delete(self, actor: UserId, id: MailboxId) -> None:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            await uow.mailboxes.remove(id)
            await uow.commit()

    async def test_connection(
        self,
        actor: UserId,
        *,
        host: str,
        port: int,
        security: MailSecurity,
        username: str,
        password: str | None = None,
        mailbox_id: MailboxId | None = None,
    ) -> ConnectionTest:
        """Sign in and list the folders. Without `password`, the stored one of `mailbox_id`
        (ValidationError if neither is given)."""
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            stored = None if mailbox_id is None else await uow.mailboxes.get(mailbox_id)
        if password is None:
            if stored is None:
                raise ValidationError("password: required without a mailbox")
            try:
                password = self._decrypt(stored)
            except DecryptionError:
                return ConnectionTest(error=because(ReasonCode.MAIL_PASSWORD_UNREADABLE))
        login = MailLogin(
            host=host.strip(),
            port=port,
            security=security,
            username=username.strip(),
            password=password,
        )
        try:
            account = await self._server.account(login)
            return ConnectionTest(
                folders=account.folders,
                keywords=account.keywords,
                own_keywords=account.own_keywords,
            )
        except MailServerError as error:
            return ConnectionTest(error=error.reason)

    def _encrypt(self, id: MailboxId, password: str) -> bytes:
        return self._cipher.encrypt(password.encode(), context=password_context(id))

    def _decrypt(self, mailbox: Mailbox) -> str:
        """Raises DecryptionError."""
        plain = self._cipher.decrypt(
            mailbox.encrypted_password, context=password_context(mailbox.id)
        )
        return plain.decode()


def _check_password(password: str) -> None:
    if not password or len(password) > MAX_PASSWORD:
        raise ValidationError(f"password: 1 to {MAX_PASSWORD} characters")


async def _check_references(uow: UnitOfWork, mailbox: Mailbox) -> None:
    """The person a fallback takes everything for, and the type of the mail text, exist."""
    if mailbox.fallback_user_id is not None:
        person = await uow.users.find(mailbox.fallback_user_id)
        if person is None or not person.active:
            raise ValidationError("fallback_user_id: no such active user")
    if (
        mailbox.body_type_id is not None
        and await uow.document_types.find(mailbox.body_type_id) is None
    ):
        raise ValidationError("body_type_id: no such document type")
