"""Mail rules: conditions on the mail, the first that matches, and what a rule must name."""

from dataclasses import replace

import pytest

from lekto.core.domain.condition_tree import MAX_DEPTH, Group
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, SpaceId, UserId, new_id
from lekto.core.domain.json_value import JsonValue
from lekto.core.domain.mail import MailAction, MailStep, step_flags
from lekto.core.domain.mail_intake import MailParts
from lekto.core.domain.mail_message import read_mail
from lekto.core.domain.mail_rules import (
    MailCondition,
    MailFacts,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
    conditions_from_json,
    conditions_to_json,
    first_match,
    mail_facts,
    steps_from_json,
    steps_to_json,
)
from lekto.core.domain.mail_traits import FlagColor, Importance, MailMarks
from lekto.core.domain.reasons import ReasonCode, because
from tests.builders import HOUR, NOW
from tests.mails import plain_mail, rich_mail

FACTS = MailFacts(
    senders=("rechnung@stadtwerke.example", "Stadtwerke Musterstadt"),
    recipients=("anna@example.test", "ben@example.test"),
    to=("anna@example.test",),
    cc=("ben@example.test",),
    subject="Ihre Rechnung Oktober",
    folder="INBOX",
    attachments=True,
    importance=Importance.LOW,
    marks=MailMarks(keywords=("Lekto", "$label1"), flag=FlagColor.ORANGE),
)
UNKNOWN = replace(FACTS, importance=None, marks=None)
PERSON = UserId(new_id())


def rule(name: str = "Strom", **changes: object) -> MailRule:
    values: dict[str, object] = {"name": name, "user_id": PERSON}
    values.update(changes)
    return MailRule.create(
        mailbox_id=MailboxId(new_id()),
        changes=MailRuleChanges(**values),  # type: ignore[arg-type]
        now=NOW,
    )


@pytest.mark.parametrize(
    ("condition", "holds"),
    [
        (MailCondition(MailField.SENDER, MailOperator.ENDS_WITH, "@STADTWERKE.example"), True),
        (MailCondition(MailField.SENDER, MailOperator.CONTAINS, "musterstadt"), True),
        (MailCondition(MailField.SENDER, MailOperator.IS, "rechnung@stadtwerke.example"), True),
        (MailCondition(MailField.SENDER, MailOperator.STARTS_WITH, "info@"), False),
        (MailCondition(MailField.RECIPIENT, MailOperator.IS, "carl@example.test"), False),
        (MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "rechnung"), True),
        (MailCondition(MailField.FOLDER, MailOperator.IS, "INBOX"), True),
        (MailCondition(MailField.FOLDER, MailOperator.IS, "inbox"), False),
        (MailCondition(MailField.ATTACHMENTS, MailOperator.PRESENT), True),
        (MailCondition(MailField.ATTACHMENTS, MailOperator.MISSING), False),
        (MailCondition(MailField.RECIPIENT, MailOperator.IS, "ben@example.test"), True),
        (MailCondition(MailField.TO, MailOperator.IS, "ben@example.test"), False),
        (MailCondition(MailField.CC, MailOperator.ENDS_WITH, "@example.test"), True),
        (MailCondition(MailField.IMPORTANCE, MailOperator.IS, "low"), True),
        (MailCondition(MailField.IMPORTANCE, MailOperator.IS, "high"), False),
        (MailCondition(MailField.KEYWORD, MailOperator.CONTAINS, "LEKTO"), True),
        (MailCondition(MailField.KEYWORD, MailOperator.CONTAINS, "Erledigt"), False),
        (MailCondition(MailField.KEYWORD, MailOperator.PRESENT), True),
        (MailCondition(MailField.FLAG, MailOperator.PRESENT), True),
        (MailCondition(MailField.FLAG, MailOperator.IS, "orange"), True),
        (MailCondition(MailField.FLAG, MailOperator.IS, "red"), False),
        (MailCondition(MailField.FLAG, MailOperator.MISSING), False),
    ],
)
def test_conditions(condition: MailCondition, holds: bool) -> None:
    assert condition.holds(FACTS) is holds
    if condition.field in (MailField.IMPORTANCE, MailField.KEYWORD, MailField.FLAG):
        assert not condition.holds(UNKNOWN)  # a mail fetched before Lekto read them


