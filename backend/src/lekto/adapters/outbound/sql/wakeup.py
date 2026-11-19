"""Signals of a SQL database (`Wakeup`).

On Postgres a connection of its own, outside SQLAlchemy's pool, listens on the channels of
`NOTIFY_CHANNELS` (`LISTEN` needs a session: through a connection pooler in transaction
pooling the notifications never arrive, and the receivers poll at their safety net instead).
When the connection breaks, the listener connects again, waiting longer after each failure
in a row, and then raises every subscription once: whatever was committed meanwhile is
looked at. Every `KEEPALIVE` it runs `SELECT 1` on the listening connection (one transaction
a minute), so a connection that died silently is noticed: one that does not answer within
`KEEPALIVE_TIMEOUT` counts as lost. While it is not listening the subscriptions are not `live`.

On SQLite there is nothing to listen on: a commit of this process signals its subscriptions
directly (`Database.listeners`), and they are never `live`, so receivers poll for the
commits of other processes.
"""

import asyncio
import contextlib
import logging
from collections.abc import Collection
from datetime import timedelta
from typing import Any

import asyncpg

from lekto.adapters.outbound.signals import InProcessSignal
from lekto.adapters.outbound.sql.database import Database
from lekto.adapters.outbound.sql.transaction import NOTIFY_CHANNELS
from lekto.core.ports.wakeup import Channel

log = logging.getLogger(__name__)

KEEPALIVE = timedelta(seconds=60)
KEEPALIVE_TIMEOUT = timedelta(seconds=10)
RECONNECT_DELAY = timedelta(seconds=1)
RECONNECT_MAX_DELAY = timedelta(seconds=30)

_CHANNELS = {name: channel for channel, name in NOTIFY_CHANNELS.items()}


class SqlWakeup:
    def __init__(self, database: Database) -> None:
        self._db = database
        self._signals: list[InProcessSignal] = []
        self._listener: asyncio.Task[None] | None = None
        self._listening = False
        self._failures = 0  # breaks of the connection in a row, since it last listened
        self._closed = False
        if database.is_sqlite:
            database.listeners.append(self._signal)

    @property
    def listening(self) -> bool:
        """Whether a connection listens for the notifications of Postgres right now."""
        return self._listening

    def subscribe(
        self, channel: Channel, *, kinds: Collection[str] | None = None
    ) -> InProcessSignal:
        if self._closed:
            raise RuntimeError("the wakeup is closed")
        signal = InProcessSignal(channel, kinds, live=lambda: self.listening)
        self._signals.append(signal)
        if not self._db.is_sqlite and self._listener is None:
            self._listener = asyncio.create_task(self._listen_forever(), name="lekto-listener")
        return signal

    async def aclose(self) -> None:
        self._closed = True
        self._signals = []
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None

    def _signal(self, channel: Channel, kind: str | None) -> None:
        for signal in self._signals:
            signal.raise_for(channel, kind)

    async def _listen_forever(self) -> None:
        while True:
            try:
                await self._listen()
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(self._failed().total_seconds())

    def _failed(self) -> timedelta:
        """One more break in a row: how long to wait before connecting again, longer after
        each (`_listen` counts anew once it listens; SQ-02)."""
        self._failures += 1
        delay = min(RECONNECT_DELAY * (1 << min(self._failures, 10)), RECONNECT_MAX_DELAY)
        log.warning(
            "listening for notifications failed; connecting again",
            extra={"failures": self._failures, "delay": delay.total_seconds()},
            exc_info=True,
        )
        return delay

    async def _listen(self) -> None:
        """Listen on one connection until it ends; raises when it breaks."""
        lost = asyncio.Event()
        loop = asyncio.get_running_loop()

        def on_notification(_connection: Any, _pid: int, channel: str, payload: str) -> None:
            self._signal(_CHANNELS[channel], payload or None)

        def on_termination(_connection: Any) -> None:
            loop.call_soon(lost.set)

        connection = await self._db.connect_raw()
        try:
            for name in NOTIFY_CHANNELS.values():
                await connection.add_listener(name, on_notification)
            connection.add_termination_listener(on_termination)
            self._listening = True
            self._failures = 0  # it listens: the next break is a first one again
            log.info("listening for notifications")
            # Connected: whatever was committed while not listening is looked at once.
            for signal in self._signals:
                signal.raise_now()
            while not lost.is_set():
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(lost.wait(), timeout=KEEPALIVE.total_seconds())
                if not lost.is_set():
                    await asyncio.wait_for(
                        connection.execute("SELECT 1"), timeout=KEEPALIVE_TIMEOUT.total_seconds()
                    )
            raise asyncpg.ConnectionDoesNotExistError("the listening connection ended")
        finally:
            self._listening = False
            with contextlib.suppress(Exception):
                await asyncio.wait_for(connection.close(), timeout=5)
