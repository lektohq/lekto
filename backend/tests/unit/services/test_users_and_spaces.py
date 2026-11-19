import pytest

from lekto.core.domain.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from lekto.core.domain.ids import SpaceId, UserId, new_id
from lekto.core.domain.rights import Actor
from lekto.core.domain.spaces import PERSONAL_SPACE_NAME, SpaceRole
from lekto.core.domain.users import Role
from tests.builders import incoming
from tests.unit.services.support import World


async def test_admin_creates_user_with_personal_space(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    user = await world.users.create_user(Actor(admin.id), "dana", Role.USER)
    async with world.uow() as uow:
        assert await uow.users.get(user.id) == user
        personal = await uow.spaces.get_personal(user.id)
    assert personal.personal_of == user.id
    assert personal.name == PERSONAL_SPACE_NAME
    assert personal.members == {user.id: SpaceRole.EDIT}


async def test_only_admins_create_users(world: World) -> None:
    user = await world.user()
    with pytest.raises(PermissionDeniedError):
        await world.users.create_user(Actor(user.id), "eve", Role.USER)


async def test_usernames_are_unique(world: World) -> None:
    admin = await world.user("root", role=Role.ADMIN)
    with pytest.raises(ConflictError):
        await world.users.create_user(Actor(admin.id), "ROOT", Role.USER)


async def test_unknown_or_deactivated_actor_is_not_authenticated(world: World) -> None:
    with pytest.raises(AuthenticationError):
        await world.users.create_user(Actor(UserId(new_id())), "x", Role.USER)
    admin = await world.user(role=Role.ADMIN)
    async with world.uow() as uow:
        stored = await uow.users.get(admin.id)
        stored.active = False
        await uow.users.update(stored)
        await uow.commit()
    with pytest.raises(AuthenticationError):
        await world.users.create_user(Actor(admin.id), "x", Role.USER)


async def test_a_creator_edits_renames_and_shares_spaces(world: World) -> None:
    creator, other = await world.user(), await world.user()
    space = await world.spaces.create(Actor(creator.id), "Household")
    assert space.members == {creator.id: SpaceRole.EDIT}
    renamed = await world.spaces.change(Actor(creator.id), space.id, name="Home")
    assert renamed.name == "Home"
    shared = await world.spaces.set_member(Actor(creator.id), space.id, other.id, SpaceRole.READ)
    assert shared.members == {creator.id: SpaceRole.EDIT, other.id: SpaceRole.READ}
    assert {d.id for d in await world.spaces.list_spaces(Actor(other.id))} == {
        space.id,
        (await world.personal_space(other)).id,
    }
    unshared = await world.spaces.remove_member(Actor(creator.id), space.id, other.id)
    assert unshared.members == {creator.id: SpaceRole.EDIT}


async def test_a_space_is_created_with_members(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    creator, reader, editor = await world.user(), await world.user(), await world.user()
    space = await world.spaces.create(
        Actor(creator.id), "Household", members={reader.id: SpaceRole.READ}
    )
    assert space.members == {creator.id: SpaceRole.EDIT, reader.id: SpaceRole.READ}
    # An admin gives the members alone (the migration client creates spaces so).
    theirs = await world.spaces.create(
        Actor(admin.id), "Theirs", members={editor.id: SpaceRole.EDIT, reader.id: SpaceRole.READ}
    )
    assert theirs.members == {editor.id: SpaceRole.EDIT, reader.id: SpaceRole.READ}
    with pytest.raises(ValidationError, match="one editor"):
        await world.spaces.create(
            Actor(admin.id), "Nobody edits", members={reader.id: SpaceRole.READ}
        )
    mine = await world.spaces.create(Actor(admin.id), "Mine")
    assert mine.members == {admin.id: SpaceRole.EDIT}
    with pytest.raises(NotFoundError):
        await world.spaces.create(
            Actor(creator.id), "Ghost", members={UserId(new_id()): SpaceRole.READ}
        )


async def test_names_of_shared_spaces_are_unique(world: World) -> None:
    owner, other = await world.user(), await world.user()
    first = await world.spaces.create(Actor(owner.id), "Taxes")
    with pytest.raises(ConflictError):
        await world.spaces.create(Actor(other.id), "taxes")
    second = await world.spaces.create(Actor(owner.id), "Insurance")
    with pytest.raises(ConflictError):
        await world.spaces.change(Actor(owner.id), second.id, name="TAXES")
    assert (await world.spaces.change(Actor(owner.id), first.id, name="TAXES")).name == "TAXES"
    # The personal spaces share their stored name and are apart.
    assert (await world.spaces.create(Actor(owner.id), "Personal")).name == "Personal"


async def test_editors_manage_a_space_readers_do_not(world: World) -> None:
    creator, editor, reader = await world.user(), await world.user(), await world.user()
    stranger = await world.user()
    space = await world.spaces.create(Actor(creator.id), "Household")
    await world.spaces.set_member(Actor(creator.id), space.id, editor.id, SpaceRole.EDIT)
    await world.spaces.set_member(Actor(creator.id), space.id, reader.id, SpaceRole.READ)
    assert (await world.spaces.change(Actor(editor.id), space.id, name="Ours")).name == "Ours"
    await world.spaces.set_member(Actor(editor.id), space.id, stranger.id, SpaceRole.READ)
    await world.spaces.remove_member(Actor(editor.id), space.id, stranger.id)
    with pytest.raises(PermissionDeniedError):
        await world.spaces.change(Actor(reader.id), space.id, name="Mine")
    with pytest.raises(PermissionDeniedError):
        await world.spaces.set_member(Actor(reader.id), space.id, stranger.id, SpaceRole.READ)
    with pytest.raises(NotFoundError):
        await world.spaces.change(Actor(stranger.id), space.id, name="Mine")
    with pytest.raises(NotFoundError):
        await world.spaces.change(Actor(creator.id), SpaceId(new_id()), name="Mine")
    # A space keeps an editor.
    await world.spaces.remove_member(Actor(editor.id), space.id, creator.id)
    with pytest.raises(ValidationError, match="one editor"):
        await world.spaces.remove_member(Actor(editor.id), space.id, editor.id)


async def test_a_personal_space_is_shared_by_its_user(world: World) -> None:
    user, other, third = await world.user(), await world.user(), await world.user()
    personal = await world.personal_space(user)
    shared = await world.spaces.set_member(Actor(user.id), personal.id, other.id, SpaceRole.EDIT)
    assert shared.members == {user.id: SpaceRole.EDIT, other.id: SpaceRole.EDIT}
    # Who edits it does not choose its members, nor rename or delete it.
    with pytest.raises(PermissionDeniedError, match="its user"):
        await world.spaces.set_member(Actor(other.id), personal.id, third.id, SpaceRole.READ)
    with pytest.raises(ValidationError, match="keeps its name"):
        await world.spaces.change(Actor(user.id), personal.id, name="Mine")
    with pytest.raises(ConflictError):
        await world.spaces.delete(Actor(user.id), personal.id)
    with pytest.raises(ValidationError, match="always edits"):
        await world.spaces.remove_member(Actor(user.id), personal.id, user.id)
    await world.spaces.remove_member(Actor(user.id), personal.id, other.id)


async def test_spaces_are_read_and_deleted(world: World) -> None:
    owner, reader, stranger = await world.user(), await world.user(), await world.user()
    space = await world.spaces.create(Actor(owner.id), "Archive")
    await world.spaces.set_member(Actor(owner.id), space.id, reader.id, SpaceRole.READ)
    assert (await world.spaces.get(Actor(reader.id), space.id)).id == space.id
    with pytest.raises(NotFoundError):
        await world.spaces.get(Actor(stranger.id), space.id)
    with pytest.raises(PermissionDeniedError):
        await world.spaces.delete(Actor(reader.id), space.id)
    with pytest.raises(NotFoundError):
        await world.spaces.delete(Actor(stranger.id), space.id)
    with pytest.raises(ConflictError):
        await world.spaces.delete(Actor(owner.id), (await world.personal_space(owner)).id)
    await world.pipeline().receive(
        Actor(owner.id), incoming(b"%PDF-1.7 x"), filename="x.pdf", space=space.id
    )
    with pytest.raises(ConflictError):
        await world.spaces.delete(Actor(owner.id), space.id)
    empty = await world.spaces.create(Actor(owner.id), "Empty")
    await world.spaces.delete(Actor(owner.id), empty.id)
    with pytest.raises(NotFoundError):
        await world.spaces.get(Actor(owner.id), empty.id)


async def test_deactivated_users_become_no_members(world: World) -> None:
    """M4-10: a membership would take effect unnoticed when the user is activated again."""
    admin, owner, gone = await world.user(role=Role.ADMIN), await world.user(), await world.user()
    space = await world.spaces.create(Actor(owner.id), "Household")
    await world.users.update(Actor(admin.id), gone.id, active=False)
    with pytest.raises(NotFoundError):
        await world.spaces.set_member(Actor(owner.id), space.id, gone.id, SpaceRole.READ)
    with pytest.raises(NotFoundError):
        await world.spaces.set_member(Actor(owner.id), space.id, UserId(new_id()), SpaceRole.READ)


async def test_members_leave_a_space_themselves(world: World) -> None:
    """A reader too; the user of a personal space and the last editor stay; nobody removes
    another member without the right to choose them."""
    owner, reader, other = await world.user(), await world.user(), await world.user()
    space = await world.spaces.create(Actor(owner.id), "Household")
    await world.spaces.set_member(Actor(owner.id), space.id, reader.id, SpaceRole.READ)
    await world.spaces.set_member(Actor(owner.id), space.id, other.id, SpaceRole.READ)
    with pytest.raises(PermissionDeniedError):
        await world.spaces.remove_member(Actor(reader.id), space.id, other.id)
    left = await world.spaces.remove_member(Actor(reader.id), space.id, reader.id)
    assert reader.id not in left.members
    with pytest.raises(NotFoundError):
        await world.spaces.get(Actor(reader.id), space.id)
    with pytest.raises(ValidationError):
        await world.spaces.remove_member(Actor(owner.id), space.id, owner.id)
    home = await world.personal_space(owner)
    await world.spaces.set_member(Actor(owner.id), home.id, other.id, SpaceRole.EDIT)
    with pytest.raises(ValidationError):
        await world.spaces.remove_member(Actor(owner.id), home.id, owner.id)
    assert (
        other.id
        not in (await world.spaces.remove_member(Actor(other.id), home.id, other.id)).members
    )


async def test_spaces_are_listed_as_they_read(world: World) -> None:
    """By how they read, a personal space by its person's name, umlauts as their letters: for
    REST and MCP alike (review 0.12.2, A-12)."""
    zoe = await world.user("zoe")
    for name in ("öko", "Bank", "Ärzte"):
        await world.spaces.create(Actor(zoe.id), name)
    personal = await world.personal_space(zoe)
    listed = await world.spaces.list_spaces(Actor(zoe.id))
    assert [space.name for space in listed if space.id != personal.id] == ["Ärzte", "Bank", "öko"]
    assert listed[-1].id == personal.id  # "zoe" comes last
