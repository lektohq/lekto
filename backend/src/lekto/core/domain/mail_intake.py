"""What Lekto takes from a mail (umsetzungsplan "Eingangskanal Mail", decisions 6, 9 to 11).

A mail that only wraps an attached mail is unwrapped, layer by layer, to the innermost (at most
`MAX_FORWARDS`); its forwarders form the chain of its origin. A mail with several attached mails
gives a letter of each, and one of its own where it has text of its own. Of a letter Lekto
takes its text (as the `.eml` it stands in, set as PDF) and its attachments it can read (PDF,
images, mails), small images aside (logos, signatures); the rest stays and the head of the PDF
names it ("Nicht übernommen").
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from lekto.core.domain import media_types
from lekto.core.domain.ids import (
    DocumentId,
    DocumentTypeId,
    MailboxId,
    MailRecordId,
    SpaceId,
    UserId,
)
from lekto.core.domain.mail import MailStep
from lekto.core.domain.mail_message import Address, MailMessage, MailPart
from lekto.core.domain.mail_traits import Importance, MailMarks
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_utc

MAX_FORWARDS = 5
HEADROOM = 1024 * 1024
"""Bytes a mail has beyond its attachments: its header, its text."""


def mail_limit(upload_max: int) -> int:
    """The largest mail Lekto fetches: one whose attachment is as large as an upload may be
    (`LEKTO_UPLOAD_MAX_SIZE`), in Base64 (a third larger), with its header and text. A larger
    one is not fetched (the worker holds a mail in memory); its record and the mailbox say so."""
    return upload_max * 4 // 3 + HEADROOM


SMALL_IMAGE = 20 * 1024
"""An image smaller than this (bytes) is a logo or a signature: left out without a word."""


@dataclass(frozen=True)
class Letter:
    """A mail Lekto takes as one cover letter with its attachments. `forwarded_by`: who
    forwarded it, outermost first; `outer`: the wrapping mail's own text beside the others."""

    message: MailMessage
    forwarded_by: tuple[Address, ...] = ()
    outer: bool = False

    @property
    def taken(self) -> tuple[MailPart, ...]:
        return tuple(part for part in self.message.attachments if kept(part) and readable(part))

    @property
    def left(self) -> tuple[MailPart, ...]:
        """Attachments Lekto cannot read, named in the head of the cover letter."""
        return tuple(part for part in self.message.attachments if kept(part) and not readable(part))


def readable(part: MailPart) -> bool:
    """A file Lekto takes: by its content, as an upload."""
    return media_types.detect(part.data[: media_types.SNIFF_SIZE]) is not None


def kept(part: MailPart) -> bool:
    """Not a small image (a logo, a signature)."""
    return not (part.media_type.startswith("image/") and len(part.data) < SMALL_IMAGE)


def letters(message: MailMessage) -> list[Letter]:
    """The letters of a mail: unwrapped, and one for each of several attached mails."""
    chain: list[Address] = []
    current = message
    while len(current.messages) == 1 and not current.attachments and len(chain) < MAX_FORWARDS:
        chain.extend(current.sender[:1])
        current = current.messages[0]
    if not current.messages:
        return [Letter(current, tuple(chain))]
    found = []
    if _has_text(current) or current.attachments:
        found.append(Letter(current, tuple(chain), outer=True))
    for inner in current.messages:
        for letter in letters(inner):
            found.append(
                Letter(letter.message, (*chain, *current.sender[:1], *letter.forwarded_by))
            )
    return found


def taken_names(message: MailMessage) -> tuple[str, ...]:
    """The names of the attachments Lekto takes of a mail, across its letters (empty for one
    without a name)."""
    return tuple(part.filename or "" for letter in letters(message) for part in letter.taken)


def _has_text(message: MailMessage) -> bool:
    return bool((message.text or "").strip()) or bool((message.html or "").strip())


class MailParts(StrEnum):
    """What of a mail a rule takes."""

    ALL = "all"  # the text and the attachments
    ATTACHMENTS = "attachments"
    TEXT = "text"
    NOTHING = "nothing"


@dataclass(frozen=True, kw_only=True)
class MailDecision:
    """What becomes of a mail: taken for `user` (into `space`, else their personal one), which
    parts, the type of the text (`body_type_id`, none: open), and the steps on the server
    afterwards, in order. `rule`: the name of the rule that decided; None for the mailbox's
    fallback."""

    user_id: UserId | None  # none when it takes nothing
    space_id: SpaceId | None = None
    parts: MailParts = MailParts.ALL
    body_type_id: DocumentTypeId | None = None
    after: tuple[MailStep, ...] = ()
    rule: str | None = None


