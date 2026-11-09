"""Reading Paperless: only what is asked for (review 0.12.2, O-10)."""

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
