"""Mailboxes: the intake channel mail (`.idea/umsetzungsplan.md`, "Eingangskanal Mail").

Admins set up mailboxes that Lekto fetches from, every `interval`: a server, an account, the
folders to look in, and from when on. The password is stored encrypted (`SecretCipher`, bound
to the mailbox's id) and never shown again. What a mail brings in, for whom and where, the mail
rules decide; a mail no rule takes goes by the mailbox's `fallback`: nothing, or everything for
one person. The mail text becomes a document of the type `body_type_id` where a rule does not
say otherwise.

`status` is what the last fetches found: when Lekto last tried and last succeeded, why the last
attempt failed (a reason), and how many mails and documents it has taken.
"""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from enum import Enum, StrEnum

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, UserId, new_id
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_utc

MAX_NAME = 100
MAX_FOLDERS = 20
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


class Unset(Enum):
    UNSET = "unset"


UNSET = Unset.UNSET
"""Marks a part of `MailboxChanges` that is left as it is."""


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
        before = replace(self)
        for name, value in vars(changes).items():
            if value is not UNSET:
                setattr(self, name, value)
        try:
            self._normalise()
        except ValidationError:
            for name, value in vars(before).items():
                setattr(self, name, value)
            raise
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
        if not 1 <= self.port <= 65535:
            raise ValidationError("port: 1 to 65535")
        self.username = self.username.strip()
        if not self.username:
            raise ValidationError("username: required")
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
