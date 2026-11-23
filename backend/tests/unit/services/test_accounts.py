"""Account management by admins and the first admin from configuration."""

import pytest

from lekto.core.domain.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    SecondFactorRequiredError,
    ValidationError,
)
from lekto.core.domain.identity import ExternalIdentity, TokenScope, hash_token
from lekto.core.domain.ids import UserId, new_id
from lekto.core.domain.rights import Actor
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import (
    BlockingSpace,
    Role,
    SeenUser,
    Settle,
    Settlement,
    UserDeletionBlockedError,
)
from lekto.core.services.users import UserService
from tests import builders
from tests.builders import NOW, PASSWORD, incoming
from tests.contracts.push import a_device
from tests.unit.services.support import World

NEW_PASSWORD = "another long passphrase"


async def test_admins_create_users_with_password(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.users.create_user(Actor(admin.id), "alice", Role.USER, PASSWORD)
    signed_in = await world.auth.login("alice", PASSWORD)
    assert signed_in.user == user
    assert (await world.personal_space(user)).personal_of == user.id
    for weak in ("short", "alice"):
        with pytest.raises(ValidationError):
            await world.users.create_user(Actor(admin.id), "bob", Role.USER, weak)
    nobody = await world.users.create_user(Actor(admin.id), "carol", Role.USER)
    account = await world.users.account(Actor(admin.id), nobody.id)
    assert not account.has_password and not account.totp_enabled


async def test_an_api_token_creates_only_plain_users(world: World) -> None:
    """Without a session (an API token, as a migration uses) a password or the role admin
    would turn a leaked token into a sign-in with more rights than the token gives."""
    admin = await world.account("root", Role.ADMIN)
    created = await world.users.create_user(Actor(admin.id), "alice", Role.USER, session=False)
    assert created.role is Role.USER
    for role, password in ((Role.ADMIN, None), (Role.USER, PASSWORD)):
        with pytest.raises(PermissionDeniedError, match="signed-in session"):
            await world.users.create_user(Actor(admin.id), "bob", role, password, session=False)


async def test_a_non_admin_is_refused_before_any_work(world: World) -> None:
    """Creating and deleting users check the admin first: a hash costs a place the sign-in
    shares, and preparing a deletion reads the documents of the spaces named and runs rules on
    their texts, so how long a refusal takes would tell a non-admin what they contain."""
    user = await world.account("alice")
    other = await world.account("bob")
    async with world.uow() as uow:
        bobs = next(
            space for space in await uow.spaces.list_accessible(other.id) if space.personal_of
        )
        alices = next(
            space for space in await uow.spaces.list_accessible(user.id) if space.personal_of
        )

    class Watching:
        """Rules that only count how often the deletion asks them."""

        asked = 0

        async def arrival_rules(self, *args: object, **kwargs: object) -> list[object]:
            Watching.asked += 1
            return []

        async def prepare(self, *args: object, **kwargs: object) -> object:
            Watching.asked += 1
            return None

    users = UserService(world.uow, world.clock, world.hasher, rules=Watching())  # type: ignore[arg-type]
    await world.pipeline().receive(
        Actor(other.id), incoming(b"%PDF-1.7 x"), filename="x.pdf", space=bobs.id
    )
    hashed = world.hasher.hashed
    with pytest.raises(PermissionDeniedError):
        await users.create_user(Actor(user.id), "eve", Role.USER, password="short")
    with pytest.raises(PermissionDeniedError):
        await users.delete_user(
            Actor(user.id),
            other.id,
            settle={bobs.id: Settlement(Settle.MOVE_TO, move_to=alices.id)},
        )
    assert (world.hasher.hashed, Watching.asked) == (hashed, 0)


async def test_only_admins_manage_accounts(world: World) -> None:
    user = await world.account("alice")
    other = await world.account("bob")
    calls = [
        world.users.create_user(Actor(user.id), "x", Role.USER),
        world.users.update(Actor(user.id), other.id, role=Role.ADMIN),
        world.users.update(Actor(user.id), other.id, active=False),
        world.users.reset_password(Actor(user.id), other.id, NEW_PASSWORD),
        world.users.disable_totp(Actor(user.id), other.id),
        world.users.unlink_external_identities(Actor(user.id), other.id),
        world.users.delete_user(Actor(user.id), other.id),
        world.users.account(Actor(user.id), other.id),
    ]
    for call in calls:
        with pytest.raises(PermissionDeniedError):
            await call


async def test_users_see_active_users_and_admins_all(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    alice, bob = await world.account("alice"), await world.account("Bob")
    await world.users.update(Actor(admin.id), bob.id, active=False)
    seen = await world.users.list_users(Actor(alice.id))
    assert [u.username for u in seen] == ["alice", "root"]
    # Others see names alone, admins also role, state and creation (RB-11).
    assert {(u.role, u.active, u.created_at) for u in seen} == {(None, None, None)}
    every = await world.users.list_users(Actor(admin.id))
    assert [u.username for u in every] == ["alice", "Bob", "root"]
    assert [u.active for u in every] == [True, False, True]
    assert (await world.users.get(Actor(alice.id), admin.id)).role is None
    with pytest.raises(NotFoundError):
        await world.users.get(Actor(alice.id), bob.id)
    assert (await world.users.get(Actor(admin.id), bob.id)).active is False


async def test_the_last_active_admin_stays(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    for call in (
        world.users.update(Actor(admin.id), admin.id, role=Role.USER),
        world.users.update(Actor(admin.id), admin.id, active=False),
        world.users.delete_user(Actor(admin.id), admin.id),
    ):
        with pytest.raises(ConflictError):
            await call
    second = await world.account("second", Role.ADMIN)
    inactive = await world.account("inactive", Role.ADMIN)
    await world.users.update(Actor(admin.id), inactive.id, active=False)
    await world.users.update(Actor(second.id), admin.id, role=Role.USER)
    with pytest.raises(ConflictError):  # the inactive admin does not count
        await world.users.update(Actor(second.id), second.id, role=Role.USER)


async def test_taking_admin_rights_writes_the_remaining_admins(world: World) -> None:
    """So that a concurrent change relying on them fails its version check."""
    admin = await world.account("root", Role.ADMIN)
    second = await world.account("second", Role.ADMIN)
    await world.users.update(Actor(admin.id), admin.id, role=Role.USER)
    async with world.uow() as uow:
        assert (await uow.users.get(second.id)).version == second.version + 1


async def test_role_changes_apply_at_once(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    signed_in = await world.auth.login("alice", PASSWORD)
    await world.users.update(Actor(admin.id), user.id, role=Role.ADMIN)
    principal = await world.auth.authenticate_session(signed_in.token)
    assert principal.user.is_admin
    await world.master_data.create_tag(Actor(user.id), "now possible")


async def test_deactivation_ends_sessions_and_refuses_tokens(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    signed_in = await world.auth.login("alice", PASSWORD)
    _, token = await world.auth.create_api_token(Actor(user.id), "cli", TokenScope.READ)

    await world.users.update(Actor(admin.id), user.id, active=False)

    async with world.uow() as uow:
        assert await uow.sessions.find_by_token(signed_in.session.token_hash) is None
    with pytest.raises(AuthenticationError):
        await world.auth.authenticate_token(token)
    with pytest.raises(AuthenticationError):
        await world.auth.login("alice", PASSWORD)
    with pytest.raises(AuthenticationError):
        await world.spaces.list_spaces(Actor(user.id))

    await world.users.update(Actor(admin.id), user.id, active=True)
    await world.auth.authenticate_token(token)
    await world.auth.login("alice", PASSWORD)


async def test_password_reset_by_an_admin(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    signed_in = await world.auth.login("alice", PASSWORD)
    _, token = await world.auth.create_api_token(Actor(user.id), "cli", TokenScope.READ)

    await world.users.reset_password(Actor(admin.id), user.id, NEW_PASSWORD)
    with pytest.raises(AuthenticationError):
        await world.auth.authenticate_session(signed_in.token)
    async with world.uow() as uow:  # no browser stays a known device
        assert await uow.known_devices.find_by_token(hash_token(signed_in.devices[0])) is None
    await world.auth.authenticate_token(token)
    await world.auth.login("alice", NEW_PASSWORD)

    # What a token made goes with it, also here (XA-K04): its push devices and webhooks.
    issued = (await world.auth.list_api_tokens(Actor(user.id)))[0]
    async with world.uow() as uow:
        device = a_device(user.id, api_token_id=issued.id)
        await uow.push_devices.add(device)
        await uow.commit()
    await world.users.reset_password(Actor(admin.id), user.id, PASSWORD, revoke_tokens=True)
    with pytest.raises(AuthenticationError):
        await world.auth.authenticate_token(token)
    async with world.uow() as uow:
        assert await uow.push_devices.find(device.id) is None
    with pytest.raises(ValidationError):
        await world.users.reset_password(Actor(admin.id), user.id, "short")


async def test_admins_turn_totp_off(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    setup = await world.auth.begin_totp(Actor(user.id))
    await world.auth.confirm_totp(Actor(user.id), world.totp.code(setup.secret, world.clock.now()))
    with pytest.raises(SecondFactorRequiredError):
        await world.auth.login("alice", PASSWORD)
    assert (await world.users.account(Actor(admin.id), user.id)).totp_enabled
    await world.users.disable_totp(Actor(admin.id), user.id)
    await world.auth.login("alice", PASSWORD)


async def test_admins_unlink_identity_providers(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    async with world.uow() as uow:
        await uow.external_identities.add(
            ExternalIdentity.link(issuer="https://idp", subject="s", user_id=user.id, now=NOW)
        )
        await uow.commit()
    assert len((await world.users.account(Actor(admin.id), user.id)).external_identities) == 1
    assert await world.users.unlink_external_identities(Actor(admin.id), user.id) == 1
    assert (await world.users.account(Actor(admin.id), user.id)).external_identities == []


async def test_deleting_a_user_without_documents(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    user = await world.account("alice")
    friend = await world.account("bob")
    personal = await world.personal_space(user)
    own = await world.spaces.create(Actor(user.id), "Mine")
    await world.spaces.set_member(Actor(user.id), own.id, friend.id, SpaceRole.EDIT)
    shared = await world.spaces.create(Actor(friend.id), "Shared")
    await world.spaces.set_member(Actor(friend.id), shared.id, user.id, SpaceRole.READ)
    await world.auth.create_api_token(Actor(user.id), "cli", TokenScope.READ)
    [device] = (await world.auth.login("alice", PASSWORD)).devices
    async with world.uow() as uow:
        uploaded = builders.processed(user, shared)
        await uow.documents.add(uploaded)
        await uow.commit()

    await world.users.delete_user(Actor(admin.id), user.id)

    async with world.uow() as uow:
        assert await uow.users.find(user.id) is None
        assert await uow.spaces.find(personal.id) is None
        assert (await uow.spaces.get(own.id)).members == {friend.id: SpaceRole.EDIT}
        assert (await uow.spaces.get(shared.id)).members == {friend.id: SpaceRole.EDIT}
        assert (await uow.documents.get(uploaded.id)).uploaded_by is None
        assert await uow.credentials.find(user.id) is None
        assert await uow.api_tokens.list_for(user.id) == []
        assert await uow.known_devices.find_by_token(hash_token(device)) is None
    with pytest.raises(AuthenticationError):
        await world.auth.login("alice", PASSWORD)
    with pytest.raises(NotFoundError):
        await world.users.delete_user(Actor(admin.id), UserId(new_id()))


async def test_spaces_that_stop_deleting_a_user_need_a_decision(world: World) -> None:
    """Tobi, 22.10.2026: the personal space with documents and each space the user alone
    edits stop it until the deletion settles them; an empty personal space goes along."""
    admin = await world.account("root", Role.ADMIN)
    alice, bob = await world.account("alice"), await world.account("bob")
    household = await world.spaces.create(Actor(alice.id), "Household")
    await world.spaces.set_member(Actor(alice.id), household.id, bob.id, SpaceRole.READ)
    async with world.uow() as uow:
        await uow.documents.add(builders.processed(alice, await uow.spaces.get_personal(bob.id)))
        await uow.commit()
    bobs = await world.personal_space(bob)

    assert await world.users.removal(Actor(admin.id), bob.id) == [
        BlockingSpace(bobs.id, bobs.name, True, 1, (Settle.MOVE_TO,))
    ]
    assert await world.users.removal(Actor(admin.id), alice.id) == [
        BlockingSpace(household.id, "Household", False, 0, (Settle.REMOVE, Settle.EDITOR))
    ]
    with pytest.raises(UserDeletionBlockedError) as blocked:
        await world.users.delete_user(Actor(admin.id), bob.id)
    assert [space.id for space in blocked.value.spaces] == [bobs.id]
    with pytest.raises(UserDeletionBlockedError, match="'Household'"):
        await world.users.delete_user(Actor(admin.id), alice.id)
    with pytest.raises(PermissionDeniedError):
        await world.users.removal(Actor(alice.id), bob.id)


async def test_deleting_a_user_settles_their_spaces(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    erika, john = await world.account("erika"), await world.account("john")
    erikas, johns = await world.personal_space(erika), await world.personal_space(john)
    household = await world.spaces.create(Actor(erika.id), "Household")
    await world.spaces.set_member(Actor(erika.id), household.id, john.id, SpaceRole.READ)
    empty = await world.spaces.create(Actor(erika.id), "Empty")
    archive = await world.spaces.create(Actor(erika.id), "Archive")
    target = await world.spaces.create(Actor(admin.id), "Target")
    async with world.uow() as uow:
        letters = [builders.processed(erika, erikas) for _ in range(2)]
        bill, kept = builders.processed(erika, household), builders.processed(erika, archive)
        for document in [*letters, bill, kept]:
            await uow.documents.add(document)
        await uow.commit()

    await world.users.delete_user(
        Actor(admin.id),
        erika.id,
        {
            erikas.id: Settlement(Settle.MOVE_TO, move_to=johns.id),
            household.id: Settlement(Settle.MOVE_TO, move_to=target.id),
            empty.id: Settlement(Settle.REMOVE),
            archive.id: Settlement(Settle.EDITOR, editor=john.id),
        },
    )

    async with world.uow() as uow:
        assert await uow.users.find(erika.id) is None
        for gone in (erikas, household, empty):
            assert await uow.spaces.find(gone.id) is None
        assert (await uow.spaces.get(archive.id)).members == {john.id: SpaceRole.EDIT}
        for letter in letters:
            moved = await uow.documents.get(letter.id)
            assert moved.space_id == johns.id and moved.uploaded_by is None
            assert moved.new_at is not None  # new for john, who could not read it before
        assert (await uow.documents.get(bill.id)).space_id == target.id
        assert (await uow.documents.get(kept.id)).space_id == archive.id


async def test_a_deletion_that_cannot_settle_changes_nothing(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    erika, john = await world.account("erika"), await world.account("john")
    erikas = await world.personal_space(erika)
    full = await world.spaces.create(Actor(erika.id), "Full")
    async with world.uow() as uow:
        for space in (erikas, full):
            await uow.documents.add(builders.processed(erika, space))
        await uow.commit()
    elsewhere = await world.spaces.create(Actor(john.id), "Elsewhere")
    settle = {erikas.id: Settlement(Settle.MOVE_TO, move_to=full.id)}
    # Into a space that goes as well, or: removing a space that holds documents.
    with pytest.raises(NotFoundError):
        await world.users.delete_user(
            Actor(admin.id),
            erika.id,
            {**settle, full.id: Settlement(Settle.MOVE_TO, move_to=erikas.id)},
        )
    with pytest.raises(ValidationError, match="cannot be settled by remove"):
        await world.users.delete_user(
            Actor(admin.id),
            erika.id,
            {
                erikas.id: Settlement(Settle.MOVE_TO, move_to=elsewhere.id),
                full.id: Settlement(Settle.REMOVE),
            },
        )
    with pytest.raises(ValidationError, match="does not stop deleting the user"):
        await world.users.delete_user(
            Actor(admin.id),
            erika.id,
            {
                erikas.id: Settlement(Settle.MOVE_TO, move_to=elsewhere.id),
                full.id: Settlement(Settle.EDITOR, editor=john.id),
                elsewhere.id: Settlement(Settle.REMOVE),
            },
        )
    with pytest.raises(NotFoundError):
        await world.users.delete_user(
            Actor(admin.id),
            erika.id,
            {
                erikas.id: Settlement(Settle.MOVE_TO, move_to=elsewhere.id),
                full.id: Settlement(Settle.EDITOR, editor=erika.id),
            },
        )
    async with world.uow() as uow:
        assert await uow.users.find(erika.id) is not None
        assert {space.id for space in await uow.spaces.list_accessible(erika.id)} >= {
            erikas.id,
            full.id,
        }
        assert await uow.documents.exists(space=erikas.id)


# --- first admin --------------------------------------------------------------------------------


async def test_the_first_admin_is_created_once(world: World) -> None:
    created = await world.users.bootstrap_admin("root", PASSWORD)
    assert created is not None and created.is_admin
    await world.auth.login("root", PASSWORD)
    assert (await world.personal_space(created)).personal_of == created.id
    # Later starts change nothing, also not the password.
    assert await world.users.bootstrap_admin("root", NEW_PASSWORD) is None
    assert await world.users.bootstrap_admin("other", NEW_PASSWORD) is None
    with pytest.raises(AuthenticationError):
        await world.auth.login("root", NEW_PASSWORD)


async def test_the_first_admin_is_created_while_all_admins_are_inactive(world: World) -> None:
    """A token that deactivated the admins (1-01) must not lock the operator out for good."""
    locked = await world.account("root", Role.ADMIN)
    assert await world.users.bootstrap_admin("rescue", NEW_PASSWORD) is None
    locked.active = False
    async with world.uow() as uow:
        await uow.users.update(locked)
        await uow.commit()
    with pytest.raises(ConflictError):
        await world.users.bootstrap_admin("root", NEW_PASSWORD)  # never changes an account
    rescue = await world.users.bootstrap_admin("rescue", NEW_PASSWORD)
    assert rescue is not None and rescue.is_active_admin


async def test_the_first_admin_does_not_take_over_a_user(world: World) -> None:
    await world.account("alice")
    with pytest.raises(ConflictError):
        await world.users.bootstrap_admin("Alice", NEW_PASSWORD)
    with pytest.raises(ValidationError):
        await world.users.bootstrap_admin("root", "short")
    await world.auth.login("alice", PASSWORD)


async def test_admins_do_not_reset_their_own_sign_in_here(world: World) -> None:
    """M4-03: the own password and TOTP are changed through AuthService, which needs the
    current password or a code."""
    admin = await world.account("root", Role.ADMIN)
    with pytest.raises(PermissionDeniedError):
        await world.users.reset_password(Actor(admin.id), admin.id, NEW_PASSWORD)
    with pytest.raises(PermissionDeniedError):
        await world.users.disable_totp(Actor(admin.id), admin.id)
    await world.auth.login("root", PASSWORD)


async def test_a_token_changes_no_role_and_no_admins_state(world: World) -> None:
    """1-01: a leaked admin token must not make an account an admin (that account then signs in
    with a session) nor lock the admins out."""
    admin, other, second = (
        await world.user(role=Role.ADMIN),
        await world.user(),
        await world.user(role=Role.ADMIN),
    )
    with pytest.raises(PermissionDeniedError, match="session"):
        await world.users.update(Actor(admin.id), other.id, role=Role.ADMIN, session=False)
    with pytest.raises(PermissionDeniedError, match="session"):
        await world.users.update(Actor(admin.id), second.id, active=False, session=False)
    assert (await world.users.get(Actor(admin.id), other.id)).role is Role.USER
    assert (await world.users.get(Actor(admin.id), second.id)).active
    # What a migration does: deactivating and reactivating users, and no-ops.
    assert not (
        await world.users.update(Actor(admin.id), other.id, active=False, session=False)
    ).active
    assert (await world.users.update(Actor(admin.id), other.id, active=True, session=False)).active
    await world.users.update(Actor(admin.id), other.id, role=Role.USER, session=False)
    await world.users.update(Actor(admin.id), second.id, active=True, session=False)


async def test_role_and_state_change_together(world: World) -> None:
    admin = await world.account("root", Role.ADMIN)
    other = await world.account("second", Role.ADMIN)
    await world.auth.login("second", PASSWORD)
    changed = await world.users.update(Actor(admin.id), other.id, role=Role.USER, active=False)
    assert (changed.role, changed.active) == (Role.USER, False)
    async with world.uow() as uow:
        assert await uow.sessions.remove_for_user(other.id) == 0  # ended with the change
    with pytest.raises(ConflictError):  # nothing changes when one part is refused
        await world.users.update(Actor(admin.id), admin.id, role=Role.ADMIN, active=False)
    assert (await world.users.get(Actor(admin.id), admin.id)).active is True
    unchanged = await world.users.update(Actor(admin.id), admin.id)
    assert SeenUser.of(unchanged, by_admin=True) == await world.users.get(Actor(admin.id), admin.id)
