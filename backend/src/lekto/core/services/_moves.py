"""A person moving a document into another space: what every such move does, whoever starts
it (`DocumentService.move`, deleting a user who leaves documents behind)."""

from datetime import datetime

from lekto.core.domain.documents import Document
from lekto.core.domain.errors import NotFoundError, SpaceWriteDeniedError
from lekto.core.domain.identity import ViaToken
from lekto.core.domain.ids import SpaceId
from lekto.core.domain.permissions import can_file_into, can_hand_over, space_role
from lekto.core.domain.spaces import Space
from lekto.core.domain.users import User
from lekto.core.ports.unit_of_work import UnitOfWork
from lekto.core.services._access import field_definitions
from lekto.core.services.inbox import arrived
from lekto.core.services.rules.changes import ChangeRules
from lekto.core.services.rules.running import Prepared


async def move_by_person(
    uow: UnitOfWork,
    document: Document,
    source: Space,
    target: Space,
    *,
    by: User,
    now: datetime,
    rules: ChangeRules | None,
    prepared: Prepared | None = None,
    via: ViaToken | None = None,
) -> None:
    """`by` moves `document` out of `source` into `target` (the caller checked they may): the
    space is a person's decision, a green document becomes new for the editors of `target`
    who could not read it before (`inbox.arrived`), the log says a person chose the space, so
    rules leave it there, and a completed document runs the rules of `target` as change rules
    (`ChangeRules.after_arrival`, with the patterns `prepared` outside the transaction from
    `ChangeRules.arrival_rules`). `via`: the API token `by` acts through. Saves the document
    and its events."""
    document.move_to(
        target.id, now, by_person=True, handed_over=target.personal_of not in (None, by.id)
    )
    await arrived(uow, document, source, now, by.id)
    if rules is not None:
        await uow.processing_log.append(rules.space_chosen(document, actor=by, now=now, via=via))
        await rules.after_arrival(
            uow,
            document=document,
            source=source,
            prepared=prepared or Prepared(),
            definitions=await field_definitions(uow),
            now=now,
            by_person=True,
            applier=by,
            via=via,
        )
    await uow.documents.update(document)
    await uow.outbox.add(document.pull_events())


async def move_target(uow: UnitOfWork, user: User, id: SpaceId) -> Space:
    """The space `user` moves a document they edit into, by hand or on confirming it: one they
    edit, or another active user's personal space (handed over). NotFoundError for a space they
    neither see nor hand over to, SpaceWriteDeniedError for one they only read (review 0.12.2,
    C-03)."""
    target = await uow.spaces.find(id)
    if target is None or not (space_role(user, target) or can_hand_over(user, target)):
        raise NotFoundError("space", id)
    if not (can_file_into(user, target) or can_hand_over(user, target)):
        raise SpaceWriteDeniedError(target.id, target.name)
    await check_receiver(uow, target, by=user)
    return target


async def check_receiver(uow: UnitOfWork, target: Space, *, by: User | None = None) -> None:
    """NotFoundError if `target` is the personal space of a user who is gone or deactivated: no
    document is handed over to them (unless `by` is a member of the space)."""
    if target.personal_of is None or (by is not None and target.role_of(by.id) is not None):
        return
    receiver = await uow.users.find(target.personal_of)
    if receiver is None or not receiver.active:
        raise NotFoundError("space", target.id)
