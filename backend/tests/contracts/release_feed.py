"""What every release feed does (`core/ports/releases.py`): the published releases, drafts left
out; ReleaseFeedError when they cannot be read."""

from datetime import UTC, datetime

import pytest

from lekto.core.domain.releases import Release
from lekto.core.ports.releases import ReleaseFeed, ReleaseFeedError

WHEN = datetime(2026, 11, 19, 12, tzinfo=UTC)
PUBLISHED = [
    Release(
        version="0.16.0",
        published_at=WHEN,
        url="https://github.com/lektohq/lekto/releases/tag/v0.16.0",
    ),
    Release(
        version="0.15.6",
        published_at=WHEN.replace(hour=10),
        url="https://github.com/lektohq/lekto/releases/tag/v0.15.6",
    ),
]


class ReleaseFeedContract:
    def feed(self, releases: list[Release], *, draft: str | None = None) -> ReleaseFeed:
        """A feed that holds `releases`, and a draft of the version `draft` beside them."""
        raise NotImplementedError

    def failing(self) -> ReleaseFeed:
        """A feed whose releases cannot be read."""
        raise NotImplementedError

    async def test_the_published_releases_without_drafts(self) -> None:
        found = await self.feed(PUBLISHED, draft="0.17.0").releases()
        assert sorted(found, key=lambda release: release.version) == sorted(
            PUBLISHED, key=lambda release: release.version
        )

    async def test_none_is_none(self) -> None:
        assert await self.feed([]).releases() == []

    async def test_a_failure_is_a_release_feed_error(self) -> None:
        with pytest.raises(ReleaseFeedError):
            await self.failing().releases()
