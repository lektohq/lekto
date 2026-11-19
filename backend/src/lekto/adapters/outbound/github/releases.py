"""The releases of Lekto from GitHub's REST API (`.knowledge/open/update-notifier-fas.md`).

One unauthenticated GET of the newest page of releases of `lektohq/lekto`; GitHub sees the address
and the user agent (`Lekto/<version>`), nothing else. Drafts are not public, and a release without
a publication date is left out. The answer is bounded in size and time.
"""

import asyncio
import json
from datetime import datetime

import httpx2

from lekto.adapters.outbound.http_client import CONNECT_TIMEOUT, describe_failure
from lekto.core.domain.releases import Release
from lekto.core.ports.releases import ReleaseFeedError

URL = "https://api.github.com/repos/lektohq/lekto/releases?per_page=30"
TIMEOUT = 15.0
"""Seconds for the whole request."""
MAX_BYTES = 2_000_000
"""The largest answer read (a page of releases with their notes is far below)."""


class GitHubReleaseFeed:
    def __init__(
        self, *, user_agent: str, url: str = URL, transport: httpx2.AsyncBaseTransport | None = None
    ) -> None:
        """`transport` replaces the network in tests."""
        self._user_agent = user_agent
        self._url = url
        self._transport = transport

    async def releases(self) -> list[Release]:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            async with asyncio.timeout(TIMEOUT):
                async with httpx2.AsyncClient(
                    transport=self._transport,
                    follow_redirects=False,
                    trust_env=False,
                    timeout=httpx2.Timeout(TIMEOUT, connect=min(CONNECT_TIMEOUT, TIMEOUT)),
                ) as client:
                    response = await client.get(self._url, headers=headers)
                    body = response.content
        except (TimeoutError, httpx2.TimeoutException) as failure:
            raise ReleaseFeedError(f"no answer within {TIMEOUT:g} seconds") from failure
        except httpx2.HTTPError as failure:
            raise ReleaseFeedError(describe_failure(failure)) from failure
        if response.status_code != 200:
            raise ReleaseFeedError(f"GitHub answered {response.status_code}")
        if len(body) > MAX_BYTES:
            raise ReleaseFeedError("the answer is too large")
        try:
            items = json.loads(body)
        except ValueError as failure:
            raise ReleaseFeedError("the answer is not JSON") from failure
        if not isinstance(items, list):
            raise ReleaseFeedError("the answer is not a list of releases")
        return [release for item in items if (release := _release(item)) is not None]


def _release(item: object) -> Release | None:
    """A published release from one item of the answer; None for a draft or one that lacks a
    field."""
    if not isinstance(item, dict) or item.get("draft"):
        return None
    tag, published, url = item.get("tag_name"), item.get("published_at"), item.get("html_url")
    if not (isinstance(tag, str) and isinstance(published, str) and isinstance(url, str)):
        return None
    if not url.startswith("https://github.com/"):
        return None
    try:
        when = datetime.fromisoformat(published)
    except ValueError:
        return None
    if when.tzinfo is None:
        return None
    return Release(version=tag.removeprefix("v"), published_at=when, url=url)
