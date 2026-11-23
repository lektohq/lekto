"""Admins have every right and see everything (Tobi, 08.10.2026); other users gain nothing from
it, and a deactivated admin has no rights. Lists show the caller's reach unless an admin asks
for all users."""

import pytest

from lekto.core.domain.documents import DocumentChanges
from lekto.core.domain.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
)
from lekto.core.domain.pipeline import Lane, Node
from lekto.core.domain.rights import Actor
from lekto.core.domain.rules import RuleScope, SetSpace
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import Role, User
from lekto.core.ports.repository import DocumentFilter
from tests.builders import UNCERTAIN, Returns, incoming
from tests.unit.services.rules_support import add_tags, channel_api, definition, rule_world
from tests.unit.services.support import World


async def _second_admin(world: World) -> tuple[User, User]:
    """An admin, and another one who can deactivate the first."""
    return await world.user("admin", role=Role.ADMIN), await world.user("boss", role=Role.ADMIN)


async def test_admins_list_spaces_of_everyone_and_manage_them(world: World) -> None:
    admin, boss = await _second_admin(world)
    owner, friend, stranger = await world.user(), await world.user(), await world.user()
    office = await world.spaces.create(Actor(owner.id), "Office")
    await world.spaces.set_member(Actor(owner.id), office.id, friend.id, SpaceRole.READ)

    # The list follows the reach the admin chose; the rights reach every space either way.
    assert office.id not in {space.id for space in await world.spaces.list_spaces(Actor(admin.id))}
    everyone = await world.spaces.list_spaces(Actor(admin.id), all_users=True)
    assert office.id in {space.id for space in everyone}
    assert office.id not in {
        space.id for space in await world.spaces.list_spaces(Actor(stranger.id))
    }
    with pytest.raises(PermissionDeniedError):
        await world.spaces.list_spaces(Actor(stranger.id), all_users=True)
    assert (await world.spaces.get(Actor(admin.id), office.id)).id == office.id

    renamed = await world.spaces.change(Actor(admin.id), office.id, name="Büro")
    assert renamed.name == "Büro"
    assert renamed.members == {owner.id: SpaceRole.EDIT, friend.id: SpaceRole.READ}
    shared = await world.spaces.set_member(Actor(admin.id), office.id, stranger.id, SpaceRole.EDIT)
    assert shared.members[stranger.id] is SpaceRole.EDIT
    await world.spaces.remove_member(Actor(admin.id), office.id, stranger.id)
    # Admins choose the members of a personal space too, but never delete it.
    personal = await world.personal_space(owner)
    await world.spaces.set_member(Actor(admin.id), personal.id, friend.id, SpaceRole.READ)
    with pytest.raises(ConflictError):
        await world.spaces.delete(Actor(admin.id), personal.id)

    # Nobody else gains anything: a reader is refused, a stranger does not learn of the space.
    with pytest.raises(PermissionDeniedError):
        await world.spaces.change(Actor(friend.id), office.id, name="Mine")
    with pytest.raises(NotFoundError):
        await world.spaces.change(Actor(stranger.id), office.id, name="Mine")

    await world.spaces.delete(Actor(admin.id), office.id)
    with pytest.raises(NotFoundError):
        await world.spaces.get(Actor(owner.id), office.id)

    # A deactivated admin has no rights.
    other = await world.spaces.create(Actor(owner.id), "Other")
    await world.users.update(Actor(boss.id), admin.id, active=False)
    with pytest.raises(AuthenticationError):
        await world.spaces.change(Actor(admin.id), other.id, name="Gone")
    with pytest.raises(AuthenticationError):
        await world.spaces.list_spaces(Actor(admin.id))


async def test_admins_control_other_users_documents_in_every_lane(world: World) -> None:
    admin, boss = await _second_admin(world)
    owner, stranger = await world.user(), await world.user()
    pipeline = world.pipeline()
    received = await pipeline.receive(Actor(owner.id), incoming(b"%PDF-1.7 a"), filename="a.pdf")
    # In processing: readable and controllable by the admin (besides its space's editors).
    assert (await world.documents.get(Actor(admin.id), received.id)).lane is None
    with pytest.raises(NotFoundError):
        await world.documents.get(Actor(stranger.id), received.id)
    await world.drain(world.pipeline({Node.JUDGE: Returns(UNCERTAIN)}))
    yellow = await world.documents.get(Actor(admin.id), received.id)
    assert yellow.lane is Lane.YELLOW

    assert await world.documents.processing_log(Actor(admin.id), yellow.id)
    assert (await world.documents.review(Actor(admin.id), yellow.id)).document.id == yellow.id
    changed = (
        await world.documents.change_metadata(
            Actor(admin.id), yellow.id, DocumentChanges(title="By the admin")
        )
    ).document
    assert changed.title == "By the admin"

    # Its space's editor has it in the inbox; the admin not, unless they ask for all users.
    assert [item.document.id for item in await world.inbox.items(Actor(owner.id))] == [yellow.id]
    assert await world.inbox.items(Actor(admin.id)) == []
    every = await world.inbox.items(Actor(admin.id), all_users=True)
    assert [item.document.id for item in every] == [yellow.id]
    listed = await world.documents.query(Actor(admin.id), _all(), all_users=True)
    assert [view.document.id for view in listed] == [yellow.id]
    assert await world.documents.query(Actor(admin.id), _all()) == []
    for user in (owner, stranger):
        with pytest.raises(PermissionDeniedError):
            await world.inbox.items(Actor(user.id), all_users=True)
        with pytest.raises(PermissionDeniedError):
            await world.documents.query(Actor(user.id), _all(), all_users=True)
    with pytest.raises(NotFoundError):
        await world.documents.processing_log(Actor(stranger.id), yellow.id)

    owners_space = await world.spaces.create(Actor(owner.id), "Archive")
    confirmed = await pipeline.confirm(
        Actor(admin.id),
        yellow.id,
        DocumentChanges(),
        accept_suggestions=True,
        space=owners_space.id,
    )
    assert confirmed is not None
    assert confirmed.document.space_id == owners_space.id
    assert confirmed.access is SpaceRole.EDIT
    await world.drain()
    assert (await world.documents.get(Actor(owner.id), yellow.id)).lane is Lane.GREEN

    await world.pipeline().reprocess_from(Actor(admin.id), yellow.id, Node.PARSE)
    await world.drain()
    await world.users.update(Actor(boss.id), admin.id, active=False)
    with pytest.raises(AuthenticationError):
        await world.documents.get(Actor(admin.id), yellow.id)
    with pytest.raises(AuthenticationError):
        await world.documents.delete(Actor(admin.id), yellow.id)
    await world.users.update(Actor(boss.id), admin.id, active=True)
    await world.documents.delete(Actor(admin.id), yellow.id)
    with pytest.raises(NotFoundError):
        await world.documents.get(Actor(owner.id), yellow.id)


