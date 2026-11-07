"""Contract suites for web push: the repository of devices and the sender."""

import base64

import pytest

from lekto.adapters.outbound.memory.push import FAKE_PUBLIC_KEY
from lekto.core.domain.errors import ConcurrencyError, ConflictError, NotFoundError
from lekto.core.domain.ids import DocumentId, PushDeviceId, UserId, new_id
from lekto.core.domain.push import PushDevice, PushKind, PushMessage, PushPreferences
from lekto.core.ports.push import PushOutcome, PushSender
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests.builders import HOUR, NOW
from tests.contracts.unit_of_work import a_user, users

AUTH = "BTBZMqHH6r4Tts7J_aSIgg"


def a_device(
    user: UserId, endpoint: str = "https://web.push.apple.com/QGx1", **changes: object
) -> PushDevice:
    values: dict[str, object] = {
        "id": PushDeviceId(new_id()),
        "user_id": user,
        "endpoint": endpoint,
        "p256dh": FAKE_PUBLIC_KEY,
        "auth": AUTH,
        "name": "iPhone",
        "created_at": NOW,
        "locale": "de",
    }
    values.update(changes)
    return PushDevice(**values)  # type: ignore[arg-type]


class PushDeviceRepositoryContract:
    async def test_a_device_round_trips_and_is_found_by_its_address(
        self, uow_factory: UnitOfWorkFactory
    ) -> None:
        user = await a_user(uow_factory)
        device = a_device(user.id, last_success_at=NOW + HOUR, failures=2)
        async with uow_factory() as uow:
            await uow.push_devices.add(device)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.push_devices.find(device.id) == device
            assert await uow.push_devices.find_by_endpoint(device.endpoint) == device
            assert await uow.push_devices.find_by_endpoint("https://web.push.apple.com/x") is None

    async def test_a_users_devices_oldest_first(self, uow_factory: UnitOfWorkFactory) -> None:
        user, other = await users(uow_factory, 2)
        later = a_device(user.id, "https://fcm.googleapis.com/fcm/send/b", created_at=NOW + HOUR)
        first = a_device(user.id, "https://fcm.googleapis.com/fcm/send/a")
        foreign = a_device(other.id, "https://updates.push.services.mozilla.com/wpush/v2/c")
        async with uow_factory() as uow:
            for device in (later, first, foreign):
                await uow.push_devices.add(device)
            await uow.commit()
        async with uow_factory() as uow:
            assert [d.id for d in await uow.push_devices.list_for(user.id)] == [first.id, later.id]
            assert await uow.push_devices.remove_for_user(user.id) == 2
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.push_devices.list_for(user.id) == []
            assert [d.id for d in await uow.push_devices.list_for(other.id)] == [foreign.id]

    async def test_an_address_is_one_device(self, uow_factory: UnitOfWorkFactory) -> None:
        user = await a_user(uow_factory)
        async with uow_factory() as uow:
            await uow.push_devices.add(a_device(user.id))
            await uow.commit()
        with pytest.raises(ConflictError):
            async with uow_factory() as uow:
                await uow.push_devices.add(a_device(user.id))
                await uow.commit()

    async def test_an_update_checks_the_version(self, uow_factory: UnitOfWorkFactory) -> None:
        user = await a_user(uow_factory)
        device = a_device(user.id)
        async with uow_factory() as uow:
            await uow.push_devices.add(device)
            await uow.commit()
        async with uow_factory() as uow:
            changed = await uow.push_devices.find(device.id)
            assert changed is not None
            changed.failures = 3
            changed.last_success_at = NOW
            await uow.push_devices.update(changed)
            await uow.commit()
        async with uow_factory() as uow:
            stored = await uow.push_devices.find(device.id)
            assert stored is not None and stored.failures == 3 and stored.version == 2
            with pytest.raises(ConcurrencyError):
                await uow.push_devices.update(device)

    async def test_a_removed_device_is_gone(self, uow_factory: UnitOfWorkFactory) -> None:
        user = await a_user(uow_factory)
        device = a_device(user.id)
        async with uow_factory() as uow:
            await uow.push_devices.add(device)
            await uow.push_devices.remove(device.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.push_devices.find(device.id) is None
            with pytest.raises(NotFoundError):
                await uow.push_devices.remove(device.id)


class PushPreferencesRepositoryContract:
    async def test_preferences_are_saved_and_changed(self, uow_factory: UnitOfWorkFactory) -> None:
        user = await a_user(uow_factory)
        documents = (DocumentId(new_id()), DocumentId(new_id()))
        async with uow_factory() as uow:
            assert await uow.push_preferences.find(user.id) is None
            await uow.push_preferences.save(
                PushPreferences(
                    id=user.id, kinds=frozenset({PushKind.WAITING}), titles=False, pending=documents
                )
            )
            await uow.commit()
        async with uow_factory() as uow:
            stored = await uow.push_preferences.find(user.id)
            assert stored is not None
            assert (stored.kinds, stored.titles, stored.pending) == (
                frozenset({PushKind.WAITING}),
                False,
                documents,
            )
            stored.pending = ()
            await uow.push_preferences.save(stored)
            await uow.commit()
        async with uow_factory() as uow:
            changed = await uow.push_preferences.find(user.id)
            assert changed is not None and changed.pending == () and changed.version == 2
            stale = PushPreferences(id=user.id, version=1)
            with pytest.raises(ConcurrencyError):
                await uow.push_preferences.save(stale)

    async def test_they_go_with_their_user(self, uow_factory: UnitOfWorkFactory) -> None:
        user = await a_user(uow_factory)
        async with uow_factory() as uow:
            await uow.push_preferences.save(PushPreferences(id=user.id))
            await uow.commit()
        async with uow_factory() as uow:
            await uow.users.remove(user.id)
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.push_preferences.find(user.id) is None


class PushSenderContract:
    """What every push sender keeps; `sender` delivers to `a_device`'s address."""

    async def test_the_public_key_is_a_p256_point(self, sender: PushSender) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        raw = base64.urlsafe_b64decode(sender.public_key + "=" * (-len(sender.public_key) % 4))
        assert len(raw) == 65 and raw[0] == 4
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)

    async def test_a_message_is_delivered_and_nothing_raises(self, sender: PushSender) -> None:
        device = a_device(UserId(new_id()))
        result = await sender.send(device, PushMessage(kind=PushKind.TEST))
        assert result.outcome is PushOutcome.DELIVERED
        assert result.error is None
