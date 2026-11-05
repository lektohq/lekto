"""Mail rules: what a mailbox's mails bring in (umsetzungsplan "Eingangskanal Mail", decision 12).

A mail rule belongs to one mailbox. Its conditions look at the mail (sender, recipients,
subject, the folder it lies in, whether it has attachments Lekto takes), in the tree every rule
has (`condition_tree`: groups of all or any, turned around or not); none means every mail. Of
a mailbox's active rules the first that matches decides, by priority (higher first, as with
document rules), the same priority by name; a mail no rule takes goes by the mailbox's
fallback.

A rule takes the mail's attachments and text, the attachments, the text, or nothing; for one
person, into a space they edit (else their personal one); the text gets a fixed document type
or Lekto determines it; on the server steps follow in order (`mail.MailStep`: read or unread,
flagged or not, keywords added or removed), and at most one last that moves the mail to a
folder or to the trash. A rule whose person, space or type is gone or out of reach is paused with
that reason when a mail would need it.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum, StrEnum

from lekto.core.domain.condition_tree import Group, check_limits, group_from_json, group_to_json
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, MailRuleId, SpaceId, UserId, new_id
from lekto.core.domain.json_value import JsonObject, JsonValue, require_object
from lekto.core.domain.mail import MAX_FOLDER, MailStep, check_steps
from lekto.core.domain.mail_intake import MailDecision, MailParts, MailRecord, letters
from lekto.core.domain.mail_message import Address, MailMessage
from lekto.core.domain.mail_traits import (
    FlagColor,
    Importance,
    MailMarks,
    flag_holds,
    importance_holds,
    is_keyword,
    keyword_holds,
)
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_name, require_utc

MAX_VALUE = 500
DEFAULT_PRIORITY = 100
MIN_PRIORITY = 0
MAX_PRIORITY = 1000


class MailField(StrEnum):
    SENDER = "sender"  # the sender's address or name
    RECIPIENT = "recipient"  # an address or name it went to (To or Cc)
    TO = "to"  # an address or name in To
    CC = "cc"  # an address or name in Cc
    SUBJECT = "subject"
    FOLDER = "folder"  # the folder of the mailbox it lies in
    ATTACHMENTS = "attachments"  # attachments Lekto takes
    IMPORTANCE = "importance"  # high, normal or low (`mail_traits`)
    KEYWORD = "keyword"  # an IMAP keyword on the server (a tag)
    FLAG = "flag"  # flagged, in a colour (Apple Mail's)


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
_THERE = frozenset({MailOperator.PRESENT, MailOperator.MISSING})
OPERATORS: dict[MailField, frozenset[MailOperator]] = {
    MailField.SENDER: _TEXT,
    MailField.RECIPIENT: _TEXT,
    MailField.TO: _TEXT,
    MailField.CC: _TEXT,
    MailField.SUBJECT: _TEXT,
    MailField.FOLDER: frozenset({MailOperator.IS}),
    MailField.ATTACHMENTS: _THERE,
    MailField.IMPORTANCE: frozenset({MailOperator.IS}),
    MailField.KEYWORD: _THERE | {MailOperator.CONTAINS},
    MailField.FLAG: _THERE | {MailOperator.IS},
}


@dataclass(frozen=True, kw_only=True)
class MailFacts:
    """What the conditions look at: the texts of each field (an address and a name each),
    whether there are attachments to take, the importance and the marks on the server (none
    for a mail fetched before Lekto read them: their conditions hold nothing)."""

    senders: tuple[str, ...]
    recipients: tuple[str, ...]
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    subject: str
    folder: str
    attachments: bool
    importance: Importance | None = None
    marks: MailMarks | None = None


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
        match self.field:
            case MailField.IMPORTANCE:
                if value not in {item.value for item in Importance}:
                    raise ValidationError("importance: high, normal or low")
            case MailField.FLAG:
                if value not in {item.value for item in FlagColor}:
                    raise ValidationError(f"flag: a colour, not {value!r}")
            case MailField.KEYWORD:
                if not is_keyword(value):
                    raise ValidationError(f"keyword: not one IMAP can carry: {value!r}")
            case _:
                limit = MAX_FOLDER if self.field is MailField.FOLDER else MAX_VALUE
                if not value or len(value) > limit:
                    raise ValidationError(f"{self.field}: a value of 1 to {limit} characters")
        object.__setattr__(self, "value", value)

    def holds(self, facts: MailFacts) -> bool:
        match self.field:
            case MailField.ATTACHMENTS:
                return facts.attachments == (self.op is MailOperator.PRESENT)
            case MailField.FOLDER:
                return facts.folder == self.value
            case MailField.IMPORTANCE:
                return importance_holds(facts.importance, self.value or "")
            case MailField.KEYWORD:
                return keyword_holds(facts.marks, self.op.value, self.value)
            case MailField.FLAG:
                return flag_holds(facts.marks, self.op.value, self.value)
        texts = {
            MailField.SENDER: facts.senders,
            MailField.RECIPIENT: facts.recipients,
            MailField.TO: facts.to,
            MailField.CC: facts.cc,
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


type MailConditions = Group[MailCondition]


def condition_to_json(condition: MailCondition) -> JsonObject:
    data: JsonObject = {"field": condition.field.value, "op": condition.op.value}
    if condition.value is not None:
        data["value"] = condition.value
    return data


def condition_from_json(data: JsonValue, where: str = "condition") -> MailCondition:
    object_ = require_object(data, where)
    unknown = sorted(set(object_) - {"field", "op", "value"})
    if unknown:
        raise ValidationError(f"{where}: unknown key '{unknown[0]}'")
    value = object_.get("value")
    if value is not None and not isinstance(value, str):
        raise ValidationError(f"{where}.value: expected a text")
    try:
        return MailCondition(
            MailField(str(object_.get("field"))), MailOperator(str(object_.get("op"))), value
        )
    except ValueError as error:
        raise ValidationError(f"{where}: {error}") from None


def conditions_to_json(conditions: MailConditions | None) -> JsonObject | None:
    """The tree in the JSON form of every rule's; None: every mail."""
    return None if conditions is None else group_to_json(conditions, condition_to_json)


