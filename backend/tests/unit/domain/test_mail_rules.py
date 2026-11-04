"""Mail rules: conditions on the mail, the first that matches, and what a rule must name."""

import pytest

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, SpaceId, UserId, new_id
from lekto.core.domain.mail import MailAction
from lekto.core.domain.mail_intake import MailParts
from lekto.core.domain.mail_message import read_mail
from lekto.core.domain.mail_rules import (
    MailCondition,
    MailFacts,
    MailField,
    MailOperator,
    MailRule,
    MailRuleChanges,
    first_match,
    mail_facts,
)
from lekto.core.domain.reasons import ReasonCode, because
from tests.builders import HOUR, NOW
from tests.mails import plain_mail, rich_mail

FACTS = MailFacts(
    senders=("rechnung@stadtwerke.example", "Stadtwerke Musterstadt"),
    recipients=("anna@example.test",),
    subject="Ihre Rechnung Oktober",
    folder="INBOX",
    attachments=True,
)
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
        (MailCondition(MailField.RECIPIENT, MailOperator.IS, "ben@example.test"), False),
        (MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "rechnung"), True),
        (MailCondition(MailField.FOLDER, MailOperator.IS, "INBOX"), True),
        (MailCondition(MailField.FOLDER, MailOperator.IS, "inbox"), False),
        (MailCondition(MailField.ATTACHMENTS, MailOperator.PRESENT), True),
        (MailCondition(MailField.ATTACHMENTS, MailOperator.MISSING), False),
    ],
)
def test_conditions(condition: MailCondition, holds: bool) -> None:
    assert condition.holds(FACTS) is holds


@pytest.mark.parametrize(
    ("field", "op", "value"),
    [
        (MailField.FOLDER, MailOperator.CONTAINS, "INBOX"),
        (MailField.ATTACHMENTS, MailOperator.PRESENT, "x"),
        (MailField.SUBJECT, MailOperator.CONTAINS, " "),
        (MailField.SUBJECT, MailOperator.PRESENT, None),
    ],
)
def test_a_bad_condition_is_refused(field: MailField, op: MailOperator, value: str | None) -> None:
    with pytest.raises(ValidationError):
        MailCondition(field, op, value)


def test_all_or_any_and_none() -> None:
    hit = MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Rechnung")
    miss = MailCondition(MailField.SUBJECT, MailOperator.CONTAINS, "Newsletter")
    assert not rule(conditions=(hit, miss)).matches(FACTS)
    assert rule(conditions=(hit, miss), any=True).matches(FACTS)
    assert rule().matches(FACTS)  # no condition: every mail


def test_the_first_by_priority_then_name_decides() -> None:
    late, early, paused = rule("B", priority=5), rule("a", priority=5), rule("0", priority=1)
    paused.pause(because(ReasonCode.MAIL_RULE_PERSON_GONE), now=NOW)
    assert first_match([late, paused, early], FACTS) is early
    assert first_match([], FACTS) is None


def test_what_a_rule_must_name() -> None:
    with pytest.raises(ValidationError):
        rule(user_id=None)  # it takes something: for whom?
    with pytest.raises(ValidationError):
        rule(after=MailAction.MOVE)  # no folder
    with pytest.raises(ValidationError):
        rule(priority=1001)
    nothing = rule(parts=MailParts.NOTHING, space_id=SpaceId(new_id()), after=MailAction.TRASH)
    assert (nothing.user_id, nothing.space_id) == (None, None)
    moved = rule(after=MailAction.MOVE, move_to=" Lekto/Erledigt ")
    assert moved.move_to == "Lekto/Erledigt"
    moved.change(MailRuleChanges(after=MailAction.READ), now=NOW)
    assert moved.move_to is None
    decision = moved.decision()
    assert (decision.user_id, decision.after, decision.rule) == (PERSON, MailAction.READ, "Strom")


def test_a_paused_rule_is_switched_on_again() -> None:
    paused = rule()
    paused.pause(because(ReasonCode.MAIL_RULE_TYPE_GONE), now=NOW + HOUR)
    assert (paused.enabled, paused.updated_at) == (False, NOW + HOUR)
    paused.change(MailRuleChanges(enabled=True), now=NOW + 2 * HOUR)
    assert (paused.enabled, paused.disabled_reason) == (True, None)


def test_the_facts_of_a_mail() -> None:
    facts = mail_facts(read_mail(rich_mail()), "Rechnungen")
    assert "rechnung@stadtwerke.example" in facts.senders
    assert "buchhaltung@example.test" in facts.recipients
    assert (facts.folder, facts.attachments) == ("Rechnungen", True)
    assert not mail_facts(read_mail(plain_mail()), "INBOX").attachments
