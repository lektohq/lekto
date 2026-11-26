from datetime import UTC, datetime

from lekto.core.ports.clock import Clock


class SystemClock(Clock):
    """The real time, in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)
