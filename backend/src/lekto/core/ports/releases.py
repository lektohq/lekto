"""Where Lekto learns of its releases (`.knowledge/open/update-notifier-fas.md`)."""

from typing import Protocol

from lekto.core.domain.releases import Release


class ReleaseFeedError(Exception):
    """The releases could not be read; the message says why, without anything secret."""


class ReleaseFeed(Protocol):
    """The published releases of Lekto. First adapter: the GitHub releases of `lektohq/lekto`
    over httpx2. Tells nothing about the instance that asks."""

    async def releases(self) -> list[Release]:
        """The published releases (drafts left out), in any order. ReleaseFeedError if they
        cannot be read."""
        ...
