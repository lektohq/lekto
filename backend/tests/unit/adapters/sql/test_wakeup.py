"""The listener for the notifications of Postgres: how long it waits before connecting again
(SQ-02)."""

import contextlib
from typing import Any

from lekto.adapters.outbound.sql.wakeup import RECONNECT_DELAY, SqlWakeup


class _Connection:
    """A connection that ends as soon as it listens."""

    async def add_listener(self, channel: str, callback: Any) -> None:
        pass

    def add_termination_listener(self, callback: Any) -> None:
        callback(self)

    async def execute(self, query: str) -> None:
        pass

    async def close(self) -> None:
        pass


class _Postgres:
    is_sqlite = False

    async def connect_raw(self) -> _Connection:
        return _Connection()


async def test_a_break_after_listening_again_is_a_first_one() -> None:
    """The count of breaks in a row starts anew once it listens: a break days later waits the
    first delay, not the longest."""
    wakeup = SqlWakeup(_Postgres())  # type: ignore[arg-type]
    for _ in range(6):
        wakeup._failed()  # six breaks in a row, the connection never listening between them
    assert wakeup._failed() == RECONNECT_DELAY * 30  # the longest
    with contextlib.suppress(Exception):
        await wakeup._listen()  # listens, then breaks
    assert wakeup._failed() == RECONNECT_DELAY * 2
