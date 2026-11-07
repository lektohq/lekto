"""Web push: the devices a person receives notifications on, and sending one message.

First sender: `webpush` (RFC 8291 encryption and RFC 8292 VAPID on `cryptography`, over
httpx2). The sender only transports; what to send and when is the push service's (core) job.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from lekto.core.domain.ids import PushDeviceId, UserId
from lekto.core.domain.push import PushDevice, PushMessage, PushPreferences


class PushDeviceRepository(Protocol):
    async def add(self, device: PushDevice) -> None: ...

    async def find(self, id: PushDeviceId) -> PushDevice | None: ...

    async def find_by_endpoint(self, endpoint: str) -> PushDevice | None: ...

    async def list_for(self, user: UserId) -> list[PushDevice]:
        """The user's devices, oldest first."""
        ...

    async def update(self, device: PushDevice) -> None: ...

    async def remove(self, id: PushDeviceId) -> None: ...

    async def remove_for_user(self, user: UserId) -> int: ...


class PushPreferencesRepository(Protocol):
    async def find(self, user: UserId) -> PushPreferences | None: ...

    async def save(self, preferences: PushPreferences) -> None:
        """Add them, or update them (ConcurrencyError if they changed meanwhile)."""
        ...


class PushOutcome(StrEnum):
    DELIVERED = "delivered"
    """The push service took the message (it delivers it when the device is online)."""
    GONE = "gone"
    """The push service no longer knows the device (404, 410): forget it."""
    FAILED = "failed"
    """No answer, or one that refused this message; another may get through."""


@dataclass(frozen=True, kw_only=True)
class PushResult:
    outcome: PushOutcome
    status_code: int | None = None
    error: str | None = None


class PushSender(Protocol):
    @property
    def public_key(self) -> str:
        """The VAPID public key (P-256, uncompressed, base64url): the browser subscribes with it
        (`applicationServerKey`)."""
        ...

    async def send(self, device: PushDevice, message: PushMessage) -> PushResult:
        """Encrypt `message` for `device` and hand it to its push service, once. Never raises;
        an error does not contain the device's address (it is a secret of the device)."""
        ...