KEPT_RECORDS = 500
"""A mailbox's records that keep what the mail's head said (Tobi, 05.11.2026): the dry run of a
mail rule looks at the latest fifty; the rest let go of it (`MailRecord.forget`) and stay only
so that no mail is fetched twice."""


class MailOutcome(StrEnum):
    """What became of a fetched mail."""

    TAKEN = "taken"  # documents made (or found: duplicates)
    NO_RULE = "no_rule"  # no rule took it, and the fallback takes nothing
    NOTHING = "nothing"  # taken, but nothing in it to take
    KNOWN = "known"  # its Message-ID came before (another folder or mailbox)
    TOO_LARGE = "too_large"
    FAILED = "failed"


@dataclass(kw_only=True)
class MailRecord:
    """A mail Lekto fetched from a mailbox's folder: it is not fetched again (by the folder's
    UIDVALIDITY and its UID; by its Message-ID across folders and mailboxes)."""

    id: MailRecordId
    mailbox_id: MailboxId
    folder: str
    uidvalidity: int
    uid: int
    message_id: str | None
    sender: str
    subject: str
    sent_at: datetime | None
    arrived_at: datetime
    size: int
    outcome: MailOutcome
    reason: Reason | None = None
    rule: str | None = None
    documents: int = 0
    fetched_at: datetime
    senders: tuple[str, ...] = ()
    """The sender's addresses and names, as the conditions of a mail rule look at them."""
    recipients: tuple[str, ...] = ()
    """The addresses and names it went to (To, Cc), likewise."""
    attachments: tuple[str, ...] = ()
    """The names of the attachments Lekto takes of it (empty for one without a name)."""
    to: tuple[str, ...] = ()
    """The addresses and names in To, as `recipients`; Cc likewise."""
    cc: tuple[str, ...] = ()
    importance: Importance | None = None
    """As its header gave it; none for a mail fetched before Lekto read it, or too large."""
    marks: MailMarks | None = None
    """Its keywords and flag on the server when it was fetched; none likewise."""
    forgotten_at: datetime | None = None
    """When the record let go of what the mail's head said (`forget`); none while it keeps it."""

    def __post_init__(self) -> None:
        require_utc(self.fetched_at, "fetched_at")

    def forget(self, *, now: datetime) -> None:
        """Let go of what the mail's head said: sender, subject, recipients, attachments,
        importance, marks and the reason (it names the subject). The record stays, with its
        UIDs, Message-ID and outcome, so that the mail is not fetched twice."""
        require_utc(now, "now")
        self.sender = ""
        self.subject = ""
        self.reason = None
        self.senders = ()
        self.recipients = ()
        self.to = ()
        self.cc = ()
        self.attachments = ()
        self.importance = None
        self.marks = None
        self.forgotten_at = now


class OriginRole(StrEnum):
    COVER = "cover"  # the letter's text
    ATTACHMENT = "attachment"


@dataclass(kw_only=True)
class MailOrigin:
    """Where a document came from: the mail, the mailbox and the rule that took it. `letter`
    numbers the letters of the mail (`letters`); an outer one (`outer`) refers to the others.
    `related`: documents Lekto had already that a cover letter refers to (duplicates)."""

    document_id: DocumentId
    record_id: MailRecordId
    mailbox_id: MailboxId
    mailbox: str
    rule: str | None
    role: OriginRole
    letter: int
    outer: bool = False
    message_id: str | None
    sender: tuple[Address, ...]
    to: tuple[Address, ...]
    cc: tuple[Address, ...]
    subject: str
    sent_at: datetime | None
    arrived_at: datetime
    forwarded_by: tuple[Address, ...] = ()
    filename: str | None = None
    related: tuple[DocumentId, ...] = field(default_factory=tuple)
    body_type_id: DocumentTypeId | None = None
    """The type the cover letter gets (the rules node sets it, before the document rules)."""
    importance: Importance | None = None
    """The letter's importance, as its header gives it; none for a document taken before."""
    marks: MailMarks | None = None
    """The keywords and flag the mail had on the server when it was fetched; none likewise."""

    @property
    def id(self) -> DocumentId:
        return self.document_id
