"""Notifications on a person's devices (web push; web/DESIGN.md, "App").

A device belongs to its owner alone: nobody else, admins included, learns that it exists
(NotFoundError). A browser's address at its push service is one device: subscribing again (after
another person signed in there) moves it to whoever subscribes. Each delivery is recorded on the
device: a push service that no longer knows it (404, 410) or failures in a row
(`GIVE_UP_AFTER`) make Lekto forget it. Without a VAPID key the server sends nothing and takes no
device (`push_off`). Devices are settings: no events.
"""

import logging
from dataclasses import replace

from lekto.core.domain.errors import ConcurrencyError, ConflictError, NotFoundError
from lekto.core.domain.ids import PushDeviceId, UserId, new_id
from lekto.core.domain.push import (
    GIVE_UP_AFTER,
    MAX_DEVICES,
    PushDevice,
    PushKind,
    PushMessage,
)
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.clock import Clock
from lekto.core.ports.push import PushOutcome, PushResult, PushSender
from lekto.core.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory

log = logging.getLogger(__name__)


class PushService:
    def __init__(self, uow: UnitOfWorkFactory, clock: Clock, sender: PushSender | None) -> None:
        self._uow = uow
        self._clock = clock
        self._sender = sender

    @property
    def enabled(self) -> bool:
        return self._sender is not None

    @property
    def public_key(self) -> str | None:
        """The key browsers subscribe with; None without push."""
        return None if self._sender is None else self._sender.public_key

    async def register(
        self,
        actor: UserId,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
        name: str,
        locale: str,
    ) -> PushDevice:
        """Take a browser's subscription for `actor`; the same address again replaces it."""
        self._sender_or_off()
        now = self._clock.now()
        device = PushDevice(
            id=PushDeviceId(new_id()),
            user_id=actor,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            name=name,
            locale=locale,
            created_at=now,
        )
        async with self._uow() as uow:
            known = await uow.push_devices.find_by_endpoint(endpoint)
            if known is not None:
                device = replace(
                    device,
                    id=known.id,
                    created_at=known.created_at,
                    version=known.version,
                )
                await uow.push_devices.update(device)
            else:
                if len(await uow.push_devices.list_for(actor)) >= MAX_DEVICES:
                    raise ConflictError(because(ReasonCode.PUSH_DEVICES_LIMIT))
                await uow.push_devices.add(device)
            await uow.commit()
        log.info("push device registered", extra={"user_id": str(actor)})
        return device

    async def devices(self, actor: UserId) -> list[PushDevice]:
        async with self._uow() as uow:
            return await uow.push_devices.list_for(actor)

    async def remove(self, actor: UserId, id: PushDeviceId) -> None:
        async with self._uow() as uow:
            await self._own(uow, actor, id)
            await uow.push_devices.remove(id)
            await uow.commit()

    async def test(self, actor: UserId, id: PushDeviceId) -> PushResult:
        """Send the device a test notification now."""
        self._sender_or_off()
        async with self._uow() as uow:
            device = await self._own(uow, actor, id)
        message = PushMessage(
            kind=PushKind.TEST, url="/ui/settings?tab=notifications", tag="lekto-test"
        )
        return await self.deliver(device, message)

    async def send_to(self, user: UserId, message: PushMessage) -> int:
        """Send `message` to every device of `user`; how many push services took it."""
        if self._sender is None:
            return 0
        async with self._uow() as uow:
            devices = await uow.push_devices.list_for(user)
        delivered = 0
        for device in devices:
            result = await self.deliver(device, message)
            delivered += result.outcome is PushOutcome.DELIVERED
        return delivered

    async def deliver(self, device: PushDevice, message: PushMessage) -> PushResult:
        """Send once and record the outcome on the device."""
        sender = self._sender_or_off()
        result = await sender.send(device, message)
        try:
            async with self._uow() as uow:
                current = await uow.push_devices.find(device.id)
                if current is None:
                    return result
                if result.outcome is PushOutcome.DELIVERED:
                    current.last_success_at = self._clock.now()
                    current.failures = 0
                    await uow.push_devices.update(current)
                elif result.outcome is PushOutcome.GONE or current.failures + 1 >= GIVE_UP_AFTER:
                    await uow.push_devices.remove(current.id)
                    log.info("push device forgotten", extra={"status": result.status_code})
                else:
                    current.failures += 1
                    await uow.push_devices.update(current)
                await uow.commit()
        except (ConcurrencyError, NotFoundError):
            pass  # Changed or removed meanwhile: the next delivery records again.
        return result

    def _sender_or_off(self) -> PushSender:
        if self._sender is None:
            raise ConflictError(because(ReasonCode.PUSH_OFF))
        return self._sender

    @staticmethod
    async def _own(uow: UnitOfWork, actor: UserId, id: PushDeviceId) -> PushDevice:
        device = await uow.push_devices.find(id)
        if device is None or device.user_id != actor:
            raise NotFoundError("push device", id)
        return device
