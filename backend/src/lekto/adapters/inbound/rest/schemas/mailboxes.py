"""Mailboxes Lekto fetches from."""

from collections.abc import Callable
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from lekto.adapters.inbound.rest.schemas.common import following_offset
from lekto.adapters.inbound.schemas import DocumentRefOut, ReasonOut
from lekto.core.domain.changes import UNSET
from lekto.core.domain.ids import DocumentTypeId, UserId
from lekto.core.domain.mail import (
    MAX_FOLDER,
    MAX_FOLDERS,
    MAX_HOST,
    MAX_INTERVAL,
    MAX_NAME,
    MAX_USERNAME,
    MIN_INTERVAL,
    Fallback,
    FetchStart,
    MailAction,
    Mailbox,
    MailboxChanges,
    MailSecurity,
    StepOutcome,
)
from lekto.core.domain.mail_intake import KEPT_RECORDS, MailOutcome
from lekto.core.domain.mail_rules import MailRule
from lekto.core.services.mailboxes import (
    MAX_PASSWORD,
    ConnectionTest,
    MailsPage,
    MailSummary,
    MailView,
)

_MINUTE = timedelta(minutes=1)

SECURITY_HELP = (
    "`tls`: TLS from the start (IMAPS, usually port 993); `starttls`: TLS after the greeting "
    "(usually 143); `none`: no encryption, for a server in one's own network."
)
START_HELP = (
    "Which mails the mailbox takes: `since_setup`, those that came after it was set up; "
    "`since_date`, those from the day `since` on; `unread`, the unread ones."
)
FALLBACK_HELP = (
    "What a mail no mail rule takes brings in: `nothing`, or `everything` for the person "
    "`fallback_user_id`."
)
BODY_TYPE_HELP = "The document type of a mail's text where a rule does not set one; none: open."


def _minutes(value: timedelta) -> int:
    return int(value / _MINUTE)


type FolderName = Annotated[str, Field(min_length=1, max_length=MAX_FOLDER)]


class _Settings(BaseModel):
    """What a mailbox does, beside where it signs in."""

    model_config = ConfigDict(extra="forbid")

    folders: list[FolderName] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_FOLDERS,
        description="The folders to look in, by their full names as `/mailboxes/test` lists them.",
    )
    interval_minutes: int | None = Field(
        default=None,
        ge=_minutes(MIN_INTERVAL),
        le=_minutes(MAX_INTERVAL),
        description="Minutes between two fetches.",
    )
    start: FetchStart | None = Field(default=None, description=START_HELP)
    since: date | None = Field(default=None, description="With `start: since_date`.")
    fallback: Fallback | None = Field(default=None, description=FALLBACK_HELP)
    fallback_user_id: UUID | None = Field(default=None, description="With `fallback: everything`.")
    body_type_id: UUID | None = Field(default=None, description=BODY_TYPE_HELP)
    enabled: bool | None = Field(default=None, description="Whether Lekto fetches from it.")

    def settings(self) -> MailboxChanges:
        """The settings given; nullable ones also when given as null."""
        given = self.model_fields_set
        return MailboxChanges(
            folders=UNSET if self.folders is None else tuple(self.folders),
            interval=(
                UNSET if self.interval_minutes is None else timedelta(minutes=self.interval_minutes)
            ),
            start=UNSET if self.start is None else self.start,
            since=self.since if "since" in given else UNSET,
            fallback=UNSET if self.fallback is None else self.fallback,
            fallback_user_id=(
                _optional(UserId, self.fallback_user_id) if "fallback_user_id" in given else UNSET
            ),
            body_type_id=(
                _optional(DocumentTypeId, self.body_type_id) if "body_type_id" in given else UNSET
            ),
            enabled=UNSET if self.enabled is None else self.enabled,
        )


def _optional[T](kind: Callable[[UUID], T], value: UUID | None) -> T | None:
    return None if value is None else kind(value)


class MailboxCreate(_Settings):
    """A new mailbox; what is left out gets the default (folder `INBOX`, every 5 minutes, since
    it was set up, nothing without a rule, no type for the mail text, enabled)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Household",
                    "host": "imap.example.org",
                    "port": 993,
                    "security": "tls",
                    "username": "household@example.org",
                    "password": "app-password",
                    "folders": ["INBOX", "Rechnungen"],
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=MAX_NAME)
    host: str = Field(min_length=1, max_length=MAX_HOST)
    port: int = Field(ge=1, le=65535)
    security: MailSecurity = Field(description=SECURITY_HELP)
    username: str = Field(min_length=1, max_length=MAX_USERNAME)
    password: SecretStr = Field(
        min_length=1, max_length=MAX_PASSWORD, description="Stored encrypted, never shown again."
    )


class MailboxPatch(_Settings):
    """What changes; what is left out stays. `since`, `fallback_user_id` and `body_type_id`
    given as null clear it."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"enabled": False}]})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    host: str | None = Field(default=None, min_length=1, max_length=MAX_HOST)
    port: int | None = Field(default=None, ge=1, le=65535)
    security: MailSecurity | None = Field(default=None, description=SECURITY_HELP)
    username: str | None = Field(default=None, min_length=1, max_length=MAX_USERNAME)
    password: SecretStr | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_PASSWORD,
        description="A new password; left out, the stored one stays.",
    )

    def changes(self) -> MailboxChanges:
        return replace(
            self.settings(),
            name=UNSET if self.name is None else self.name,
            host=UNSET if self.host is None else self.host,
            port=UNSET if self.port is None else self.port,
            security=UNSET if self.security is None else self.security,
            username=UNSET if self.username is None else self.username,
        )


