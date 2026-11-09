"""The fields of a mail, alike in mail rules and document rules: the same operators, the same
values, the same limits, and one priority (review 0.12.2, C-02 and C-06)."""

from collections.abc import Callable

import pytest

from lekto.core.domain.condition_tree import Group
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, UserId, new_id
from lekto.core.domain.mail_rules import (
    MailCondition,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
)
from lekto.core.domain.mail_traits import MAIL_OPERATORS, MAX_MAIL_TEXT
from lekto.core.domain.rules import (
    MAX_PRIORITY,
    Condition,
    ConditionField,
    ForceReview,
    Operator,
    RuleDefinition,
)
from tests.builders import NOW

VALUES = {"importance": "high", "flag": "red", "keyword": "Tax"}


def _takes(build: Callable[[], object]) -> bool:
    try:
        build()
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize("name", sorted(MAIL_OPERATORS))
@pytest.mark.parametrize("op", [op.value for op in MailOperator])
def test_both_kinds_of_rule_take_the_same_conditions_on_a_mail(name: str, op: str) -> None:
    value = None if op in ("present", "missing") else VALUES.get(name, "Stadtwerke")
    mail = _takes(lambda: MailCondition(MailField(name), MailOperator(op), value))
    document = _takes(
        lambda: Condition(field=ConditionField(f"mail_{name}"), op=Operator(op), value=value)
    )
    assert mail == document == (op in MAIL_OPERATORS[name])


@pytest.mark.parametrize("name", ["sender", "recipient", "to", "cc", "subject"])
@pytest.mark.parametrize(("length", "taken"), [(MAX_MAIL_TEXT, True), (MAX_MAIL_TEXT + 1, False)])
def test_both_kinds_of_rule_hold_a_mail_text_to_one_limit(
    name: str, length: int, taken: bool
) -> None:
    value = "x" * length
    assert _takes(lambda: MailCondition(MailField(name), MailOperator.IS, value)) is taken
    field = ConditionField(f"mail_{name}")
    assert _takes(lambda: Condition(field=field, op=Operator.IS, value=value)) is taken


@pytest.mark.parametrize("priority", [True, 1.5, -1, MAX_PRIORITY + 1])
def test_both_kinds_of_rule_refuse_the_same_priorities(priority: object) -> None:
    always = Condition(field=ConditionField.CHANNEL, op=Operator.IN, value=["web"])
    with pytest.raises(ValidationError, match="priority must be a whole number"):
        RuleDefinition(
            name="R",
            conditions=Group(mode="all", items=(always,)),
            actions=(ForceReview("x"),),
            priority=priority,  # type: ignore[arg-type]
        )
    with pytest.raises(ValidationError, match="priority must be a whole number"):
        MailRule.create(
            mailbox_id=MailboxId(new_id()),
            changes=MailRuleChanges(name="R", user_id=UserId(new_id()), priority=priority),  # type: ignore[arg-type]
            now=NOW,
        )
