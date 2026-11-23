"""Reading Paperless: only what is asked for (review 0.12.2, O-10)."""

from pathlib import Path

import httpx2

from lekto_migration import fake_paperless
from lekto_migration.paperless import Paperless
from tests.conftest import Setup


async def test_the_texts_of_a_few_documents_are_asked_for_by_their_ids(setup: Setup) -> None:
    every = [int(item["id"]) for item in setup.archive.documents]
    assert len(every) > 1
    wanted = {every[0]}
    setup.archive.page_size_limit = 1  # page by page, the archive would take a request each
    source = Paperless(
        "http://paperless", fake_paperless.TOKEN, transport=setup.paperless.transport()
    )
    try:
        texts = await source.contents(wanted)
    finally:
        await source.close()
    assert set(texts) == wanted
    # One request, for the one document: not the archive page by page.
    lists = [path for method, path in setup.paperless.requests if path == "/api/documents/"]
    assert len(lists) == 1


async def test_too_many_requests_waits_as_paperless_asks_and_tries_again(
    setup: Setup, tmp_path: Path
) -> None:
    """A 429 passes like a server error, after `Retry-After` (as Lekto's; MI-K04)."""
    inner = setup.paperless.transport()
    refused: list[str] = []

    async def handle(request: httpx2.Request) -> httpx2.Response:
        if request.url.path not in refused:
            refused.append(request.url.path)
            return httpx2.Response(429, headers={"Retry-After": "7"})
        return await inner.handle_async_request(request)

    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    document = int(setup.archive.documents[0]["id"])
    source = Paperless(
        "http://paperless",
        fake_paperless.TOKEN,
        transport=httpx2.MockTransport(handle),
        sleep=sleep,
    )
    try:
        assert await source.count("/api/tags/") >= 0
        download = await source.download_original(document, tmp_path / "file")
    finally:
        await source.close()
    assert download.size > 0
    assert slept == [7.0, 7.0]
