"""What an admin may beyond a user splits into admin rights, which an admin acting through an API
token has only as the token carries them (`.knowledge/plans/token-rights.md`): counting every
user's documents, reaching every space, the mailboxes, managing. Without one the admin acts as a
user with the same spaces; a user gains nothing from carrying one."""

import pytest

from lekto.core.domain.document_facts import FactCriterion, FactRole
from lekto.core.domain.documents import Channel
from lekto.core.domain.errors import NotFoundError, PermissionDeniedError
from lekto.core.domain.mail import Mailbox
from lekto.core.domain.pipeline import Node
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.rights import Actor, TokenRight
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import Role, User
from lekto.core.ports.repository import CountBy, DocumentFilter
from lekto.core.services.profiles import ProfileService
from tests.builders import UNCERTAIN, Returns, incoming
from tests.mails import LOGIN
from tests.unit.services.support import World

COUNT_ALL = TokenRight.ADMIN_COUNT_ALL
DOCUMENTS_ALL = TokenRight.ADMIN_DOCUMENTS_ALL
MAILBOXES = TokenRight.ADMIN_MAILBOXES
MANAGE = TokenRight.ADMIN_MANAGE


def acting(user: User, *rights: TokenRight) -> Actor:
    """`user` acting through a token with `rights` (the areas do not matter to the core)."""
    return Actor(user.id, frozenset(rights))


def _lacks(error: pytest.ExceptionInfo[PermissionDeniedError], right: TokenRight) -> bool:
    reason = error.value.reason
    return (
        reason is not None
        and reason.code is ReasonCode.TOKEN_LACKS_RIGHT
        and reason.params.get("right") == right.value
    )


async def _yellow(world: World, owner: User) -> None:
    """A document of `owner` waiting in their inbox."""
    await world.pipeline().receive(Actor(owner.id), incoming(b"%PDF-1.7 a"), filename="a.pdf")
    await world.drain(world.pipeline({Node.JUDGE: Returns(UNCERTAIN)}))


async def test_counting_every_user_s_documents_opens_the_numbers_alone(world: World) -> None:
    admin, owner = await world.user(role=Role.ADMIN), await world.user()
    await _yellow(world, owner)
    (document,) = await world.visible(owner.id)
    counter = acting(admin, COUNT_ALL)

    assert await world.documents.count(counter, DocumentFilter(), all_users=True) == 1
    assert (await world.inbox.summary(counter, all_users=True)).counts
    assert await world.documents.document_counts(counter, CountBy.CONTACT, all_users=True) == {}
    assert (await world.documents.facets(counter, DocumentFilter(), all_users=True)).total == 1
    # Its own reach holds nothing; what shows documents stays closed.
    assert await world.documents.count(counter, DocumentFilter()) == 0
    with pytest.raises(PermissionDeniedError) as error:
        await world.documents.query(counter, DocumentFilter(), all_users=True)
    assert _lacks(error, DOCUMENTS_ALL)
    with pytest.raises(PermissionDeniedError) as error:
        await world.inbox.items(counter, all_users=True)
    assert _lacks(error, DOCUMENTS_ALL)
    with pytest.raises(NotFoundError):
        await world.documents.get(counter, document.id)

    for counts in (
        world.documents.count(acting(admin), DocumentFilter(), all_users=True),
        world.inbox.summary(acting(admin, DOCUMENTS_ALL), all_users=True),
        world.documents.document_counts(acting(admin), CountBy.CONTACT, all_users=True),
        world.documents.facets(acting(admin), DocumentFilter(), all_users=True),
    ):
        with pytest.raises(PermissionDeniedError) as error:
            await counts
        assert _lacks(error, COUNT_ALL)


async def test_reaching_every_space_opens_other_users_documents_and_spaces(world: World) -> None:
    admin, owner, friend = await world.user(role=Role.ADMIN), await world.user(), await world.user()
    await _yellow(world, owner)
    (document,) = await world.visible(owner.id)
    office = await world.spaces.create(Actor(owner.id), "Office")
    reach = acting(admin, DOCUMENTS_ALL)

    assert (await world.documents.get(reach, document.id)).id == document.id
    assert await world.documents.processing_log(reach, document.id)
    listed = await world.documents.query(reach, DocumentFilter(), all_users=True)
    assert [view.document.id for view in listed] == [document.id]
    assert [item.document.id for item in await world.inbox.items(reach, all_users=True)] == [
        document.id
    ]
    assert office.id in {
        space.id for space in await world.spaces.list_spaces(reach, all_users=True)
    }
    await world.spaces.set_member(reach, office.id, friend.id, SpaceRole.READ)
    shared = await world.spaces.create(reach, "Shared", members={friend.id: SpaceRole.EDIT})
    assert admin.id not in shared.members  # an admin may give the members alone

    plain = acting(admin)  # a user with the same spaces: none of the owner's
    with pytest.raises(NotFoundError):
        await world.documents.get(plain, document.id)
    with pytest.raises(PermissionDeniedError) as error:
        await world.spaces.list_spaces(plain, all_users=True)
    assert _lacks(error, DOCUMENTS_ALL)
    with pytest.raises((PermissionDeniedError, NotFoundError)):
        await world.spaces.change(plain, office.id, name="Mine")
    alone = await world.spaces.create(plain, "Own", members={friend.id: SpaceRole.EDIT})
    assert alone.members[admin.id] is SpaceRole.EDIT  # a user is always an editor of theirs


