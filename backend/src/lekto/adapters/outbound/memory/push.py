"""The devices of web push in memory, and a stand-in push service for tests."""

from collections.abc import Callable

from lekto.adapters.outbound.memory.rows import MemoryRepository, _copy
from lekto.core.domain.ids import PushDeviceId, UserId
from lekto.core.domain.push import PushDevice, PushMessage, PushPreferences
from lekto.core.ports.push import PushOutcome, PushResult

# A valid P-256 point, base64url, as a stand-in for Lekto's VAPID public key.
FAKE_PUBLIC_KEY = (
    "BGvzF6zWejQ5l7PQ34JOmxbdz9I7uYmQKFeQDvnm345kRw3z914m-6_mTZGxrLcSgjP-pgIDSC_ULL3Jk5I1Lrw"
)


class MemoryPushDeviceRepository(MemoryRepository[PushDeviceId, PushDevice]):
    async def find_by_endpoint(self, endpoint: str) -> PushDevice | None:
        return next((_copy(row) for row in self._all() if row.endpoint == endpoint), None)

    async def list_for(self, user: UserId) -> list[PushDevice]:
        rows = [row for row in self._all() if row.user_id == user]
        return [_copy(row) for row in sorted(rows, key=lambda row: (row.created_at, row.id))]

    async def remove_for_user(self, user: UserId) -> int:
        return self._remove_rows([row for row in self._all() if row.user_id == user])


class MemoryPushPreferencesRepository(MemoryRepository[UserId, PushPreferences]):
    async def save(self, preferences: PushPreferences) -> None:
        if self._uow._row(self._table, preferences.id) is None:
            await self.add(preferences)
        else:
            await self.update(preferences)


class FakePushSender:
    """Records what it was asked to send. Delivers unless `answers` maps a device's address to
    another outcome, or is a function of device and message."""

    def __init__(
        self,
        answers: dict[str, PushOutcome]
        | Callable[[PushDevice, PushMessage], PushOutcome]
        | None = None,
    ) -> None:
        self.sent: list[tuple[PushDevice, PushMessage]] = []
        self.answers = answers or {}

    @property
    def public_key(self) -> str:
        return FAKE_PUBLIC_KEY

    async def send(self, device: PushDevice, message: PushMessage) -> PushResult:
        self.sent.append((device, message))
        if callable(self.answers):
            outcome = self.answers(device, message)
        else:
            outcome = self.answers.get(device.endpoint, PushOutcome.DELIVERED)
        status = {PushOutcome.DELIVERED: 201, PushOutcome.GONE: 410, PushOutcome.FAILED: 500}
        return PushResult(
            outcome=outcome,
            status_code=status[outcome],
            error=None if outcome is PushOutcome.DELIVERED else "refused",
        )
