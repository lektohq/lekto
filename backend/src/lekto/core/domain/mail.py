"""Mailboxes: the intake channel mail (`.idea/decisions/2026-11-04-mail.md`).

Admins set up mailboxes that Lekto fetches from, every `interval`: a server, an account, the
folders to look in, and from when on. The password is stored encrypted (`SecretCipher`, bound
to the mailbox's id) and never shown again. What a mail brings in, for whom and where, the mail
rules decide; a mail no rule takes goes by the mailbox's `fallback`: nothing, or everything for
one person. The mail text becomes a document of the type `body_type_id` where a rule does not
say otherwise.

`status` is what the last fetches found: when Lekto last tried and last succeeded, why the last
attempt failed (a reason), and how many mails and documents it has taken.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

from lekto.core.domain.changes import UNSET, Unset, apply_changes
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, UserId, new_id
from lekto.core.domain.mail_traits import (
    COLOR_BITS,
    FLAGGED,
    SEEN,
    FlagColor,
    check_mail_value,
    flag_bits,
)
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_utc

MAX_NAME = 100
MAX_HOST = 255
MAX_USERNAME = 320
MAX_FOLDERS = 20
MAX_FOLDER = 1000  # characters of a folder's name
MIN_INTERVAL = timedelta(minutes=1)
MAX_INTERVAL = timedelta(hours=24)
DEFAULT_INTERVAL = timedelta(minutes=5)
DEFAULT_FOLDER = "INBOX"


class MailSecurity(StrEnum):
    """How the connection is secured: TLS from the start (IMAPS, port 993), TLS after the
    greeting (STARTTLS, port 143), or none (a server in one's own network)."""

    TLS = "tls"
    STARTTLS = "starttls"
    NONE = "none"


class FetchStart(StrEnum):
    """Which mails a mailbox takes: those that came after it was set up, those from a day on,
    or the unread ones (whenever they came)."""

    SINCE_SETUP = "since_setup"
    SINCE_DATE = "since_date"
    UNREAD = "unread"


class Fallback(StrEnum):
    """What a mail no rule takes brings in: nothing, or everything (for `fallback_user_id`)."""

    NOTHING = "nothing"
    EVERYTHING = "everything"


class MailAction(StrEnum):
    """A step on a mail on the server once Lekto has taken it (Tobi, 05.11.2026: an ordered
    list of them): marked read or unread, flagged in a colour or not, a keyword added or
    removed; then at most one that ends it, moved to a folder or to the trash."""

    READ = "read"
    UNREAD = "unread"
    FLAG = "flag"  # with a colour (`mail_traits.FlagColor`)
    UNFLAG = "unflag"
    ADD_KEYWORD = "add_keyword"  # with the keyword
    REMOVE_KEYWORD = "remove_keyword"  # with the keyword
    MOVE = "move"  # with the folder
    TRASH = "trash"


ENDING = frozenset({MailAction.MOVE, MailAction.TRASH})
"""The steps after which the mail is gone from its folder: last, and at most one."""
MAX_STEPS = 10


def step_flags(step: "MailStep") -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The IMAP flags a step adds and removes (none for a move or the trash): a flag's colour
    as Apple Mail's bits, the other bits taken away."""
    match step.action:
        case MailAction.READ:
            return (SEEN,), ()
        case MailAction.UNREAD:
            return (), (SEEN,)
        case MailAction.FLAG:
            bits = flag_bits(FlagColor(str(step.value)))
            return (FLAGGED, *bits), tuple(bit for bit in COLOR_BITS if bit not in bits)
        case MailAction.UNFLAG:
            return (), (FLAGGED, *COLOR_BITS)
        case MailAction.ADD_KEYWORD:
            return (str(step.value),), ()
        case MailAction.REMOVE_KEYWORD:
            return (), (str(step.value),)
    return (), ()


@dataclass(frozen=True)
class MailStep:
    """One step on a mail on the server; `value`: the colour of `FLAG`, the keyword of
    `ADD_KEYWORD` and `REMOVE_KEYWORD`, the folder of `MOVE`, none for the others."""

    action: MailAction
    value: str | None = None

    def __post_init__(self) -> None:
        value = None if self.value is None else self.value.strip()
        match self.action:
            case MailAction.FLAG:
                check_mail_value("flag", value, label="flag")
            case MailAction.ADD_KEYWORD | MailAction.REMOVE_KEYWORD:
                check_mail_value("keyword", value, label=self.action.value)
            case MailAction.MOVE:
                if not value or len(value) > MAX_FOLDER:
                    raise ValidationError("move: the folder to move the mail to")
            case _:
                if value is not None:
                    raise ValidationError(f"{self.action} takes no value")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class StepOutcome:
    """A step done on a mail on the server, and why the server refused it (none: done)."""

    step: MailStep
    failed: Reason | None = None


def check_steps(steps: tuple[MailStep, ...]) -> None:
    """At most `MAX_STEPS`, none twice, and one that ends it only last. ValidationError
    otherwise."""
    if len(steps) > MAX_STEPS:
        raise ValidationError(f"after: at most {MAX_STEPS} steps")
    if len(set(steps)) != len(steps):
        raise ValidationError("after: a step twice")
    if any(step.action in ENDING for step in steps[:-1]):
        raise ValidationError("after: moving or trashing comes last, once")


@dataclass(frozen=True)
class MailLogin:
    """Where and as whom to sign in to a mail server (IMAP)."""

    host: str
    port: int
    security: MailSecurity
    username: str
    password: str = field(repr=False)


@dataclass(frozen=True, kw_only=True)
class MailboxStatus:
    """What the fetches of a mailbox found; nothing before the first."""

    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    error: Reason | None = None  # why the last attempt failed; none after a success
    mails: int = 0  # mails taken in
    documents: int = 0  # documents made from them
    skipped_at: datetime | None = None  # when a mail was last left out, too large
    skipped: Reason | None = None  # which and why
    step_failed_at: datetime | None = None  # when a step on a mail on the server last failed
    step_failed: Reason | None = None  # which, on which mail, and the server's answer
    keywords: tuple[str, ...] = ()  # the keywords its folders knew at the last fetch
    own_keywords: bool | None = None  # whether the server stores Lekto's own; none: not known


@dataclass(frozen=True, kw_only=True)
class MailboxChanges:
    """A change of a mailbox; parts left UNSET stay as they are. `since` counts only with
    `SINCE_DATE`, `fallback_user_id` only with `EVERYTHING`: otherwise they are cleared."""

    name: str | Unset = UNSET
    host: str | Unset = UNSET
    port: int | Unset = UNSET
    security: MailSecurity | Unset = UNSET
    username: str | Unset = UNSET
    folders: tuple[str, ...] | Unset = UNSET
    interval: timedelta | Unset = UNSET
    start: FetchStart | Unset = UNSET
    since: date | Unset | None = UNSET
    fallback: Fallback | Unset = UNSET
    fallback_user_id: UserId | Unset | None = UNSET
    body_type_id: DocumentTypeId | Unset | None = UNSET
    enabled: bool | Unset = UNSET


@dataclass(kw_only=True)
class Mailbox:
    id: MailboxId
    name: str
    host: str
    port: int
    security: MailSecurity
    username: str
    encrypted_password: bytes = field(repr=False)
    folders: tuple[str, ...]
    interval: timedelta
    start: FetchStart
    since: date | None  # with `SINCE_DATE`
    fallback: Fallback
    fallback_user_id: UserId | None  # with `EVERYTHING`
    body_type_id: DocumentTypeId | None
    enabled: bool
    status: MailboxStatus
    created_at: datetime
    updated_at: datetime
    version: int = 0

    @classmethod
    def create(
        cls,
        *,
        name: str,
        host: str,
        port: int,
        security: MailSecurity,
        username: str,
        encrypted_password: bytes,
        folders: tuple[str, ...] = (DEFAULT_FOLDER,),
        interval: timedelta = DEFAULT_INTERVAL,
        start: FetchStart = FetchStart.SINCE_SETUP,
        since: date | None = None,
        fallback: Fallback = Fallback.NOTHING,
        fallback_user_id: UserId | None = None,
        body_type_id: DocumentTypeId | None = None,
        enabled: bool = True,
        now: datetime,
        id: MailboxId | None = None,
    ) -> "Mailbox":
        require_utc(now, "now")
        mailbox = cls(
            id=id or MailboxId(new_id()),
            name=name,
            host=host,
            port=port,
            security=security,
            username=username,
            encrypted_password=encrypted_password,
            folders=folders,
            interval=interval,
            start=start,
            since=since,
            fallback=fallback,
            fallback_user_id=fallback_user_id,
            body_type_id=body_type_id,
            enabled=enabled,
            status=MailboxStatus(),
            created_at=now,
            updated_at=now,
        )
        mailbox._normalise()
        return mailbox

    def change(self, changes: MailboxChanges, *, now: datetime) -> None:
        """Apply `changes`; ValidationError if the result is not a valid mailbox (nothing is
        changed then)."""
        require_utc(now, "now")
        apply_changes(self, changes, self._normalise)
        self.updated_at = now

    def set_password(self, encrypted: bytes, *, now: datetime) -> None:
        require_utc(now, "now")
        self.encrypted_password = encrypted
        self.updated_at = now

    def record(self, status: MailboxStatus) -> None:
        """What a fetch found (no change of the settings: `updated_at` stays)."""
        self.status = status

    def _normalise(self) -> None:
        self.name = self.name.strip()
        if not self.name or len(self.name) > MAX_NAME:
            raise ValidationError(f"name: 1 to {MAX_NAME} characters")
        self.host = self.host.strip()
        if not self.host or any(character.isspace() for character in self.host):
            raise ValidationError("host: a server name or address")
        if len(self.host) > MAX_HOST:
            raise ValidationError(f"host: at most {MAX_HOST} characters")
        if not 1 <= self.port <= 65535:
            raise ValidationError("port: 1 to 65535")
        self.username = self.username.strip()
        if not self.username or len(self.username) > MAX_USERNAME:
            raise ValidationError(f"username: 1 to {MAX_USERNAME} characters")
        folders = tuple(dict.fromkeys(folder.strip() for folder in self.folders))
        if not folders or "" in folders or len(folders) > MAX_FOLDERS:
            raise ValidationError(f"folders: 1 to {MAX_FOLDERS}, none empty")
        self.folders = folders
        if not MIN_INTERVAL <= self.interval <= MAX_INTERVAL:
            raise ValidationError("interval: from one minute to one day")
        if self.start is not FetchStart.SINCE_DATE:
            self.since = None
        elif self.since is None:
            raise ValidationError("since: a day when the mailbox starts from a day")
        if self.fallback is not Fallback.EVERYTHING:
            self.fallback_user_id = None
        elif self.fallback_user_id is None:
            raise ValidationError("fallback_user_id: the person everything is taken for")


def password_context(id: MailboxId) -> bytes:
    """Binds an encrypted password to its mailbox."""
    return b"mailbox-password:" + id.bytes
