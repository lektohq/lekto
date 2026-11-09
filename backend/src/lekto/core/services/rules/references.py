"""Rules whose references go away.

Deleting a contact, type, field or space is not blocked by rules that refer to it: the
person deleting it would have to change rules they may not see or should not have to look after
(the editors of a space do not see the rules of other spaces that file into it). Instead the
affected rules are disabled, with the reason, in the same unit of work. Enabling such a rule
checks its references again.

Mail rules go the same way (review 0.12.2, C-06): deleting a document type, a space or a
person, or deactivating a person, pauses the mail rules that name them, with the reason, in the
same unit of work (`pause_mail_rules`), so that the list shows them paused at once. Intake still
pauses a rule that cannot take a mail when one comes (a person who lost the right to a space).

Tags are the exception (0.3): a tag in use, by a rule too, is not deleted. Only admins delete
tags, and they see every rule.
"""

from collections.abc import Callable, Mapping
from datetime import datetime

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.fields import FieldDefinition
from lekto.core.domain.ids import DocumentTypeId, FieldId, SpaceId, UserId
from lekto.core.domain.mail_rules import MailRule
from lekto.core.domain.reasons import Reason, ReasonCode, because
from lekto.core.domain.rules import References, Rule, check_fields
from lekto.core.ports.unit_of_work import UnitOfWork


async def disable_rules(
    uow: UnitOfWork, now: datetime, reason: Reason, affected: Callable[[Rule], bool]
) -> int:
    """Disable every enabled rule (global or of any space) for which `affected` holds; returns
    how many."""
    count = 0
    for rule in await uow.rules.list_for(spaces=None, include_global=True):
        if rule.enabled and affected(rule):
            rule.disable(now, reason)
            await uow.rules.update(rule)
            count += 1
    return count


async def pause_mail_rules(
    uow: UnitOfWork, now: datetime, reason: Reason, affected: Callable[[MailRule], bool]
) -> int:
    """Pause every enabled mail rule for which `affected` holds; returns how many."""
    count = 0
    for rule in await uow.mail_rules.list_all():
        if rule.enabled and affected(rule):
            rule.pause(reason, now=now)
            await uow.mail_rules.update(rule)
            count += 1
    return count


async def pause_mail_rules_of_person(uow: UnitOfWork, now: datetime, person: UserId) -> int:
    """The mail rules that take mails for a person who is deleted or deactivated."""
    return await pause_mail_rules(
        uow, now, because(ReasonCode.MAIL_RULE_PERSON_GONE), lambda rule: rule.user_id == person
    )


async def pause_mail_rules_into(uow: UnitOfWork, now: datetime, space: SpaceId) -> int:
    """The mail rules that file into a space that is deleted."""
    return await pause_mail_rules(
        uow,
        now,
        because(ReasonCode.MAIL_RULE_SPACE_UNREACHABLE),
        lambda rule: rule.space_id == space,
    )


async def pause_mail_rules_typing(uow: UnitOfWork, now: datetime, type_id: DocumentTypeId) -> int:
    """The mail rules that give a mail's text a document type that is deleted."""
    return await pause_mail_rules(
        uow,
        now,
        because(ReasonCode.MAIL_RULE_TYPE_GONE),
        lambda rule: rule.text_type_id == type_id,
    )


def refers_to(
    select: Callable[[References], frozenset[object]], id: object
) -> Callable[[Rule], bool]:
    """`affected` for `disable_rules`: the rule refers to `id` among the selected references."""

    def affected(rule: Rule) -> bool:
        return id in select(rule.definition.references())

    return affected


def misfits(
    changed: FieldId, definitions: Mapping[FieldId, FieldDefinition]
) -> Callable[[Rule], bool]:
    """`affected` for `disable_rules`: the rule refers to the `changed` field and its
    field conditions or values no longer fit `definitions` (all field definitions), e.g.
    because a choice it uses was removed."""

    def affected(rule: Rule) -> bool:
        if changed not in rule.definition.references().fields:
            return False
        try:
            check_fields(rule.definition, definitions)
        except ValidationError:
            return True
        return False

    return affected