def _all() -> DocumentFilter:
    return DocumentFilter()


async def test_admins_file_into_any_space(world: World) -> None:
    admin = await world.user("admin", role=Role.ADMIN)
    owner = await world.user()
    office = await world.spaces.create(Actor(owner.id), "Office")
    received = await world.pipeline().receive(
        Actor(admin.id), incoming(b"%PDF-1.7 b"), filename="b.pdf", space=office.id
    )
    await world.drain()
    document = await world.documents.get(Actor(admin.id), received.id)
    assert (document.space_id, document.lane) == (office.id, Lane.GREEN)
    # The space's editor sees it, as any document in their space.
    assert (await world.documents.get(Actor(owner.id), received.id)).id == received.id
    user = await world.user()
    with pytest.raises(NotFoundError):
        await world.pipeline().receive(
            Actor(user.id), incoming(b"%PDF-1.7 c"), filename="c.pdf", space=office.id
        )


async def test_admins_confirm_into_any_space(world: World) -> None:
    admin, boss = await _second_admin(world)
    owner, stranger = await world.user(), await world.user()
    foreign = await world.spaces.create(Actor(stranger.id), "Foreign")
    rules = await rule_world(world)
    pipeline = rules.pipeline()
    received = await pipeline.receive(Actor(owner.id), incoming(b"%PDF-1.7 d"), filename="d.pdf")
    await world.drain(rules.pipeline(Returns(UNCERTAIN)))
    with pytest.raises(NotFoundError):
        await pipeline.confirm(Actor(owner.id), received.id, DocumentChanges(), space=foreign.id)

    await pipeline.confirm(
        Actor(admin.id), received.id, DocumentChanges(), accept_suggestions=True, space=foreign.id
    )
    await world.drain(pipeline)
    filed = await world.documents.get(Actor(stranger.id), received.id)
    assert (filed.space_id, filed.lane) == (foreign.id, Lane.GREEN)
    # Who uploaded it is no member of the space it lies in now.
    with pytest.raises(NotFoundError):
        await world.documents.get(Actor(owner.id), received.id)

    # Rights hang on the space: filing holds, also once the admin is gone.
    await world.users.update(Actor(boss.id), admin.id, active=False)
    await pipeline.reprocess_from(Actor(stranger.id), received.id, Node.APPLY_RULES)
    await world.drain(pipeline)
    assert (await world.documents.get(Actor(stranger.id), received.id)).lane is Lane.GREEN


async def test_admins_change_the_rules_of_every_space(world: World) -> None:
    r = await rule_world(world)
    owner, stranger = await world.user(), await world.user()
    tag = await r.tag("t")
    rule = await r.personal_rule(owner, definition("Title", channel_api(), add_tags(tag.id)))
    foreign = await world.spaces.create(Actor(stranger.id), "Stranger's")

    # References are checked for whoever saves the rule: an admin may file anywhere.
    changed = await r.rules.change(
        Actor(r.admin.id), rule.id, definition("File", channel_api(), SetSpace(foreign.id))
    )
    personal = await world.personal_space(owner)
    assert (changed.scope, changed.space_id, changed.current.created_by) == (
        RuleScope.SPACE,
        personal.id,
        r.admin.id,
    )
    # The owner cannot file there: their change is refused.
    with pytest.raises(NotFoundError):
        await r.rules.change(
            Actor(owner.id), rule.id, definition("File", channel_api(), SetSpace(foreign.id))
        )
    await r.rules.delete(Actor(r.admin.id), rule.id)
    with pytest.raises(NotFoundError):
        await r.rules.get(Actor(owner.id), rule.id)
    # Nobody else changes the rules of a space they do not edit.
    other = await r.personal_rule(owner, definition("Other", channel_api(), add_tags(tag.id)))
    with pytest.raises(NotFoundError):
        await r.rules.change(
            Actor(stranger.id), other.id, definition("X", channel_api(), add_tags(tag.id))
        )


async def test_admins_apply_a_global_rule_to_every_document(world: World) -> None:
    r = await rule_world(world)
    alice, bob = await world.user(), await world.user()
    tax = await r.tag("tax")
    theirs = [await r.arrive(alice), await r.arrive(bob)]
    rule = await r.global_rule(definition("Tax", channel_api(), add_tags(tax.id)))

    preview = await r.applications.preview(Actor(r.admin.id), rule.id)
    assert {item.document.id for item in preview.items} == {d.id for d in theirs}
    # A user applies it to what they may edit only.
    assert [
        item.document.id for item in (await r.applications.preview(Actor(alice.id), rule.id)).items
    ] == [theirs[0].id]
