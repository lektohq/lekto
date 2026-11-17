"""A subscription to the signals of one process's wakeup (`ports.wakeup.Signal`): what the
memory's and the SQL database's wakeups share (PM-12)."""

import asyncio
import contextlib
from collections.abc import Callable, Collection
from datetime import timedelta

from lekto.core.ports.wakeup import Channel


class InProcessSignal:
    """A flag that a signal of `channel` (of one of the job `kinds` on `JOBS`; None: all) sets,
    cleared by the wait that saw it. `live` asks the wakeup whether signals of other processes
    reach it at the moment."""

    def __init__(
        self, channel: Channel, kinds: Collection[str] | None, live: Callable[[], bool]
    ) -> None:
        self.channel = channel
        self.kinds = None if kinds is None else frozenset(kinds)
        self._live = live
        self._event = asyncio.Event()

    @property
    def live(self) -> bool:
        return self._live()

    def raise_for(self, channel: Channel, kind: str | None) -> None:
        if channel is self.channel and (self.kinds is None or kind in self.kinds):
            self._event.set()

    def raise_now(self) -> None:
        """Raise it whatever the channel (the SQL wakeup, after reconnecting)."""
        self._event.set()

    async def wait(self, timeout: timedelta) -> bool:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._event.wait(), timeout=timeout.total_seconds())
        if not self._event.is_set():
            return False
        self._event.clear()
        return True
