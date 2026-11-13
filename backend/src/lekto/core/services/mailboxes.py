"""Setting up the mailboxes Lekto fetches from (`.idea/decisions/2026-11-04-mail.md`).

Only admins see and change mailboxes (Tobi, 04.11.2026: System, Eingangskanäle, Mail). The
password is encrypted at once, bound to the mailbox, and never shown again; a change without a
password keeps the stored one. Testing a connection signs in with what the form holds (for a
mailbox being changed, the stored password unless a new one is given) and lists the folders, so
an admin picks them instead of typing them.
"""

from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, MailRuleId, UserId
from lekto.core.domain.mail import (
    Mailbox,
    MailboxChanges,
    MailLogin,
    MailSecurity,
    password_context,
)
from lekto.core.domain.mail_intake import MailOutcome, MailRecord
from lekto.core.domain.mail_rules import MailRule, first_match, record_facts
from lekto.core.domain.reasons import Action, Reason, ReasonCode, because
from lekto.core.ports.clock import Clock
from lekto.core.ports.identity import DecryptionError, SecretCipher
from lekto.core.ports.mail_server import MailServer, MailServerError
from lekto.core.ports.repository import PAGE_LIMIT, PAGE_SIZE
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import DocumentRef, ReadableDocuments, require_admin
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


@dataclass(frozen=True)
class MailView:
    """A mail Lekto fetched, as the page of its mailbox shows it: its record, the documents
    it made as far as the caller may read them (`hidden` the others), and for a mail still
    waiting for a rule the rule that takes it at the next fetch (`next_rule`; none: no rule
    matches it now)."""

    record: MailRecord
    documents: tuple[DocumentRef, ...] = ()
    hidden: int = 0
    next_rule: MailRule | None = None


@dataclass(frozen=True)
class MailsPage:
    """A page of a mailbox's mails and how many match in all."""

    mails: tuple[MailView, ...]
    total: int


@dataclass(frozen=True)
class MailSummary:
    """What a mailbox's log holds: how many mails by outcome (of `rule`, if asked; outcomes
    without any left out), the mailbox's rules to choose, and how many waiting mails each
    active rule takes at the next fetch (rules without any left out)."""

    counts: Mapping[MailOutcome, int]
    rules: tuple[MailRule, ...]
    waiting: tuple[tuple[MailRule, int], ...]


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

    async def mails(
        self,
        actor: UserId,
        id: MailboxId,
        *,
        outcomes: Collection[MailOutcome] | None = None,
        rule: MailRuleId | None = None,
        offset: int = 0,
        limit: int = PAGE_SIZE,
    ) -> MailsPage:
        """The mails the mailbox fetched, the latest first, `offset` in; only `outcomes` and
        those `rule` took where given (admins). NotFoundError for no such mailbox."""
        limit = max(1, min(limit, PAGE_LIMIT))
        async with self._uow() as uow:
            user = await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            mailbox = await uow.mailboxes.get(id)
            records = await uow.mail_records.page(
                mailbox.id, outcomes=outcomes, rule=rule, offset=max(0, offset), limit=limit
            )
            counts = await uow.mail_records.counts(mailbox.id, rule=rule)
            active = _active(await uow.mail_rules.of_mailbox(mailbox.id))
            readable = ReadableDocuments(uow, user)
            views = []
            for record in records:
                refs = [
                    await readable.ref(origin.document_id)
                    for origin in await uow.mail_origins.of_record(record.id)
                ]
                shown = tuple(ref for ref in refs if ref is not None)
                views.append(
                    MailView(
                        record,
                        shown,
                        hidden=len(refs) - len(shown),
                        next_rule=_next_rule(active, record),
                    )
                )
        total = sum(n for outcome, n in counts.items() if not outcomes or outcome in outcomes)
        return MailsPage(tuple(views), total)

    async def mail_summary(
        self, actor: UserId, id: MailboxId, *, rule: MailRuleId | None = None
    ) -> MailSummary:
        """How many of the mailbox's mails by outcome (of those `rule` took, if given), its
        rules, and how many waiting mails each active rule takes at the next fetch (admins)."""
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            mailbox = await uow.mailboxes.get(id)
            counts = await uow.mail_records.counts(mailbox.id, rule=rule)
            rules = await uow.mail_rules.of_mailbox(mailbox.id)
            waiting = await uow.mail_records.waiting(mailbox.id)
        active = _active(rules)
        taking = Counter(
            found.id for record in waiting if (found := _next_rule(active, record)) is not None
        )
        return MailSummary(
            counts,
            tuple(rules),
            tuple((item, taking[item.id]) for item in active if taking[item.id]),
        )

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


def _active(rules: list[MailRule]) -> list[MailRule]:
    return [rule for rule in rules if rule.enabled]


def _next_rule(active: list[MailRule], record: MailRecord) -> MailRule | None:
    """The rule that takes a waiting mail at the next fetch, as its record keeps it (its flags
    of the fetch: the fetch reads them anew)."""
    return first_match(active, record_facts(record)) if record.waiting else None
