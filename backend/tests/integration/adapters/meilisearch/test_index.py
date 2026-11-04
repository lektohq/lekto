"""The Meilisearch adapter against a real Meilisearch (the devcontainer service)."""

import secrets

import httpx2

from lekto.adapters.outbound.meilisearch import MeilisearchIndex
from lekto.adapters.outbound.meilisearch.languages import synonym_groups
from lekto.composition.settings import Settings
from lekto.core.domain.ids import SpaceId, new_id
from lekto.core.domain.search import IndexDocument, Visibility
from tests.builders import index_document, search_query
from tests.contracts.search_index import SearchIndexContract
from tests.integration.services import drop, new_index


class TestMeilisearchIndex(SearchIndexContract):
    pass


async def test_compound_words_are_split(search_index: MeilisearchIndex) -> None:
    space = SpaceId(new_id())
    document = index_document(space_id=space, title="Stromrechnung", text="Ihre Jahresabrechnung")
    await search_index.upsert([document])
    for word in ("Strom", "rechnung", "Abrechnung"):
        result = await search_index.search(search_query(word, Visibility(frozenset({space}))))
        assert [hit.id for hit in result.hits] == [document.id], word


async def test_the_rare_word_decides_and_stop_words_do_not(search_index: MeilisearchIndex) -> None:
    """The most frequent words of a query go first, so the rare word that decides stays, also
    at its end; the stop words count for nothing; a query that this leaves without hits is asked
    again by its first word."""
    space = SpaceId(new_id())
    visible = Visibility(frozenset({space}))
    sofa = index_document(space_id=space, title="Rechnung", text="Rechnung über ein Sofa")
    year = index_document(space_id=space, title="Rechnung für das neue Jahr", text="Rechnung")
    tax = index_document(space_id=space, title="Hundesteuer 2026", text="Wie viel: 120 Euro.")
    common = [
        index_document(space_id=space, title="Umzug", text="Unsere neue Adresse"),
        index_document(space_id=space, title="Preise", text="Neue Preise ab Mai"),
    ]
    await search_index.upsert([sofa, year, tax, *common])
    result = await search_index.search(search_query("Rechnung für das neue Sofa", visible))
    assert result.hits[0].id == sofa.id
    assert (await search_index.search(search_query("wie viel ich", visible))).hits == []
    # Two rare words in two documents: by the most frequent first nothing is left.
    result = await search_index.search(search_query("Hundesteuer Sofa", visible))
    assert [hit.id for hit in result.hits] == [tax.id]


async def test_every_word_of_a_synonym_group_finds_the_others(
    search_index: MeilisearchIndex,
) -> None:
    """The list is only worth what works: each word, as a query, finds a document in each of
    the group's words, also where the splitting of compounds is in the way."""
    groups = synonym_groups("deu")
    documents: dict[str, IndexDocument] = {}
    spaces = []
    for group in groups:
        space = SpaceId(new_id())
        spaces.append(space)
        for word in group:
            documents[word] = index_document(space_id=space, title="Brief", text=f"Ihr {word}")
    await search_index.upsert(list(documents.values()))
    missed = []
    for space, group in zip(spaces, groups, strict=True):
        visible = Visibility(frozenset({space}))
        for word in group:
            result = await search_index.search(search_query(word, visible, limit=20))
            found = {hit.id for hit in result.hits}
            missed += [f"{word} -> {other}" for other in group if documents[other].id not in found]
    assert missed == [], "\n".join(missed)


async def test_the_settings_are_applied_once(meilisearch_settings: Settings) -> None:
    """A second adapter on the same index finds the settings in place and changes nothing, so a
    restart does not index again."""
    name = f"lekto-test-{secrets.token_hex(6)}"
    first, again = new_index(meilisearch_settings, name), new_index(meilisearch_settings, name)
    try:
        await first.check()
        await first.upsert([index_document()])
        before = await _settings_tasks(meilisearch_settings, name)
        await again.upsert([index_document()])
        assert await _settings_tasks(meilisearch_settings, name) == before
    finally:
        await first.aclose()
        await again.aclose()
        await drop(meilisearch_settings, name)
    assert before >= 1


async def _settings_tasks(settings: Settings, name: str) -> int:
    assert settings.meilisearch_url is not None
    key = settings.meilisearch_api_key
    headers = {} if key is None else {"Authorization": f"Bearer {key.get_secret_value()}"}
    async with httpx2.AsyncClient(
        base_url=str(settings.meilisearch_url), headers=headers
    ) as client:
        response = await client.get("/tasks", params={"indexUids": name, "types": "settingsUpdate"})
    return int(response.json()["total"])


async def test_an_index_without_embedder_takes_documents_without_vectors(
    meilisearch_settings: Settings,
) -> None:
    name = f"lekto-test-{secrets.token_hex(6)}"
    index = new_index(meilisearch_settings, name, dimensions=None)
    try:
        space = SpaceId(new_id())
        document = index_document(space_id=space, title="Mahnung")
        await index.upsert([document])
        result = await index.search(search_query("Mahnung", Visibility(frozenset({space}))))
        assert [hit.id for hit in result.hits] == [document.id]
    finally:
        await index.aclose()
        await drop(meilisearch_settings, name)
