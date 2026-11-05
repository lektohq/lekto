"""Mail rules: what a mailbox's mails bring in."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lekto.adapters.inbound.schemas import ReasonOut
from lekto.core.domain.changes import UNSET, Unset
from lekto.core.domain.condition_tree import MAX_CONDITIONS, MAX_DEPTH
from lekto.core.domain.ids import DocumentTypeId, SpaceId, UserId
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.mail import MAX_FOLDER, MAX_STEPS, MailAction, MailStep
from lekto.core.domain.mail_intake import MailOutcome, MailParts
from lekto.core.domain.mail_rules import (
    MAX_PRIORITY,
    MAX_VALUE,
    MIN_PRIORITY,
    MailConditions,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
    conditions_from_json,
    conditions_to_json,
)
from lekto.core.domain.validation import MAX_NAME
from lekto.core.services.mail_rules import Decider, DryRunMail

PARTS_HELP = (
    "What it takes: `all` (the attachments and the text), `attachments`, `text`, `nothing`."
)
AFTER_HELP = (
    "The steps on the mail on the server once taken, in order: `read`, `unread`, `flag` (with "
    "`value` a colour: `red`, `orange`, `yellow`, `green`, `blue`, `purple`, `gray`, as Apple "
    "Mail shows it), `unflag`, `add_keyword` and `remove_keyword` (with `value` an IMAP "
    "keyword), then at most one last: `move` (with `value` the folder) or `trash`. None twice; "
    f"at most {MAX_STEPS}. A step the server refuses is noted at the mailbox; the next ones go on."
)
CONDITIONS_HELP = (
    "A tree as a document rule's: a group of `all` or `any`, `not` turns it around; its items "
    f"are conditions or groups again, nested at most {MAX_DEPTH} deep, at most {MAX_CONDITIONS} "
    "conditions. "
    "Fields: `sender`, `recipient` (To or Cc), `to`, `cc` and `subject` with `contains`, `is`, "
    "`starts_with`, `ends_with` (an address or a name, regardless of case); `folder` with `is`; "
    "`attachments` with `present` or `missing` (attachments Lekto takes); `importance` with `is` "
    "(`high`, `normal`, `low`); `keyword` with `contains` (an IMAP keyword, regardless of "
    "case), `present` or `missing`; `flag` with `present`, `missing` or `is` (a colour: `red`, "
    "`orange`, `yellow`, `green`, `blue`, `purple`, `gray`). Null: every mail."
)


MAX_CONDITION_VALUE = max(MAX_VALUE, MAX_FOLDER)
"""A condition's value at most, before the domain checks it by its field (a folder's name may
be longer than a text)."""


class MailConditionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: MailField
    op: MailOperator
    value: str | None = Field(default=None, max_length=MAX_CONDITION_VALUE)


class MailStepBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: MailAction
    value: str | None = Field(default=None, max_length=MAX_FOLDER)

    def domain(self) -> MailStep:
        return MailStep(self.action, self.value)

    @classmethod
    def of(cls, step: MailStep) -> "MailStepBody":
        return cls(action=step.action, value=step.value)


# The same two models as `AllGroup` and `AnyGroup` of the document rules (`schemas/rules.py`)
# with the mail rules' condition; see the note there. Keep the four in step.
class MailAllGroup(BaseModel):
    """All items hold (and); `not` turns the result around."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all: list["MailConditionBody | MailAllGroup | MailAnyGroup"] = Field(
        min_length=1, max_length=MAX_CONDITIONS
    )
    negate: bool = Field(default=False, alias="not")


