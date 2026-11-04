"""Setting up the mail rules of the mailboxes (umsetzungsplan "Eingangskanal Mail", decision 12).

Mail rules are global and only admins see and change them, as the mailboxes (Tobi, 04.11.2026).
A rule's person must be active, its space one the person files into, its type one that exists;
`MailIntakeService` pauses a rule whose one is gone by the time a mail needs it.
"""

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import MailboxId, MailRuleId, UserId
from lekto.core.domain.mail_rules import MailRule, MailRuleChanges
from lekto.core.domain.permissions import can_file_into
from lekto.core.domain.reasons import Action
from lekto.core.ports.clock import Clock
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory
from lekto.core.services._access import require_admin


class MailRuleService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def list_rules(self, actor: UserId) -> list[MailRule]:
        """Every mail rule, by mailbox, priority and name."""
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            return await uow.mail_rules.list_all()

    async def get(self, actor: UserId, id: MailRuleId) -> MailRule:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            return await uow.mail_rules.get(id)

    async def create(self, actor: UserId, mailbox: MailboxId, changes: MailRuleChanges) -> MailRule:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            await uow.mailboxes.get(mailbox)
            rule = MailRule.create(mailbox_id=mailbox, changes=changes, now=self._clock.now())
            await _check(uow, rule)
            await uow.mail_rules.add(rule)
            await uow.commit()
            return rule

    async def change(self, actor: UserId, id: MailRuleId, changes: MailRuleChanges) -> MailRule:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            rule = await uow.mail_rules.get(id)
            rule.change(changes, now=self._clock.now())
            await _check(uow, rule)
            await uow.mail_rules.update(rule)
            await uow.commit()
            return rule

    async def delete(self, actor: UserId, id: MailRuleId) -> None:
        async with self._uow() as uow:
            await require_admin(uow, actor, Action.MANAGE_MAILBOXES)
            await uow.mail_rules.remove(id)
            await uow.commit()


async def _check(uow: UnitOfWork, rule: MailRule) -> None:
    """The person, space and type the rule names exist and fit (ValidationError)."""
    if rule.user_id is None:
        return
    person = await uow.users.find(rule.user_id)
    if person is None or not person.active:
        raise ValidationError("user_id: no such active user")
    if rule.space_id is not None:
        space = await uow.spaces.find(rule.space_id)
        if space is None or not can_file_into(person, space):
            raise ValidationError("space_id: a space the person files into")
    if rule.text_type_id is not None and await uow.document_types.find(rule.text_type_id) is None:
        raise ValidationError("text_type_id: no such document type")
