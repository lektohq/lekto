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
folder or to the trash. A rule whose person, space or type is deleted (or the person
deactivated) is paused with that reason at once (`services.rules.references`); one that is out of
reach otherwise (the person lost the right to the space) when a mail would need it.

A stored rule is read as a valid one: its conditions and steps check themselves as they are
built (`conditions_from_json`, `steps_from_json`). One that cannot be read any more (a limit
tightened without a revision, a row written by hand) comes paused with the reason
`MAIL_RULE_UNREADABLE` and without its conditions and steps, so that the mailbox's other rules
still fetch; it takes a change only with both anew (`change`). Whoever tightens a limit here
(a keyword's length, a colour, an operator of a field) still brings a revision that turns the
stored rows into what the limit allows, as revisions 0062 and 0064 did (Tobi, 05.11.2026).
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from lekto.core.domain.changes import UNSET, Unset, apply_changes
from lekto.core.domain.condition_tree import Group, check_limits, group_from_json, group_to_json
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentTypeId, MailboxId, MailRuleId, SpaceId, UserId, new_id
from lekto.core.domain.json_value import JsonObject, JsonValue, require_object
from lekto.core.domain.mail import MAX_FOLDER, MailAction, MailStep, check_steps
from lekto.core.domain.mail_intake import MailDecision, MailParts, MailRecord, letters
from lekto.core.domain.mail_message import MailMessage, address_texts
from lekto.core.domain.mail_traits import (
    MAIL_OPERATORS,
    MailHead,
    MailMarks,
    check_mail_value,
    flag_holds,
    importance_holds,
    keyword_holds,
)
from lekto.core.domain.reasons import Reason, ReasonCode
from lekto.core.domain.rules import DEFAULT_PRIORITY as DEFAULT_PRIORITY
from lekto.core.domain.rules import MAX_PRIORITY as MAX_PRIORITY
from lekto.core.domain.rules import MIN_PRIORITY as MIN_PRIORITY
from lekto.core.domain.rules import check_priority
from lekto.core.domain.sorting import sort_key
from lekto.core.domain.validation import require_name, require_utc


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


_OWN_OPERATORS: dict[MailField, frozenset[str]] = {
    MailField.FOLDER: frozenset({"is"}),
    MailField.ATTACHMENTS: frozenset({"present", "missing"}),
}
OPERATORS: dict[MailField, frozenset[MailOperator]] = {
    field: frozenset(
        MailOperator(op) for op in _OWN_OPERATORS.get(field) or MAIL_OPERATORS[field.value]
    )
    for field in MailField
}


@dataclass(frozen=True, kw_only=True)
class MailFacts(MailHead):
    """What a mail rule's conditions look at: the mail's head, the folder of the mailbox it
    lies in, and whether there are attachments to take."""

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
        if self.field is MailField.FOLDER:
            if not value or len(value) > MAX_FOLDER:
                raise ValidationError(f"folder: a value of 1 to {MAX_FOLDER} characters")
        else:
            check_mail_value(self.field.value, value, label=self.field.value)
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
        return facts.text_holds(self.field.value, self.op.value, self.value or "")


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


def steps_to_json(steps: tuple[MailStep, ...]) -> list[JsonValue]:
    """The steps in the JSON form a rule's are stored in."""
    found: list[JsonValue] = []
    for step in steps:
        data: JsonObject = {"action": step.action.value}
        if step.value is not None:
            data["value"] = step.value
        found.append(data)
    return found


def steps_from_json(data: JsonValue) -> tuple[MailStep, ...]:
    """The steps of `data`, checked as a rule's (`check_steps`); ValidationError otherwise."""
    if not isinstance(data, list):
        raise ValidationError("after: expected a list")
    steps = []
    for index, item in enumerate(data):
        where = f"after[{index}]"
        object_ = require_object(item, where)
        unknown = sorted(set(object_) - {"action", "value"})
        if unknown:
            raise ValidationError(f"{where}: unknown key '{unknown[0]}'")
        value = object_.get("value")
        if value is not None and not isinstance(value, str):
            raise ValidationError(f"{where}.value: expected a text")
        try:
            steps.append(MailStep(MailAction(str(object_.get("action"))), value))
        except (ValueError, ValidationError) as error:
            raise ValidationError(f"{where}: {error}") from None
    check_steps(tuple(steps))
    return tuple(steps)


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

    @property
    def unreadable(self) -> bool:
        """Read without its conditions and steps (`MAIL_RULE_UNREADABLE`)."""
        reason = self.disabled_reason
        return reason is not None and reason.code is ReasonCode.MAIL_RULE_UNREADABLE

    def change(self, changes: MailRuleChanges, *, now: datetime) -> None:
        """Apply `changes`; ValidationError if the result is not a valid rule (nothing changes
        then). Switching it on clears the reason it was paused for. A rule read without its
        conditions and steps takes a change only with both anew; that ends the pause, and the
        rule stays off until switched on."""
        require_utc(now, "now")
        unreadable = self.unreadable
        if unreadable and (changes.conditions is UNSET or changes.after is UNSET):
            raise ValidationError(
                "the stored rule cannot be read; save it anew with its conditions and steps"
            )
        apply_changes(self, changes, self._check)
        if self.enabled or unreadable:
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
            rule_id=self.id,
        )

    def _check(self) -> None:
        self.name = require_name(self.name, "rule name")
        check_priority(self.priority)
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


def mail_facts(message: MailMessage, folder: str, flags: frozenset[str] | None = None) -> MailFacts:
    """What the conditions of a rule look at in a mail lying in `folder` with IMAP `flags`
    (none: not known)."""
    return MailFacts(
        senders=address_texts(message.sender),
        recipients=address_texts((*message.to, *message.cc)),
        to=address_texts(message.to),
        cc=address_texts(message.cc),
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


def rule_order(rule: MailRule) -> tuple[int, str, str]:
    """The order in which a mailbox's rules are asked, and listed: by priority (higher first),
    the same priority by name as every list sorts names (`sort_key`, DIN 5007), then by id."""
    return (-rule.priority, sort_key(rule.name), str(rule.id))


def first_match(rules: list[MailRule], facts: MailFacts) -> MailRule | None:
    """The first active rule that matches, in `rule_order`."""
    ordered = sorted((rule for rule in rules if rule.enabled), key=rule_order)
    return next((rule for rule in ordered if rule.matches(facts)), None)
