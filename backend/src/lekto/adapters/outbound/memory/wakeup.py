"""In-process signals: a MemoryDatabase tells its wakeups what every commit queued."""

from collections.abc import Collection

from lekto.adapters.outbound.memory.database import MemoryDatabase
from lekto.adapters.outbound.signals import InProcessSignal
from lekto.core.ports.wakeup import Channel


class MemoryWakeup:
    """Signals of one in-memory database. Every process has its own database, so its signals
    reach every receiver there is: the subscriptions are `live`."""

    def __init__(self, database: MemoryDatabase) -> None:
        self._signals: list[InProcessSignal] = []
        self._closed = False
        database.listeners.append(self._signal)

    def subscribe(
        self, channel: Channel, *, kinds: Collection[str] | None = None
    ) -> InProcessSignal:
        if self._closed:
            raise RuntimeError("the wakeup is closed")
        signal = InProcessSignal(channel, kinds, live=lambda: True)
        self._signals.append(signal)
        return signal

    async def aclose(self) -> None:
        self._closed = True
        self._signals = []

    def _signal(self, channel: Channel, kind: str | None) -> None:
        for signal in self._signals:
            signal.raise_for(channel, kind)
