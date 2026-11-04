"""Mail rules: what a mailbox's mails bring in."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lekto.adapters.inbound.schemas import ReasonOut
from lekto.core.domain.ids import DocumentTypeId, SpaceId, UserId
from lekto.core.domain.mail import MailAction
from lekto.core.domain.mail_intake import MailOutcome, MailParts
from lekto.core.domain.mail_rules import (
    MAX_CONDITIONS,
    MAX_FOLDER,
    MAX_PRIORITY,
    MIN_PRIORITY,
    UNSET,
    MailCondition,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
    Unset,
)
from lekto.core.domain.validation import MAX_NAME
from lekto.core.services.mail_rules import Decider, DryRunMail

PARTS_HELP = (
    "What it takes: `all` (the attachments and the text), `attachments`, `text`, `nothing`."
)
AFTER_HELP = (
    "What becomes of the mail on the server: `nothing`, `read` (marked as read), `move` (to "
    "`move_to`), `trash`."
)
CONDITIONS_HELP = (
    "Fields: `sender`, `recipient` (To, Cc) and `subject` with `contains`, `is`, `starts_with`, "
    "`ends_with` (an address or a name, regardless of case); `folder` with `is`; `attachments` "
    "with `present` or `missing` (attachments Lekto takes). None: every mail."
)


class MailConditionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: MailField
    op: MailOperator
    value: str | None = Field(default=None, max_length=MAX_FOLDER)

    def domain(self) -> MailCondition:
        return MailCondition(self.field, self.op, self.value)

    @classmethod
    def of(cls, condition: MailCondition) -> "MailConditionBody":
        return cls(field=condition.field, op=condition.op, value=condition.value)


class _Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int | None = Field(
        default=None, ge=MIN_PRIORITY, le=MAX_PRIORITY, description="Higher first."
    )
    any: bool | None = Field(default=None, description="Any condition (or); else all (and).")
    conditions: list[MailConditionBody] | None = Field(
        default=None, max_length=MAX_CONDITIONS, description=CONDITIONS_HELP
    )
    parts: MailParts | None = Field(default=None, description=PARTS_HELP)
    user_id: UUID | None = Field(default=None, description="Whom it takes the mail for.")
    space_id: UUID | None = Field(
        default=None, description="A space the person files into; null: their personal one."
    )
    text_type_id: UUID | None = Field(
        default=None, description="The document type of the mail's text; null: Lekto decides."
    )
    after: MailAction | None = Field(default=None, description=AFTER_HELP)
    move_to: Annotated[str, Field(min_length=1, max_length=MAX_FOLDER)] | None = None
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
            any=UNSET if self.any is None else self.any,
            conditions=(
                UNSET
                if self.conditions is None
                else tuple(item.domain() for item in self.conditions)
            ),
            parts=UNSET if self.parts is None else self.parts,
            user_id=optional("user_id", self.user_id, UserId),
            space_id=optional("space_id", self.space_id, SpaceId),
            text_type_id=optional("text_type_id", self.text_type_id, DocumentTypeId),
            after=UNSET if self.after is None else self.after,
            move_to=self.move_to if "move_to" in given else UNSET,
            enabled=UNSET if self.enabled is None else self.enabled,
        )


class MailRuleCreate(_Rule):
    """A new mail rule of a mailbox; what is left out gets the default (priority 100, all
    conditions, takes the attachments and the text, leaves the mail, active)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "mailbox_id": "01a1a7fc-702c-736e-a661-ff59645bdc52",
                    "name": "Bills of the utilities",
                    "conditions": [
                        {"field": "sender", "op": "ends_with", "value": "@stadtwerke.example"}
                    ],
                    "user_id": "01a1a7fc-7013-741e-ae72-58401e634e5d",
                    "after": "read",
                }
            ]
        },
    )

    mailbox_id: UUID
    name: str = Field(min_length=1, max_length=MAX_NAME)


class MailRulePatch(_Rule):
    """What changes; what is left out stays. `space_id`, `text_type_id`, `user_id` and
    `move_to` given as null clear it. Switching it on clears why it was paused."""

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
    any: bool
    conditions: list[MailConditionBody]
    parts: MailParts
    user_id: UUID | None
    space_id: UUID | None
    text_type_id: UUID | None
    after: MailAction
    move_to: str | None
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
            any=rule.any,
            conditions=[MailConditionBody.of(item) for item in rule.conditions],
            parts=rule.parts,
            user_id=rule.user_id,
            space_id=rule.space_id,
            text_type_id=rule.text_type_id,
            after=rule.after,
            move_to=rule.move_to,
            enabled=rule.enabled,
            disabled_reason=(
                None if rule.disabled_reason is None else ReasonOut.of(rule.disabled_reason)
            ),
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