def conditions_from_json(data: JsonValue) -> MailConditions | None:
    return None if data is None else group_from_json(data, condition_from_json)


class Unset(Enum):
    UNSET = "unset"


UNSET = Unset.UNSET


@dataclass(frozen=True, kw_only=True)
class MailRuleChanges:
    """A change of a mail rule; parts left UNSET stay as they are."""

    name: str | Unset = UNSET
    priority: int | Unset = UNSET
    conditions: MailConditions | Unset | None = UNSET
    parts: MailParts | Unset = UNSET
    user_id: UserId | Unset | None = UNSET
    space_id: SpaceId | Unset | None = UNSET
    text_type_id: DocumentTypeId | Unset | None = UNSET
    after: tuple[MailStep, ...] | Unset = UNSET
    enabled: bool | Unset = UNSET


@dataclass(kw_only=True)
class MailRule:
    id: MailRuleId
    mailbox_id: MailboxId
    name: str
    priority: int
    conditions: MailConditions | None  # none: every mail
    parts: MailParts
    user_id: UserId | None  # whom it takes the mail for; none when it takes nothing
    space_id: SpaceId | None  # where to; none: the person's personal space
    text_type_id: DocumentTypeId | None  # the type of the text; none: Lekto determines it
    after: tuple[MailStep, ...]  # on the server, in order; a move or the trash last
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
            conditions=None,
            parts=MailParts.ALL,
            user_id=None,
            space_id=None,
            text_type_id=None,
            after=(),
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
        if self.conditions is None:
            return True
        return self.conditions.holds(lambda condition: condition.holds(facts))

    def decision(self) -> MailDecision:
        return MailDecision(
            user_id=self.user_id,
            space_id=self.space_id,
            parts=self.parts,
            body_type_id=self.text_type_id,
            after=self.after,
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
        if self.conditions is not None:
            check_limits([self.conditions])
        takes = self.parts is not MailParts.NOTHING
        if takes and self.user_id is None:
            raise ValidationError("user_id: the person the mail is taken for")
        if not takes:
            self.user_id = self.space_id = self.text_type_id = None
        elif self.space_id is not None and self.user_id is None:
            raise ValidationError("space_id: only with a person")
        check_steps(self.after)


def mail_texts(addresses: tuple[Address, ...]) -> tuple[str, ...]:
    """The addresses and names conditions on addresses look at."""
    return tuple(text for item in addresses for text in (item.address, item.name) if text)


def mail_facts(message: MailMessage, folder: str, flags: frozenset[str] | None = None) -> MailFacts:
    """What the conditions of a rule look at in a mail lying in `folder` with IMAP `flags`
    (none: not known)."""
    return MailFacts(
        senders=mail_texts(message.sender),
        recipients=mail_texts((*message.to, *message.cc)),
        to=mail_texts(message.to),
        cc=mail_texts(message.cc),
        subject=message.subject,
        folder=folder,
        attachments=any(letter.taken for letter in letters(message)),
        importance=message.importance,
        marks=None if flags is None else MailMarks.of_flags(flags),
    )


def record_facts(record: MailRecord) -> MailFacts:
    """What the conditions of a rule look at in a mail fetched before, as its record keeps it."""
    return MailFacts(
        senders=record.senders,
        recipients=record.recipients,
        to=record.to,
        cc=record.cc,
        subject=record.subject,
        folder=record.folder,
        attachments=bool(record.attachments),
        importance=record.importance,
        marks=record.marks,
    )


def first_match(rules: list[MailRule], facts: MailFacts) -> MailRule | None:
    """The first active rule that matches, by priority (higher first), the same priority by
    name."""
    ordered = sorted(
        (rule for rule in rules if rule.enabled),
        key=lambda rule: (-rule.priority, rule.name.casefold()),
    )
    return next((rule for rule in ordered if rule.matches(facts)), None)