class MailAnyGroup(BaseModel):
    """At least one item holds (or); `not` turns the result around."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    any: list["MailConditionBody | MailAllGroup | MailAnyGroup"] = Field(
        min_length=1, max_length=MAX_CONDITIONS
    )
    negate: bool = Field(default=False, alias="not")


type MailGroup = MailAllGroup | MailAnyGroup


def _tree(group: MailGroup) -> MailConditions:
    data: JsonValue = group.model_dump(mode="json", by_alias=True, exclude_defaults=True)
    tree = conditions_from_json(data)
    assert tree is not None
    return tree


def _group_out(conditions: MailConditions | None) -> MailGroup | None:
    data = conditions_to_json(conditions)
    if data is None:
        return None
    return MailAnyGroup.model_validate(data) if "any" in data else MailAllGroup.model_validate(data)


class _Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(
        default=None, ge=MIN_PRIORITY, le=MAX_PRIORITY, description="Higher first."
    )
    conditions: MailAllGroup | MailAnyGroup | None = Field(
        default=None, description=CONDITIONS_HELP
    )
    parts: MailParts | None = Field(default=None, description=PARTS_HELP)
    user_id: UUID | None = Field(default=None, description="Whom it takes the mail for.")
    space_id: UUID | None = Field(
        default=None, description="A space the person files into; null: their personal one."
    )
    text_type_id: UUID | None = Field(
        default=None, description="The document type of the mail's text; null: Lekto decides."
    )
    after: list[MailStepBody] | None = Field(
        default=None, max_length=MAX_STEPS, description=AFTER_HELP
    )
    enabled: bool | None = None

    def changes(self, name: str | None) -> MailRuleChanges:
        given = self.model_fields_set

        def optional[T](
            key: str, value: UUID | None, kind: Callable[[UUID], T]
        ) -> T | Unset | None:
            if key not in given:
                return UNSET
            return None if value is None else kind(value)

        return MailRuleChanges(
            name=UNSET if name is None else name,
            priority=UNSET if self.priority is None else self.priority,
            conditions=(
                UNSET
                if "conditions" not in given
                else None
                if self.conditions is None
                else _tree(self.conditions)
            ),
            parts=UNSET if self.parts is None else self.parts,
            user_id=optional("user_id", self.user_id, UserId),
            space_id=optional("space_id", self.space_id, SpaceId),
            text_type_id=optional("text_type_id", self.text_type_id, DocumentTypeId),
            after=UNSET if self.after is None else tuple(item.domain() for item in self.after),
            enabled=UNSET if self.enabled is None else self.enabled,
        )


class MailRuleCreate(_Rule):
    """A new mail rule of a mailbox; what is left out gets the default (priority 100, no
    conditions: every mail, takes the attachments and the text, leaves the mail, active)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "mailbox_id": "01a1a7fc-702c-736e-a661-ff59645bdc52",
                    "name": "Bills of the utilities",
                    "conditions": {
                        "all": [
                            {"field": "sender", "op": "ends_with", "value": "@stadtwerke.example"}
                        ]
                    },
                    "user_id": "01a1a7fc-7013-741e-ae72-58401e634e5d",
                    "after": [
                        {"action": "read"},
                        {"action": "add_keyword", "value": "Lekto"},
                        {"action": "move", "value": "Erledigt"},
                    ],
                }
            ]
        },
    )

    mailbox_id: UUID
    name: str = Field(min_length=1, max_length=MAX_NAME)


class MailRulePatch(_Rule):
    """What changes; what is left out stays. `conditions`, `space_id`, `text_type_id`,
    `user_id` given as null clear it (no conditions: every mail). Switching it
    on clears why it was paused."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"enabled": False}]})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)


class MailRuleDryRun(MailRuleCreate):
    """A rule as the editor holds it, saved or not; `rule_id`: the stored one it stands for."""

    model_config = ConfigDict(extra="forbid")

    rule_id: UUID | None = Field(
        default=None, description="The rule being edited: the dry run puts this one in its place."
    )


class DryRunMailOut(BaseModel):
    """A mail fetched lately, and what would become of it with the rule."""

    subject: str
    sender: str
    folder: str
    sent_at: datetime | None
    arrived_at: datetime
    attachments: list[str] = Field(
        description="The names of the attachments Lekto takes (empty for one without a name)."
    )
    outcome: MailOutcome = Field(description="What became of it when it came.")
    matches: bool = Field(description="Whether the rule's conditions hold.")
    decider: Decider = Field(
        description=(
            "Who would decide it now: `rule` (this one), `other` (another rule before it, named "
            "in `rule`), `fallback` (the mailbox takes everything), `nothing` (no rule, the "
            "mailbox takes nothing)."
        )
    )
    rule: str | None

    @classmethod
    def of(cls, item: DryRunMail) -> "DryRunMailOut":
        record = item.record
        return cls(
            subject=record.subject,
            sender=record.sender,
            folder=record.folder,
            sent_at=record.sent_at,
            arrived_at=record.arrived_at,
            attachments=list(record.attachments),
            outcome=record.outcome,
            matches=item.matches,
            decider=item.decider,
            rule=item.rule,
        )


class MailRuleOut(BaseModel):
    id: UUID
    mailbox_id: UUID
    name: str
    priority: int
    conditions: MailAllGroup | MailAnyGroup | None = Field(description=CONDITIONS_HELP)
    parts: MailParts
    user_id: UUID | None
    space_id: UUID | None
    text_type_id: UUID | None
    after: list[MailStepBody] = Field(description=AFTER_HELP)
    enabled: bool
    disabled_reason: ReasonOut | None = Field(description="Why Lekto paused it; null otherwise.")
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, rule: MailRule) -> "MailRuleOut":
        return cls(
            id=rule.id,
            mailbox_id=rule.mailbox_id,
            name=rule.name,
            priority=rule.priority,
            conditions=_group_out(rule.conditions),
            parts=rule.parts,
            user_id=rule.user_id,
            space_id=rule.space_id,
            text_type_id=rule.text_type_id,
            after=[MailStepBody.of(step) for step in rule.after],
            enabled=rule.enabled,
            disabled_reason=(
                None if rule.disabled_reason is None else ReasonOut.of(rule.disabled_reason)
            ),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