class MailboxStatusOut(BaseModel):
    """What the fetches found."""

    last_attempt_at: datetime | None
    last_success_at: datetime | None
    error: ReasonOut | None = Field(
        description="Why the last attempt failed; none after a success."
    )
    mails: int = Field(description="Mails taken in.")
    documents: int = Field(description="Documents made from them.")
    skipped_at: datetime | None = Field(
        description="When a mail was last left out because it was too large."
    )
    skipped: ReasonOut | None = Field(description="Which mail that was, and why.")
    step_failed_at: datetime | None = Field(
        description="When a step of a mail rule on a mail on the server last failed."
    )
    step_failed: ReasonOut | None = Field(
        description="Which step, on which mail, and what the server answered."
    )
    keywords: list[str] = Field(
        description="The keywords its folders knew at the last fetch, to choose in a rule."
    )
    own_keywords: bool | None = Field(
        description="Whether the server stores keywords of Lekto's own; null before a fetch."
    )


class MailboxOut(BaseModel):
    """A mailbox, without its password."""

    id: UUID
    name: str
    host: str
    port: int
    security: MailSecurity
    username: str
    folders: list[str]
    interval_minutes: int
    start: FetchStart
    since: date | None
    fallback: Fallback
    fallback_user_id: UUID | None
    body_type_id: UUID | None
    enabled: bool
    status: MailboxStatusOut
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, mailbox: Mailbox) -> "MailboxOut":
        status = mailbox.status
        return cls(
            id=mailbox.id,
            name=mailbox.name,
            host=mailbox.host,
            port=mailbox.port,
            security=mailbox.security,
            username=mailbox.username,
            folders=list(mailbox.folders),
            interval_minutes=_minutes(mailbox.interval),
            start=mailbox.start,
            since=mailbox.since,
            fallback=mailbox.fallback,
            fallback_user_id=mailbox.fallback_user_id,
            body_type_id=mailbox.body_type_id,
            enabled=mailbox.enabled,
            status=MailboxStatusOut(
                last_attempt_at=status.last_attempt_at,
                last_success_at=status.last_success_at,
                error=None if status.error is None else ReasonOut.of(status.error),
                mails=status.mails,
                documents=status.documents,
                skipped_at=status.skipped_at,
                skipped=None if status.skipped is None else ReasonOut.of(status.skipped),
                step_failed_at=status.step_failed_at,
                step_failed=(
                    None if status.step_failed is None else ReasonOut.of(status.step_failed)
                ),
                keywords=list(status.keywords),
                own_keywords=status.own_keywords,
            ),
            created_at=mailbox.created_at,
            updated_at=mailbox.updated_at,
        )


class ConnectionTestBody(BaseModel):
    """Where and as whom to sign in. Without `password`, the stored one of `mailbox_id`."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "host": "imap.example.org",
                    "port": 993,
                    "security": "tls",
                    "username": "household@example.org",
                    "password": "app-password",
                }
            ]
        },
    )

    host: str = Field(min_length=1, max_length=MAX_HOST)
    port: int = Field(ge=1, le=65535)
    security: MailSecurity = Field(description=SECURITY_HELP)
    username: str = Field(min_length=1, max_length=MAX_USERNAME)
    password: SecretStr | None = Field(default=None, min_length=1, max_length=MAX_PASSWORD)
    mailbox_id: UUID | None = Field(
        default=None, description="The mailbox being changed, for its stored password."
    )


class ConnectionTestOut(BaseModel):
    """The folders the account has (`INBOX` first), the keywords its inbox knows and whether
    the server stores keywords of Lekto's own; or why signing in failed."""

    ok: bool
    folders: list[str]
    keywords: list[str] = Field(
        description="Keywords (tags) the inbox knows, without the clients' own (a forward, spam)."
    )
    own_keywords: bool = Field(
        description="Whether the server stores keywords of Lekto's own (PERMANENTFLAGS `\\*`)."
    )
    error: ReasonOut | None

    @classmethod
    def of(cls, test: ConnectionTest) -> "ConnectionTestOut":
        return cls(
            ok=test.error is None,
            folders=list(test.folders),
            keywords=list(test.keywords),
            own_keywords=test.own_keywords,
            error=None if test.error is None else ReasonOut.of(test.error),
        )


