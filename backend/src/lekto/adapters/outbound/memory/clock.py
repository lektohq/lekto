from datetime import UTC, datetime, timedelta

from lekto.core.domain.validation import require_utc
from lekto.core.ports.clock import Clock


class ManualClock(Clock):
    """A clock that only moves when told to; starts at the given time or now."""

    def __init__(self, now: datetime | None = None) -> None:
        self._now = require_utc(now) if now is not None else datetime.now(UTC)

    def now(self) -> datetime:
        return self._now

    def set(self, now: datetime) -> None:
        self._now = require_utc(now)

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("a clock does not run backwards")
        self._now += delta
