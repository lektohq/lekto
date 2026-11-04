"""Mail rules: what a mailbox's mails bring in (umsetzungsplan "Eingangskanal Mail", decision 12).

A mail rule belongs to one mailbox. Its conditions look at the mail (sender, recipients,
subject, the folder it lies in, whether it has attachments Lekto takes), all or any of them;
none means every mail. Of a mailbox's active rules the first that matches decides, by priority
(smaller first), the same priority by name; a mail no rule takes goes by the mailbox's fallback.

A rule takes the mail's attachments and text, the attachments, the text, or nothing; for one
person, into a space they edit (else their personal one); the text gets a fixed document type
or Lekto determines it; on the server the mail is left, marked as read, moved to a folder, or
moved to the trash. A rule whose person, space or type is gone or out of reach is paused with
that reason when a mail would need it.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, StrEnum

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, MailRuleId, SpaceId, UserId, new_id
from lekto.core.domain.mail import MailAction
from lekto.core.domain.mail_intake import MailDecision, MailParts, letters
from lekto.core.domain.mail_message import Address, MailMessage
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_name, require_utc

MAX_CONDITIONS = 20
MAX_VALUE = 500
MAX_FOLDER = 1000
DEFAULT_PRIORITY = 100
MIN_PRIORITY = 0
MAX_PRIORITY = 1000


class MailField(StrEnum):
    SENDER = "sender"  # the sender's address or name
    RECIPIENT = "recipient"  # an address or name it went to (To, Cc)
    SUBJECT = "subject"
    FOLDER = "folder"  # the folder of the mailbox it lies in
    ATTACHMENTS = "attachments"  # attachments Lekto takes


class MailOperator(StrEnum):
    CONTAINS = "contains"
    IS = "is"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    PRESENT = "present"
    MISSING = "missing"


_TEXT = frozenset(
    {MailOperator.CONTAINS, MailOperator.IS, MailOperator.STARTS_WITH, MailOperator.ENDS_WITH}
)
OPERATORS: dict[MailField, frozenset[MailOperator]] = {
    MailField.SENDER: _TEXT,
    MailField.RECIPIENT: _TEXT,
    MailField.SUBJECT: _TEXT,
    MailField.FOLDER: frozenset({MailOperator.IS}),
    MailField.ATTACHMENTS: frozenset({MailOperator.PRESENT, MailOperator.MISSING}),
}


@dataclass(frozen=True)
class MailFacts:
    """What the conditions look at: the texts of each field (an address and a name each), and
    whether there are attachments to take."""

    senders: tuple[str, ...]
    recipients: tuple[str, ...]
    subject: str
    folder: str
    attachments: bool


@dataclass(frozen=True)
class MailCondition:
    field: MailField
    op: MailOperator
    value: str | None = None

    def __post_init__(self) -> None:
        if self.op not in OPERATORS[self.field]:
            raise ValidationError(f"operator '{self.op}' does not apply to {self.field}")
        if self.op in (MailOperator.PRESENT, MailOperator.MISSING):
            if self.value is not None:
                raise ValidationError(f"'{self.op}' takes no value")
            return
        value = (self.value or "").strip()
        limit = MAX_FOLDER if self.field is MailField.FOLDER else MAX_VALUE
        if not value or len(value) > limit:
            raise ValidationError(f"{self.field}: a value of 1 to {limit} characters")
        object.__setattr__(self, "value", value)

    def holds(self, facts: MailFacts) -> bool:
        if self.field is MailField.ATTACHMENTS:
            return facts.attachments == (self.op is MailOperator.PRESENT)
        if self.field is MailField.FOLDER:
            return facts.folder == self.value
        texts = {
            MailField.SENDER: facts.senders,
            MailField.RECIPIENT: facts.recipients,
            MailField.SUBJECT: (facts.subject,),
        }[self.field]
        wanted = (self.value or "").casefold()
        return any(_compare(self.op, text.casefold(), wanted) for text in texts)


def _compare(op: MailOperator, text: str, wanted: str) -> bool:
    match op:
        case MailOperator.IS:
            return text == wanted
        case MailOperator.STARTS_WITH:
            return text.startswith(wanted)
        case MailOperator.ENDS_WITH:
            return text.endswith(wanted)
        case _:
            return wanted in text


class Unset(Enum):
    UNSET = "unset"


UNSET = Unset.UNSET


@dataclass(frozen=True, kw_only=True)
class MailRuleChanges:
    """A change of a mail rule; parts left UNSET stay as they are."""

    name: str | Unset = UNSET
    priority: int | Unset = UNSET
    any: bool | Unset = UNSET
    conditions: tuple[MailCondition, ...] | Unset = UNSET
    parts: MailParts | Unset = UNSET
    user_id: UserId | Unset | None = UNSET
    space_id: SpaceId | Unset | None = UNSET
    text_type_id: DocumentTypeId | Unset | None = UNSET
    after: MailAction | Unset = UNSET
    move_to: str | Unset | None = UNSET
    enabled: bool | Unset = UNSET


@dataclass(kw_only=True)
class MailRule:
    id: MailRuleId
    mailbox_id: MailboxId
    name: str
    priority: int
    any: bool  # any condition (or), else all of them (and)
    conditions: tuple[MailCondition, ...]
    parts: MailParts
    user_id: UserId | None  # whom it takes the mail for; none when it takes nothing
    space_id: SpaceId | None  # where to; none: the person's personal space
    text_type_id: DocumentTypeId | None  # the type of the text; none: Lekto determines it
    after: MailAction
    move_to: str | None  # with `MOVE`
    enabled: bool
    disabled_reason: Reason | None
    created_at: datetime
    updated_at: datetime
    version: int = 0

    @classmethod
    def create(
        cls, *, mailbox_id: MailboxId, changes: MailRuleChanges, now: datetime
    ) -> "MailRule":
        require_utc(now, "now")
        rule = cls(
            id=MailRuleId(new_id()),
            mailbox_id=mailbox_id,
            name="",
            priority=DEFAULT_PRIORITY,
            any=False,
            conditions=(),
            parts=MailParts.ALL,
            user_id=None,
            space_id=None,
            text_type_id=None,
            after=MailAction.NOTHING,
            move_to=None,
            enabled=True,
            disabled_reason=None,
            created_at=now,
            updated_at=now,
        )
        rule.change(changes, now=now)
        return rule

    def change(self, changes: MailRuleChanges, *, now: datetime) -> None:
        """Apply `changes`; ValidationError if the result is not a valid rule (nothing changes
        then). Switching it on clears the reason it was paused for."""
        require_utc(now, "now")
        before = replace(self)
        for name, value in vars(changes).items():
            if value is not UNSET:
                setattr(self, name, value)
        try:
            self._check()
        except ValidationError:
            for name, value in vars(before).items():
                setattr(self, name, value)
            raise
        if self.enabled:
            self.disabled_reason = None
        self.updated_at = now

    def pause(self, reason: Reason, *, now: datetime) -> None:
        """Switched off by Lekto, with the reason."""
        self.enabled = False
        self.disabled_reason = reason
        self.updated_at = now

    def matches(self, facts: MailFacts) -> bool:
        if not self.conditions:
            return True
        results = (condition.holds(facts) for condition in self.conditions)
        return any(results) if self.any else all(results)

    def decision(self) -> MailDecision:
        return MailDecision(
            user_id=self.user_id,
            space_id=self.space_id,
            parts=self.parts,
            body_type_id=self.text_type_id,
            after=self.after,
            move_to=self.move_to,
            rule=self.name,
        )

    def _check(self) -> None:
        self.name = require_name(self.name, "rule name")
        if (
            isinstance(self.priority, bool)
            or not isinstance(self.priority, int)
            or not MIN_PRIORITY <= self.priority <= MAX_PRIORITY
        ):
            raise ValidationError(f"priority: a whole number from {MIN_PRIORITY} to {MAX_PRIORITY}")
        if len(self.conditions) > MAX_CONDITIONS:
            raise ValidationError(f"conditions: at most {MAX_CONDITIONS}")
        takes = self.parts is not MailParts.NOTHING
        if takes and self.user_id is None:
            raise ValidationError("user_id: the person the mail is taken for")
        if not takes:
            self.user_id = self.space_id = self.text_type_id = None
        elif self.space_id is not None and self.user_id is None:
            raise ValidationError("space_id: only with a person")
        if self.after is MailAction.MOVE:
            folder = (self.move_to or "").strip()
            if not folder or len(folder) > MAX_FOLDER:
                raise ValidationError("move_to: the folder to move the mail to")
            self.move_to = folder
        else:
            self.move_to = None


def mail_facts(message: MailMessage, folder: str) -> MailFacts:
    """What the conditions of a rule look at in a mail lying in `folder`."""

    def texts(addresses: tuple[Address, ...]) -> tuple[str, ...]:
        return tuple(text for item in addresses for text in (item.address, item.name) if text)

    return MailFacts(
        senders=texts(message.sender),
        recipients=texts((*message.to, *message.cc)),
        subject=message.subject,
        folder=folder,
        attachments=any(letter.taken for letter in letters(message)),
    )


def first_match(rules: list[MailRule], facts: MailFacts) -> MailRule | None:
    """The first active rule that matches, by priority, the same priority by name."""
    ordered = sorted(
        (rule for rule in rules if rule.enabled),
        key=lambda rule: (rule.priority, rule.name.casefold()),
    )
    return next((rule for rule in ordered if rule.matches(facts)), None)