class MailRuleRefOut(BaseModel):
    id: UUID
    name: str
    enabled: bool

    @classmethod
    def of(cls, rule: MailRule) -> "MailRuleRefOut":
        return cls(id=rule.id, name=rule.name, enabled=rule.enabled)


class MailStepOut(BaseModel):
    action: MailAction
    value: str | None
    failed: ReasonOut | None = Field(description="Why the server refused it; null: done.")

    @classmethod
    def of(cls, item: StepOutcome) -> "MailStepOut":
        return cls(
            action=item.step.action,
            value=item.step.value,
            failed=None if item.failed is None else ReasonOut.of(item.failed),
        )


class MailOut(BaseModel):
    """A mail the mailbox fetched and what became of it."""

    id: UUID
    folder: str
    subject: str = Field(description="Empty once Lekto let go of what the head said.")
    sender: str
    sent_at: datetime | None
    arrived_at: datetime = Field(description="When it arrived at the server.")
    fetched_at: datetime
    size: int = Field(description="Bytes.")
    outcome: MailOutcome = Field(
        description=(
            "`taken`: documents made; `nothing`: taken, nothing in it to take; `no_rule`: no rule "
            "took it and the fallback takes nothing; `known`: its Message-ID came before; "
            "`too_large`; `failed`."
        )
    )
    reason: ReasonOut | None = Field(description="Why it was left out or failed.")
    rule: str | None = Field(description="The rule that took it, by its name then.")
    rule_id: UUID | None = Field(description="That rule; null for the fallback or no rule.")
    decided_at: datetime | None = Field(
        description="When a rule or the fallback took it; later than `fetched_at`: afterwards."
    )
    later: bool = Field(description="A rule switched on after it came took it.")
    documents: list[DocumentRefOut] = Field(description="Those the caller may read.")
    documents_hidden: int = Field(description="Its documents the caller may not read, or gone.")
    steps: list[MailStepOut] = Field(description="The steps on the server, in order.")
    gone_at: datetime | None = Field(
        description="When a fetch found it gone from its folder while no rule had taken it."
    )
    forgotten: bool = Field(description="Lekto let go of what its head said (an old mail).")
    waiting: bool = Field(description="No rule took it yet, and one switched on later may.")
    next_rule: MailRuleRefOut | None = Field(
        description="For a waiting mail: the rule that takes it at the next fetch."
    )

    @classmethod
    def of(cls, view: MailView) -> "MailOut":
        record = view.record
        return cls(
            id=record.id,
            folder=record.folder,
            subject=record.subject,
            sender=record.sender,
            sent_at=record.sent_at,
            arrived_at=record.arrived_at,
            fetched_at=record.fetched_at,
            size=record.size,
            outcome=record.outcome,
            reason=None if record.reason is None else ReasonOut.of(record.reason),
            rule=record.rule,
            rule_id=record.rule_id,
            decided_at=record.decided_at,
            later=record.later,
            documents=[DocumentRefOut.of(ref) for ref in view.documents],
            documents_hidden=view.hidden,
            steps=[MailStepOut.of(item) for item in record.steps],
            gone_at=record.gone_at,
            forgotten=record.forgotten_at is not None,
            waiting=record.waiting,
            next_rule=None if view.next_rule is None else MailRuleRefOut.of(view.next_rule),
        )


class MailPageOut(BaseModel):
    items: list[MailOut]
    total: int = Field(description="How many mails match in all.")
    next_offset: int | None = Field(
        description="Pass as `offset` for the next page; null on the last page."
    )

    @classmethod
    def of(cls, page: MailsPage, offset: int) -> "MailPageOut":
        return cls(
            items=[MailOut.of(view) for view in page.mails],
            total=page.total,
            next_offset=following_offset(offset, len(page.mails), page.total),
        )


class MailWaitingOut(BaseModel):
    rule: MailRuleRefOut
    mails: int = Field(description="Waiting mails it takes at the next fetch.")


class MailSummaryOut(BaseModel):
    """What the log of a mailbox holds."""

    counts: dict[MailOutcome, int] = Field(
        description="Mails by outcome (of `rule_id`, if given); outcomes without any left out."
    )
    rules: list[MailRuleRefOut] = Field(description="The mailbox's rules, to narrow the log.")
    waiting: list[MailWaitingOut] = Field(
        description=(
            "Mails no rule took yet that an active rule takes at the next fetch, by rule (those "
            "without any left out)."
        )
    )
    kept: int = Field(
        description=f"Mails whose head Lekto keeps, the latest {KEPT_RECORDS}: only these wait."
    )

    @classmethod
    def of(cls, summary: MailSummary) -> "MailSummaryOut":
        return cls(
            counts=dict(summary.counts),
            rules=[MailRuleRefOut.of(rule) for rule in summary.rules],
            waiting=[
                MailWaitingOut(rule=MailRuleRefOut.of(rule), mails=count)
                for rule, count in summary.waiting
            ],
            kept=KEPT_RECORDS,
        )
