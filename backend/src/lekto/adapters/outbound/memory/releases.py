"""Releases from a list, for tests and the memory container."""

from lekto.core.domain.releases import Release
from lekto.core.ports.releases import ReleaseFeed, ReleaseFeedError


class FakeReleaseFeed(ReleaseFeed):
    """Answers with `releases`, or raises `error` while it is set; counts the questions."""

    def __init__(self, releases: list[Release] | None = None) -> None:
        self.releases_given = list(releases or [])
        self.error: str | None = None
        self.asked = 0

    async def releases(self) -> list[Release]:
        self.asked += 1
        if self.error is not None:
            raise ReleaseFeedError(self.error)
        return list(self.releases_given)