@pytest.mark.parametrize(
    ("field", "op", "value"),
    [
        (MailField.FOLDER, MailOperator.CONTAINS, "INBOX"),
        (MailField.ATTACHMENTS, MailOperator.PRESENT, "x"),
        (MailField.SUBJECT, MailOperator.CONTAINS, " "),
        (MailField.SUBJECT, MailOperator.PRESENT, None),
        (MailField.IMPORTANCE, MailOperator.IS, "urgent"),
        (MailField.FLAG, MailOperator.IS, "pink"),
        (MailField.KEYWORD, MailOperator.CONTAINS, "zwei Wörter"),
    ],
)
def test_a_bad_condition_is_refused(field: MailField, op: MailOperator, value: str | None) -> None:
    with pytest.raises(ValidationError):
        MailCondition(field, op, value)


HIT = MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Rechnung")
MISS = MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Newsletter")


def test_the_tree_of_every_rule() -> None:
    assert not rule(conditions=Group(mode="all", items=(HIT, MISS))).matches(FACTS)
    assert rule(conditions=Group(mode="any", items=(HIT, MISS))).matches(FACTS)
    assert rule(conditions=Group(mode="all", items=(MISS,), negate=True)).matches(FACTS)
    inner = Group(mode="any", items=(MISS, Group(mode="all", items=(HIT,), negate=True)))
    assert not rule(conditions=Group(mode="all", items=(HIT, inner))).matches(FACTS)
    assert rule().matches(FACTS)  # no condition: every mail


def test_the_tree_has_the_limits_of_every_rule() -> None:
    deep: Group[MailCondition] = Group(mode="all", items=(HIT,))
    for _ in range(MAX_DEPTH):
        deep = Group(mode="all", items=(deep,))
    with pytest.raises(ValidationError, match="deep"):
        rule(conditions=deep)


def test_the_tree_in_json() -> None:
    tree = Group(mode="any", items=(HIT, Group(mode="all", items=(MISS,), negate=True)))
    data = conditions_to_json(tree)
    assert data == {
        "any": [
            {"field": "subject", "op": "contains", "value": "Rechnung"},
            {"all": [{"field": "subject", "op": "contains", "value": "Newsletter"}], "not": True},
        ]
    }
    assert conditions_from_json(data) == tree
    assert conditions_to_json(None) is None and conditions_from_json(None) is None
    with pytest.raises(ValidationError, match="unknown key"):
        conditions_from_json({"all": [{"field": "subject", "op": "is", "value": "x", "y": 1}]})
    with pytest.raises(ValidationError):
        conditions_from_json({"all": [{"field": "nope", "op": "is", "value": "x"}]})


def test_the_first_by_priority_then_name_decides() -> None:
    late, early, paused = rule("B", priority=5), rule("a", priority=5), rule("0", priority=9)
    paused.pause(because(ReasonCode.MAIL_RULE_PERSON_GONE), now=NOW)
    assert first_match([late, paused, early], FACTS) is early
    assert first_match([], FACTS) is None
    # An umlaut sorts as its letter, as every list shows names (DIN 5007, A-10).
    bank, doctors = rule("Bank", priority=5), rule("Ärzte", priority=5)
    assert first_match([bank, doctors], FACTS) is doctors


def test_what_a_rule_must_name() -> None:
    with pytest.raises(ValidationError):
        rule(user_id=None)  # it takes something: for whom?
    with pytest.raises(ValidationError):
        MailStep(MailAction.MOVE)  # no folder
    with pytest.raises(ValidationError):
        rule(priority=1001)
    trash = (MailStep(MailAction.TRASH),)
    nothing = rule(parts=MailParts.NOTHING, space_id=SpaceId(new_id()), after=trash)
    assert (nothing.user_id, nothing.space_id) == (None, None)
    moved = rule(after=(MailStep(MailAction.MOVE, " Lekto/Erledigt "),))
    assert moved.after[0].value == "Lekto/Erledigt"
    read = (MailStep(MailAction.READ), MailStep(MailAction.ADD_KEYWORD, "Lekto"))
    moved.change(MailRuleChanges(after=read), now=NOW)
    decision = moved.decision()
    assert (decision.user_id, decision.after, decision.rule) == (PERSON, read, "Strom")


@pytest.mark.parametrize(
    "steps",
    [
        (MailStep(MailAction.TRASH), MailStep(MailAction.READ)),  # trashing comes last
        (MailStep(MailAction.MOVE, "A"), MailStep(MailAction.TRASH)),  # one that ends it
        (MailStep(MailAction.READ), MailStep(MailAction.READ)),  # twice
        tuple(MailStep(MailAction.ADD_KEYWORD, f"k{index}") for index in range(11)),
    ],
)
def test_steps_in_their_order(steps: tuple[MailStep, ...]) -> None:
    with pytest.raises(ValidationError):
        rule(after=steps)