async def test_managing_opens_master_data_users_profiles_and_the_migration(world: World) -> None:
    admin, owner = await world.user(role=Role.ADMIN), await world.user()
    manager, plain = acting(admin, MANAGE), acting(admin)

    contact = await world.master_data.create_contact(manager, "Muster Bäckerei")
    with pytest.raises(PermissionDeniedError) as error:
        await world.master_data.create_contact(plain, "Muster Versicherung")
    assert _lacks(error, MANAGE)
    with pytest.raises(PermissionDeniedError):
        await world.master_data.change_contact(plain, contact.id, name="Muster Bank")

    seen = {item.id: item for item in await world.users.list_users(manager)}
    assert seen[owner.id].role is Role.USER
    seen = {item.id: item for item in await world.users.list_users(plain)}
    assert seen[owner.id].role is None  # as a user sees them
    assert (await world.users.get(plain, owner.id)).role is None

    profiles = ProfileService(world.uow, world.clock)
    await profiles.get(manager, owner.id, session=False)
    with pytest.raises(PermissionDeniedError):
        await profiles.get(plain, owner.id, session=False)

    pipeline = world.pipeline()
    await pipeline.receive(
        manager, incoming(b"%PDF-1.7 m"), filename="m.pdf", channel=Channel.MIGRATION
    )
    with pytest.raises(PermissionDeniedError):
        await pipeline.receive(
            plain, incoming(b"%PDF-1.7 n"), filename="n.pdf", channel=Channel.MIGRATION
        )
    with pytest.raises(PermissionDeniedError):
        await pipeline.receive(
            plain, incoming(b"%PDF-1.7 o"), filename="o.pdf", uploaded_by=owner.id
        )

    persons = DocumentFilter(facts=(FactCriterion(role=FactRole.PERSON),))
    assert await world.documents.count(manager, persons) == 0
    with pytest.raises(PermissionDeniedError):
        await world.documents.count(plain, persons)


async def test_the_mailboxes_right_lists_and_fetches_but_does_not_manage(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    mailbox = await _mailbox(world, admin)
    mailboxes, plain = acting(admin, MAILBOXES), acting(admin, MANAGE)

    assert [item.id for item in await world.mailboxes.list_mailboxes(mailboxes)] == [mailbox.id]
    assert (await world.mailboxes.get(mailboxes, mailbox.id)).id == mailbox.id
    await world.mail_intake().fetch_now(mailboxes, mailbox.id)
    with pytest.raises(PermissionDeniedError) as error:
        await world.mailboxes.delete(mailboxes, mailbox.id)
    assert _lacks(error, MANAGE)

    # Managing is not listing: each is a right of its own.
    with pytest.raises(PermissionDeniedError) as error:
        await world.mailboxes.list_mailboxes(plain)
    assert _lacks(error, MAILBOXES)
    with pytest.raises(PermissionDeniedError):
        await world.mail_intake().fetch_now(plain, mailbox.id)


async def test_managing_shows_every_user_s_webhooks(world: World) -> None:
    admin, owner = await world.user(role=Role.ADMIN), await world.user()
    created = await world.webhooks.create(
        Actor(owner.id), name="Theirs", url="https://hooks.example/a", event_types=["*"]
    )
    theirs = created.webhook
    assert theirs.id in {
        item.id for item in await world.webhooks.list_webhooks(acting(admin, MANAGE))
    }
    assert await world.webhooks.list_webhooks(acting(admin)) == []
    with pytest.raises(NotFoundError):
        await world.webhooks.get(acting(admin), theirs.id)


async def test_a_user_gains_nothing_from_admin_rights(world: World) -> None:
    user = await world.user()
    every = Actor(user.id, frozenset(TokenRight))
    with pytest.raises(PermissionDeniedError) as error:
        await world.documents.count(every, DocumentFilter(), all_users=True)
    reason = error.value.reason
    assert reason is not None and reason.code is ReasonCode.ADMINS_ONLY
    with pytest.raises(PermissionDeniedError):
        await world.master_data.create_contact(every, "Muster Bäckerei")


async def _mailbox(world: World, admin: User) -> Mailbox:
    return await world.mailboxes.create(
        Actor(admin.id),
        name="Household",
        host=LOGIN.host,
        port=LOGIN.port,
        security=LOGIN.security,
        username=LOGIN.username,
        password=LOGIN.password,
    )
