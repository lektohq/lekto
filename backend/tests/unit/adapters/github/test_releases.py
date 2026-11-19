"""The releases of Lekto from GitHub's REST API, against a stand-in for GitHub."""

import json

import httpx2
import pytest

from lekto.adapters.outbound.github.releases import MAX_BYTES, URL, GitHubReleaseFeed
from lekto.core.domain.releases import Release
from lekto.core.ports.releases import ReleaseFeed, ReleaseFeedError
from tests.contracts.release_feed import PUBLISHED, ReleaseFeedContract


def _item(release: Release, *, draft: bool = False) -> dict[str, object]:
    return {
        "tag_name": f"v{release.version}",
        "published_at": release.published_at.isoformat().replace("+00:00", "Z"),
        "html_url": release.url,
        "draft": draft,
        "prerelease": False,
        "body": "## Notes",
    }


def _answering(
    status: int, body: bytes, seen: list[httpx2.Request] | None = None
) -> GitHubReleaseFeed:
    def handle(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(status, content=body)

    return GitHubReleaseFeed(user_agent="Lekto/0.15.6", transport=httpx2.MockTransport(handle))


class TestGitHubReleaseFeed(ReleaseFeedContract):
    def feed(self, releases: list[Release], *, draft: str | None = None) -> ReleaseFeed:
        items = [_item(release) for release in releases]
        if draft is not None:
            items.append(
                _item(
                    Release(
                        version=draft,
                        published_at=PUBLISHED[0].published_at,
                        url="https://github.com/x",
                    ),
                    draft=True,
                )
            )
        return _answering(200, json.dumps(items).encode())

    def failing(self) -> ReleaseFeed:
        return _answering(503, b"")


async def test_it_asks_github_as_lekto_and_tells_nothing_else() -> None:
    seen: list[httpx2.Request] = []
    await _answering(200, b"[]", seen).releases()
    (request,) = seen
    assert str(request.url) == URL
    assert request.method == "GET"
    assert request.headers["user-agent"] == "Lekto/0.15.6"
    assert "authorization" not in request.headers
    assert request.content == b""


@pytest.mark.parametrize(
    ("status", "body", "why"),
    [
        (403, b"rate limit", "GitHub answered 403"),
        (200, b"<html>", "not JSON"),
        (200, b'{"message": "x"}', "not a list"),
        (200, b"[" + b" " * MAX_BYTES + b"]", "too large"),
    ],
)
async def test_an_answer_it_cannot_use_is_an_error(status: int, body: bytes, why: str) -> None:
    with pytest.raises(ReleaseFeedError, match=why):
        await _answering(status, body).releases()


async def test_items_it_cannot_read_are_left_out() -> None:
    good = _item(PUBLISHED[0])
    items = [
        good,
        {**good, "published_at": None},
        {**good, "html_url": "https://evil.example/x"},
        {**good, "published_at": "2026-11-19T12:00:00"},
        "nonsense",
    ]
    assert await _answering(200, json.dumps(items).encode()).releases() == [PUBLISHED[0]]


async def test_no_network_is_an_error() -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("down", request=request)

    feed = GitHubReleaseFeed(user_agent="Lekto/0.15.6", transport=httpx2.MockTransport(fail))
    with pytest.raises(ReleaseFeedError, match="cannot connect"):
        await feed.releases()