@pytest.mark.parametrize(
    ("action", "value"),
    [
        (MailAction.FLAG, "pink"),
        (MailAction.FLAG, None),
        (MailAction.ADD_KEYWORD, "zwei Wörter"),
        (MailAction.READ, "x"),
    ],
)
def test_a_bad_step_is_refused(action: MailAction, value: str | None) -> None:
    with pytest.raises(ValidationError):
        MailStep(action, value)


def test_the_flags_of_a_step() -> None:
    assert step_flags(MailStep(MailAction.FLAG, "purple")) == (
        ("\\Flagged", "$MailFlagBit0", "$MailFlagBit2"),
        ("$MailFlagBit1",),
    )
    assert step_flags(MailStep(MailAction.UNFLAG)) == (
        (),
        ("\\Flagged", "$MailFlagBit0", "$MailFlagBit1", "$MailFlagBit2"),
    )
    assert step_flags(MailStep(MailAction.UNREAD)) == ((), ("\\Seen",))
    assert step_flags(MailStep(MailAction.REMOVE_KEYWORD, "Lekto")) == ((), ("Lekto",))
    assert step_flags(MailStep(MailAction.MOVE, "A")) == ((), ())


def test_a_paused_rule_is_switched_on_again() -> None:
    paused = rule()
    paused.pause(because(ReasonCode.MAIL_RULE_TYPE_GONE), now=NOW + HOUR)
    assert (paused.enabled, paused.updated_at) == (False, NOW + HOUR)
    paused.change(MailRuleChanges(enabled=True), now=NOW + 2 * HOUR)
    assert (paused.enabled, paused.disabled_reason) == (True, None)


def test_the_steps_in_json() -> None:
    steps = (MailStep(MailAction.FLAG, "red"), MailStep(MailAction.MOVE, "Done"))
    data = steps_to_json(steps)
    assert data == [{"action": "flag", "value": "red"}, {"action": "move", "value": "Done"}]
    assert steps_from_json(data) == steps
    assert steps_from_json([]) == ()
    cases: list[tuple[JsonValue, str]] = [
        ({"action": "read"}, "after: expected a list"),
        ([{"action": "nope"}], "after\\[0\\]: "),
        ([{"action": "flag", "value": "pink"}], "after\\[0\\]: flag"),
        ([{"action": "read", "value": 1}], "after\\[0\\].value"),
        ([{"action": "read", "x": 1}], "after\\[0\\]: unknown key"),
        ([{"action": "trash"}, {"action": "read"}], "after: moving or trashing comes last"),
    ]
    for bad, place in cases:
        with pytest.raises(ValidationError, match=place):
            steps_from_json(bad)


def test_a_rule_read_without_its_conditions_and_steps() -> None:
    unreadable = rule(conditions=Group(mode="all", items=(HIT,)))
    unreadable.pause(because(ReasonCode.MAIL_RULE_UNREADABLE, detail="x"), now=NOW)
    unreadable.conditions, unreadable.after = None, ()
    assert unreadable.unreadable
    with pytest.raises(ValidationError, match="anew"):
        unreadable.change(MailRuleChanges(name="Gas"), now=NOW + HOUR)
    with pytest.raises(ValidationError, match="anew"):
        unreadable.change(MailRuleChanges(enabled=True, conditions=None), now=NOW + HOUR)
    assert (unreadable.name, unreadable.updated_at) == ("Strom", NOW)
    unreadable.change(
        MailRuleChanges(conditions=None, after=(MailStep(MailAction.READ),)), now=NOW + HOUR
    )
    assert (unreadable.enabled, unreadable.disabled_reason) == (False, None)
    assert not unreadable.unreadable
    unreadable.change(MailRuleChanges(enabled=True), now=NOW + 2 * HOUR)
    assert unreadable.enabled


def test_the_facts_of_a_mail() -> None:
    facts = mail_facts(read_mail(rich_mail()), "Rechnungen")
    assert "rechnung@stadtwerke.example" in facts.senders
    assert "buchhaltung@example.test" in facts.recipients
    assert (facts.folder, facts.attachments) == ("Rechnungen", True)
    assert not mail_facts(read_mail(plain_mail()), "INBOX").attachments
