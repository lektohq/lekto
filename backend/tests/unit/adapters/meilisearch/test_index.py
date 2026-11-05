"""The Meilisearch adapter against a simulated Meilisearch: what it sends, how it reads the
answers, how it treats failures. No network; the real service is covered by the integration
tests."""

import json
import unicodedata
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from typing import Any
from uuid import UUID

import httpx2
import pytest

from lekto.adapters.outbound.meilisearch import MeilisearchIndex
from lekto.adapters.outbound.meilisearch import index as index_module
from lekto.adapters.outbound.meilisearch.index import (
    HIGHLIGHT_END,
    HIGHLIGHT_START,
    filter_expression,
    segments,
)
from lekto.core.domain.errors import SearchIndexError, SearchUnavailableError
from lekto.core.domain.ids import ContactId, DocumentId, DocumentTypeId, SpaceId, TagId
from lekto.core.domain.periods import Period
from lekto.core.domain.pipeline import Lane
from lekto.core.domain.search import EmbeddingStamp, Segment, Visibility
from lekto.core.ports.repository import DocumentFilter
from lekto.core.ports.search_index import SearchQuery, TextMatch
from tests.builders import DEFAULT_SETTINGS, NOW, index_document, search_query

URL = "http://meilisearch:7700"


def uid(n: int) -> UUID:
    return UUID(int=n)


class SimulatedMeilisearch:
    """Answers like Meilisearch for the calls the adapter makes; records every request. The
    index exists with the wanted settings unless `settings` says otherwise."""

    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.task_status = "succeeded"
        self.task_error: dict[str, Any] = {}
        self.pending_polls = 0
        self.index_exists = True
        self.deleting_a_missing_index = False  # the task of a DELETE /indexes/... fails
        self.settings: dict[str, Any] | None = None  # None: the index has what is wanted
        self.search_answer: dict[str, Any] = {"hits": [], "estimatedTotalHits": 0}
        self.fail: Callable[[httpx2.Request], httpx2.Response | None] = lambda _: None

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        override = self.fail(request)
        if override is not None:
            return override
        path, method = request.url.path, request.method
        if path == "/tasks/7":
            return httpx2.Response(
                200,
                json={
                    "uid": 7,
                    "status": "failed",
                    "error": {"code": "index_not_found", "message": "Index not found"},
                },
            )
        if (
            method == "DELETE"
            and path.count("/") == 2
            and path.startswith("/indexes/")
            and self.deleting_a_missing_index
        ):
            return httpx2.Response(202, json={"taskUid": 7, "status": "enqueued"})
        if path.startswith("/tasks/"):
            if self.pending_polls > 0:
                self.pending_polls -= 1
                return httpx2.Response(200, json={"uid": 1, "status": "processing"})
            return httpx2.Response(
                200, json={"uid": 1, "status": self.task_status, "error": self.task_error}
            )
        if path.endswith("/settings") and method == "GET":
            if not self.index_exists:
                return httpx2.Response(
                    404, json={"code": "index_not_found", "message": "Index not found"}
                )
            return httpx2.Response(200, json=self.settings or {})
        if path.endswith("/search"):
            return httpx2.Response(200, json=self.search_answer)
        if path == "/health":
            return httpx2.Response(200, json={"status": "available"})
        if path == "/version":
            return httpx2.Response(200, json={"pkgVersion": "1.54.3"})
        if path.endswith("/documents/fetch"):
            return httpx2.Response(200, json={"results": [], "total": 0})
        return httpx2.Response(202, json={"taskUid": 1, "status": "enqueued"})

    def index(self, **arguments: Any) -> MeilisearchIndex:
        tuning: dict[str, Any] = {
            "locales": DEFAULT_SETTINGS.search_locales.split("+"),
            "timeout": DEFAULT_SETTINGS.meilisearch_timeout.total_seconds(),
            "task_timeout": DEFAULT_SETTINGS.meilisearch_task_timeout.total_seconds(),
            **arguments,
        }
        return MeilisearchIndex(
            url=URL, transport=httpx2.MockTransport(self.handle), index="lekto-test", **tuning
        )

    def calls(self, method: str, suffix: str = "") -> list[httpx2.Request]:
        return [
            request
            for request in self.requests
            if request.method == method and request.url.path.endswith(suffix)
        ]

    def body(self, request: httpx2.Request) -> Any:
        return json.loads(request.content)


def wanted_settings(sim: SimulatedMeilisearch, **arguments: Any) -> dict[str, Any]:
    return sim.index(**arguments)._settings()


async def test_a_missing_index_is_created_with_its_settings() -> None:
    sim = SimulatedMeilisearch()
    sim.index_exists = False
    index = sim.index(dimensions=3, locales=["deu"])
    await index.upsert([index_document()])
    (create,) = sim.calls("POST", "/indexes")
    assert sim.body(create) == {"uid": "lekto-test", "primaryKey": "id"}
    (patch,) = sim.calls("PATCH", "/settings")
    settings = sim.body(patch)
    assert settings["localizedAttributes"] == [{"locales": ["deu"], "attributePatterns": ["*"]}]
    assert settings["embedders"] == {"default": {"source": "userProvided", "dimensions": 3}}
    assert settings["pagination"] == {"maxTotalHits": 1000}
    assert "space_id" in settings["filterableAttributes"]
    assert "owner_id" not in settings["filterableAttributes"]
    assert settings["searchableAttributes"][0] == "title"
    assert {"und", "ich", "wie", "viel"} <= set(settings["stopWords"])
    assert settings["stopWords"] == sorted(settings["stopWords"])


def test_the_synonyms_are_those_of_the_languages() -> None:
    sim = SimulatedMeilisearch()
    assert sim.index(locales=["eng"])._settings()["synonyms"] == {}  # no use for others yet
    german = sim.index(locales=["deu"])._settings()["synonyms"]
    assert "Einmalzahlung" in german["Weihnachtsgeld"]
    assert "Weihnachtsgeld" in german["Einmalzahlung"]  # both ways
    assert "Weihnachtsgeld" not in german["Weihnachtsgeld"]
    assert all(others == sorted(others) for others in german.values())


async def test_synonyms_in_place_in_another_order_are_not_applied_again() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.settings["synonyms"] = {
        word: list(reversed(others)) for word, others in reversed(sim.settings["synonyms"].items())
    }
    await sim.index().upsert([index_document()])
    assert sim.calls("PATCH", "/settings") == []


async def test_the_point_of_an_ordinal_leaves_the_query() -> None:
    """Meilisearch splits a query at the point, so "13. Gehalt" would not meet its synonyms."""
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.search_answer = {"hits": [], "estimatedTotalHits": 1}
    visible = Visibility(frozenset({SpaceId(uid(100))}))
    for text, sent in (
        ("13. Gehalt", "13 Gehalt"),
        ("Rechnung vom 1. März", "Rechnung vom 1 März"),
        ("31.12.2025", "31.12.2025"),
        ("1.297,42 EUR", "1.297,42 EUR"),
        ("Seite 3.", "Seite 3."),
    ):
        sim.requests.clear()
        await sim.index().search(search_query(text, visible))
        assert [sim.body(call)["q"] for call in sim.calls("POST", "/search")] == [sent]


def test_the_stop_words_are_those_of_the_languages() -> None:
    sim = SimulatedMeilisearch()
    assert sim.index(locales=["eng"])._settings()["stopWords"] == []  # none measured yet
    german = sim.index(locales=["deu"])._settings()["stopWords"]
    assert sim.index(locales=["deu", "eng"])._settings()["stopWords"] == german


async def test_settings_that_are_in_place_are_not_applied_again() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=3)
    sim.settings["filterableAttributes"] = list(reversed(sim.settings["filterableAttributes"]))
    index = sim.index(dimensions=3)
    await index.upsert([index_document()])
    await index.upsert([index_document()])
    assert sim.calls("PATCH") == []
    assert sim.calls("GET", "/settings") != []
    assert len(sim.calls("GET", "/settings")) == 1  # checked once in a while


async def test_the_setup_is_checked_again_after_a_while(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(index_module, "monotonic", lambda: now[0])
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=3)
    index = sim.index(dimensions=3)
    await index.upsert([index_document()])
    now[0] += index_module.READY_FOR - 1
    await index.upsert([index_document()])
    assert len(sim.calls("GET", "/settings")) == 1

    sim.index_exists = False  # Meilisearch lost its data
    now[0] += 2
    await index.upsert([index_document()])
    assert len(sim.calls("GET", "/settings")) == 2
    assert len(sim.calls("POST", "/indexes")) == 1  # created again, with its settings
    assert len(sim.calls("PATCH", "/settings")) == 1


async def test_an_answer_that_the_index_is_gone_sets_it_up_again() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=3)
    index = sim.index(dimensions=3)
    await index.remove(DocumentId(uid(1)))
    gone = [True]

    def lose(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path.endswith("/search") and gone:
            gone.clear()
            body = {"code": "index_not_found", "message": "Index `lekto-test` not found."}
            return httpx2.Response(404, json=body)
        return None

    sim.fail = lose
    visibility = Visibility(frozenset({SpaceId(uid(5))}))
    with pytest.raises(SearchIndexError, match="index_not_found"):
        await index.search(search_query("x", visibility))
    settings_checks = len(sim.calls("GET", "/settings"))
    await index.search(search_query("x", visibility))
    assert len(sim.calls("GET", "/settings")) == settings_checks + 1


async def test_writes_name_the_primary_key() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    await sim.index().upsert([index_document()])
    (write,) = sim.calls("PUT", "/documents")
    assert write.url.params["primaryKey"] == "id"


async def test_the_marks_of_a_match_cannot_come_from_a_document() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    text = f"vor {HIGHLIGHT_START}falsch{HIGHLIGHT_END} nach"
    await sim.index().upsert([index_document(text=text)])
    (write,) = sim.calls("PUT", "/documents")
    assert sim.body(write)[0]["text"] == "vor falsch nach"


async def test_only_the_differing_settings_are_applied() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=3)
    sim.settings["embedders"] = {"default": {"source": "userProvided", "dimensions": 2}}
    await sim.index(dimensions=3).upsert([index_document()])
    (patch,) = sim.calls("PATCH", "/settings")
    assert sim.body(patch) == {
        "embedders": {"default": {"source": "userProvided", "dimensions": 3}}
    }


async def test_a_document_is_sent_whole() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)
    contact, kind, tag = ContactId(uid(1)), DocumentTypeId(uid(2)), TagId(uid(3))
    document = index_document(
        id=DocumentId(uid(10)),
        version=5,
        space_id=SpaceId(uid(12)),
        lane=None,
        title="Rechnung",
        text="Text",
        contact_id=contact,
        contact="Stadtwerke",
        document_type_id=kind,
        document_type="Rechnung",
        tag_ids=(tag,),
        tags=("Energie",),
        fields=("Betrag: 12.50 EUR",),
        document_date=date(2026, 3, 3),
        vectors=((0.5, 0.25), (1.0, 0.0)),
        embedding=EmbeddingStamp("bge-m3", "d1"),
    )
    plain = index_document(lane=Lane.YELLOW)
    await sim.index(dimensions=2).upsert([document, plain])
    (write,) = sim.calls("PUT", "/documents")
    first, second = sim.body(write)
    assert first["id"] == str(uid(10))
    assert (first["lane"], first["version"], first["contact_id"]) == ("processing", 5, str(uid(1)))
    assert first["tag_ids"] == [str(uid(3))]
    assert first["document_date"] == 1772496000  # 2026-03-03 00:00 UTC
    assert first["created_at"] == int(NOW.timestamp())
    assert first["_vectors"] == {"default": [[0.5, 0.25], [1.0, 0.0]]}
    assert (first["embedding_model"], first["embedding_digest"]) == ("bge-m3", "d1")
    # A document without vectors opts out of the embedder.
    assert second["_vectors"] == {"default": None}
    assert second["lane"] == "yellow"
    assert second["contact_id"] is None


async def test_kept_vectors_are_left_out_of_the_update() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)
    await sim.index(dimensions=2).upsert([index_document(vectors=None)])
    (write,) = sim.calls("PUT", "/documents")
    (sent,) = sim.body(write)
    assert not {"_vectors", "embedding_model", "embedding_digest"} & set(sent)


async def test_an_index_without_embedder_sends_no_vectors() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    await sim.index().upsert([index_document()])
    (write,) = sim.calls("PUT", "/documents")
    assert "_vectors" not in sim.body(write)[0]
    assert "embedders" not in sim.settings


async def test_vectors_of_the_wrong_length_never_leave_the_adapter() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=3)
    document = index_document(vectors=((1.0, 2.0),), embedding=EmbeddingStamp("m", "d"))
    with pytest.raises(SearchIndexError, match="needs 3"):
        await sim.index(dimensions=3).upsert([document])
    assert sim.calls("PUT", "/documents") == []


async def test_writes_wait_for_their_task() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.pending_polls = 3
    await sim.index().upsert([index_document()])
    assert len(sim.calls("GET", "/tasks/1")) == 4


async def test_a_failed_task_is_an_error_with_its_code() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.task_status = "failed"
    sim.task_error = {"code": "invalid_vector_dimensions", "message": "embedder `default` needs 3"}
    with pytest.raises(SearchIndexError, match="invalid_vector_dimensions: embedder `default`"):
        await sim.index().upsert([index_document()])
    with pytest.raises(SearchIndexError, match="failed"):
        await sim.index().remove(DocumentId(uid(1)))


async def test_a_task_that_takes_too_long_is_unavailability() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.pending_polls = 10_000
    with pytest.raises(SearchUnavailableError, match="did not finish within"):
        await sim.index(task_timeout=0.05).upsert([index_document()])


async def test_unreachable_and_slow_meilisearch_are_unavailability() -> None:
    sim = SimulatedMeilisearch()

    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused")

    def stall(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("slow")

    for failure, message in ((refuse, "cannot reach"), (stall, "did not answer in time")):
        sim.fail = failure
        with pytest.raises(SearchUnavailableError, match=message):
            await sim.index().upsert([index_document()])
        with pytest.raises(SearchUnavailableError, match=message):
            await sim.index().check()


async def test_server_errors_are_unavailability_and_client_errors_are_not() -> None:
    sim = SimulatedMeilisearch()
    sim.fail = lambda _: httpx2.Response(503, text="busy")
    with pytest.raises(SearchUnavailableError, match="HTTP 503"):
        await sim.index().search(_query())
    sim.fail = lambda _: httpx2.Response(
        401, json={"code": "invalid_api_key", "message": "The provided API key is invalid."}
    )
    with pytest.raises(SearchIndexError, match="invalid_api_key") as failure:
        await sim.index().search(_query())
    assert not isinstance(failure.value, SearchUnavailableError)


async def test_check_looks_at_health_and_key() -> None:
    sim = SimulatedMeilisearch()
    await sim.index().check()
    assert [request.url.path for request in sim.requests] == ["/health", "/version"]
    sim.fail = lambda request: (
        httpx2.Response(200, json={"status": "unhealthy"})
        if request.url.path == "/health"
        else None
    )
    with pytest.raises(SearchUnavailableError):
        await sim.index().check()


async def test_state_of_a_missing_document() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.fail = lambda request: (
        httpx2.Response(404, json={"code": "document_not_found", "message": "not found"})
        if "/documents/" in request.url.path
        else None
    )
    assert await sim.index().state(DocumentId(uid(1))) is None


async def test_a_search_that_finds_nothing_by_the_rarest_words_asks_again_by_the_first() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)  # and the search finds nothing
    result = await sim.index().search(_query())
    assert [sim.body(call)["matchingStrategy"] for call in sim.calls("POST", "/search")] == [
        "frequency",
        "last",
    ]
    assert result.hits == []
    # A later page of a search with hits keeps the strategy, even when it is empty.
    sim.requests.clear()
    sim.search_answer = {"hits": [], "estimatedTotalHits": 25}
    await sim.index().search(_query(offset=40))
    assert [sim.body(call)["matchingStrategy"] for call in sim.calls("POST", "/search")] == [
        "frequency"
    ]


async def test_the_stop_words_as_meilisearch_keeps_them_are_in_place() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.settings["stopWords"] = sorted(
        unicodedata.normalize("NFD", word) for word in sim.settings["stopWords"]
    )
    await sim.index().upsert([index_document()])
    assert sim.calls("PATCH", "/settings") == []


async def test_the_matches_of_a_document_ask_the_query_and_each_word_alone() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.search_answer = {
        "hits": [
            {
                "id": str(uid(1)),
                "text": "Größe: Gehalt",
                "_matchesPosition": {"text": [{"start": 9, "length": 6}]},
            }
        ],
        "estimatedTotalHits": 1,
    }
    visible = Visibility(frozenset({SpaceId(uid(100))}))
    found = await sim.index().matches(DocumentId(uid(1)), "13. Gehalt Gehalt", visible)
    assert found == [TextMatch(7, 13)]  # bytes counted as characters, once
    bodies = [sim.body(call) for call in sim.calls("POST", "/search")]
    assert [body["q"] for body in bodies] == ["13 Gehalt Gehalt ", "13 ", "Gehalt "]
    assert all(body["filter"].startswith(f'id = "{uid(1)}" AND ') for body in bodies)
    assert all(body["attributesToSearchOn"] == ["text"] for body in bodies)


async def test_a_query_of_stop_words_alone_finds_nothing_without_asking() -> None:
    """Meilisearch would answer it with every document, as if nothing were asked."""
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    visible = Visibility(frozenset({SpaceId(uid(100))}))
    for text in ("und", "Wie viel ich?", "Für ", "* (("):
        result = await sim.index(locales=["deu"]).search(search_query(text, visible))
        assert (result.hits, result.estimated_total) == ([], 0), text
        assert await sim.index().matches(DocumentId(uid(1)), text, visible) == [], text
    assert sim.calls("POST", "/search") == []
    await sim.index(locales=["deu"]).search(search_query("und Strom", visible))
    assert {sim.body(call)["q"] for call in sim.calls("POST", "/search")} == {"und Strom"}
    # Without the language's stop words they are words like any other.
    sim.requests.clear()
    await sim.index(locales=["eng"]).search(search_query("und", visible))
    assert {sim.body(call)["q"] for call in sim.calls("POST", "/search")} == {"und"}


async def test_with_the_meaning_one_word_finds_its_documents_first_above_the_floor() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)

    def hit(n: int, score: float) -> dict[str, Any]:
        return {"id": str(uid(n)), "version": 1, "_rankingScore": score}

    words = {"hits": [hit(2, 0.3)], "estimatedTotalHits": 1}
    mixed = {"hits": [hit(1, 0.8), hit(3, 0.6), hit(2, 0.5)], "estimatedTotalHits": 3}
    sim.fail = lambda request: (
        httpx2.Response(200, json=mixed if b'"hybrid"' in request.content else words)
        if request.url.path.endswith("/search")
        else None
    )
    index = sim.index(dimensions=2)
    query = _query(vector=(0.5, 0.5), semantic_ratio=0.5, meaning_min_score=0.7)
    result = await index.search(query)
    # The word's document first; the meaning's below the floor left out.
    assert [hit.id for hit in result.hits] == [uid(2), uid(1)]
    assert (result.word_total, result.estimated_total, result.semantic) == (1, 2, True)
    bodies = [sim.body(call) for call in sim.calls("POST", "/search")]
    assert [(body["offset"], body["limit"], "hybrid" in body) for body in bodies] == [
        (0, 200, False),
        (0, 200, True),
    ]
    assert bodies[1]["vector"] == [0.5, 0.5]
    assert bodies[1]["hybrid"] == {"embedder": "default", "semanticRatio": 0.5}
    # Pages are cut from that order.
    second = await index.search(replace(query, offset=1, limit=1))
    assert [hit.id for hit in second.hits] == [uid(1)]
    # More than one word: the order of the meaning and the words as Meilisearch has it.
    two = await index.search(replace(query, text="Urlaubsgeld Juni", meaning_min_score=None))
    assert [hit.id for hit in two.hits] == [uid(1), uid(3), uid(2)]


async def test_the_floor_of_the_meaning_keeps_the_words_hits_beyond_the_depth() -> None:
    """Where the floor cuts a candidate, the meaning's documents beyond the depth lie below it
    too, but the words' hits beyond are still counted, so that the pages reach them."""
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)

    def hit(n: int, score: float) -> dict[str, Any]:
        return {"id": str(uid(n)), "version": 1, "_rankingScore": score}

    # The 200 candidates: 150 by the meaning above the floor, 20 below it, 30 hits of the words.
    mixed = {
        "hits": [hit(n, 0.9) for n in range(1000, 1150)]
        + [hit(n, 0.5) for n in range(1150, 1170)]
        + [hit(n, 0.3) for n in range(1, 31)],
        "estimatedTotalHits": 5000,
    }
    words = {"hits": [hit(n, 0.3) for n in range(1, 201)], "estimatedTotalHits": 300}
    sim.fail = lambda request: (
        httpx2.Response(200, json=mixed if b'"hybrid"' in request.content else words)
        if request.url.path.endswith("/search")
        else None
    )
    query = replace(
        _query(vector=(0.5, 0.5), semantic_ratio=0.5, meaning_min_score=0.7, limit=10),
        text="Urlaubsgeld Juni",
    )
    result = await sim.index(dimensions=2).search(query)
    assert len(result.hits) == 10 and result.word_total == 300
    # 180 here (150 of the meaning, 30 of the words), 170 known hits of the words beyond the
    # candidates and 100 the words find beyond their page; the 20 below the floor are gone.
    assert result.estimated_total == 180 + 170 + 100


async def test_the_search_request_and_its_answer() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)
    sim.search_answer = {
        "hits": [
            {
                "id": str(uid(1)),
                "version": 3,
                "_rankingScore": 0.75,
                "_formatted": {
                    "id": str(uid(1)),
                    "text": f"…die {HIGHLIGHT_START}Zahlung{HIGHLIGHT_END} ist offen",
                },
            },
            {"id": str(uid(2)), "version": 1},
        ],
        "estimatedTotalHits": 40,
    }
    result = await sim.index(dimensions=2).search(_query(offset=20, limit=10))
    (search,) = sim.calls("POST", "/search")
    body = sim.body(search)
    assert (body["q"], body["offset"], body["limit"]) == ("Zahlung", 20, 10)
    assert body["matchingStrategy"] == "frequency"
    assert "vector" not in body and "hybrid" not in body
    assert body["attributesToCrop"] == ["text"]
    assert body["highlightPreTag"] == HIGHLIGHT_START
    assert not result.semantic
    assert result.estimated_total == 40
    first, second = result.hits
    assert (first.id, first.version, first.score) == (uid(1), 3, 0.75)
    assert first.snippet == (
        Segment("…die "),
        Segment("Zahlung", match=True),
        Segment(" ist offen"),
    )
    assert (second.score, second.snippet) == (None, ())


async def test_an_index_that_was_created_without_settings_is_set_up_for_the_search() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    refused = [True]

    def lost(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.path.endswith("/search") and refused:
            refused.pop()
            error = {"code": "invalid_search_filter", "message": "not filterable"}
            return httpx2.Response(400, json=error)
        return None

    sim.fail = lost
    sim.search_answer = {"hits": [{"id": str(uid(1)), "version": 1}], "estimatedTotalHits": 1}
    index = sim.index()
    await index.upsert([index_document()])  # the index counts as set up now
    settings_checks = len(sim.calls("GET", "/settings"))
    result = await index.search(_query())
    assert [hit.id for hit in result.hits] == [uid(1)]
    assert len(sim.calls("POST", "/search")) == 2
    assert len(sim.calls("GET", "/settings")) == settings_checks + 1


async def test_a_search_without_vector_or_with_ratio_zero_is_plain_full_text() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim, dimensions=2)
    index = sim.index(dimensions=2)
    for query in (_query(), _query(vector=(1.0, 0.0), semantic_ratio=0.0)):
        assert not (await index.search(query)).semantic
    for request in sim.calls("POST", "/search"):
        assert "hybrid" not in sim.body(request)
        assert "vector" not in sim.body(request)


async def test_vectors_need_an_embedder() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    with pytest.raises(SearchIndexError, match="no embedder"):
        await sim.index().search(_query(vector=(1.0,)))


async def test_a_search_without_lanes_finds_nothing_and_asks_nothing() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    result = await sim.index().search(_query(filter=DocumentFilter(lanes=frozenset())))
    assert result.hits == []
    assert sim.calls("POST", "/search") == []


async def test_the_rebuild_swaps_and_removes_the_old_index() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    index = sim.index()
    build = await index.begin_rebuild()
    await build.add([index_document()])
    await build.finish()
    nodes = [
        (request.method, request.url.path)
        for request in sim.requests
        if request.url.path != "/tasks/1"
    ]
    assert ("DELETE", "/indexes/lekto-test-rebuild") in nodes
    assert ("PUT", "/indexes/lekto-test-rebuild/documents") in nodes
    swap = [request for request in sim.requests if request.url.path == "/swap-indexes"]
    assert sim.body(swap[0]) == [{"indexes": ["lekto-test", "lekto-test-rebuild"]}]
    assert nodes[-1] == ("DELETE", "/indexes/lekto-test-rebuild")
    assert nodes.index(("POST", "/swap-indexes")) < len(nodes) - 1


async def test_the_rebuild_goes_on_when_there_is_no_old_build_index() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.deleting_a_missing_index = True
    build = await sim.index().begin_rebuild()  # no error although there was nothing to delete
    await build.abort()


async def test_deleting_an_index_fails_on_other_errors() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.task_status, sim.task_error = "failed", {"code": "internal", "message": "disk full"}
    with pytest.raises(SearchIndexError, match="disk full"):
        await (await sim.index().begin_rebuild()).abort()


async def test_dropping_tries_both_indexes_even_if_the_first_fails() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.task_status, sim.task_error = "failed", {"code": "internal", "message": "disk full"}
    with pytest.raises(SearchIndexError, match="disk full"):
        await sim.index().drop()
    deleted = [request.url.path for request in sim.calls("DELETE")]
    assert "/indexes/lekto-test-rebuild" in deleted


async def test_dropping_removes_the_index_and_the_remains_of_a_rebuild() -> None:
    sim = SimulatedMeilisearch()
    sim.settings = wanted_settings(sim)
    sim.deleting_a_missing_index = True  # neither exists: nothing fails
    await sim.index().drop()
    deleted = [
        request.url.path for request in sim.calls("DELETE") if "/indexes/" in request.url.path
    ]
    assert deleted == ["/indexes/lekto-test", "/indexes/lekto-test-rebuild"]


# --- filters and segments --------------------------------------------------------------------


def _query(**fields: Any) -> SearchQuery:
    visibility = Visibility(frozenset({SpaceId(uid(100))}))
    return search_query("Zahlung", visibility, **fields)


def test_the_filter_for_a_user_without_spaces() -> None:
    nothing = Visibility(frozenset())
    assert filter_expression(nothing, DocumentFilter()) == f'(space_id = "{UUID(int=0)}")'
    assert filter_expression(_query().visibility, _query().filter) == (
        f'(space_id IN ["{uid(100)}"])'
    )


def test_the_filter_for_a_user_with_spaces_and_criteria() -> None:
    visibility = Visibility(
        frozenset({SpaceId(uid(100))}), frozenset({SpaceId(uid(2)), SpaceId(uid(1))})
    )
    query = search_query(
        "x",
        visibility,
        filter=DocumentFilter(
            contacts=frozenset({ContactId(uid(10)), ContactId(uid(3))}),
            document_types=frozenset({DocumentTypeId(uid(4))}),
            tags=(frozenset({TagId(uid(6)), TagId(uid(5))}), frozenset({TagId(uid(7))})),
            contact_groups=(frozenset({TagId(uid(8))}),),
            document_type_groups=(frozenset({TagId(uid(9))}),),
            spaces=frozenset({SpaceId(uid(1))}),
            lanes=frozenset({Lane.GREEN, None}),
            document_dates=Period.month(2026, 9),
        ),
    )
    assert filter_expression(query.visibility, query.filter) == (
        f'(space_id IN ["{uid(100)}"] OR (lane = "green" AND space_id IN '
        f'["{uid(1)}", "{uid(2)}"])) '
        f'AND contact_id IN ["{uid(3)}", "{uid(10)}"] AND document_type_id IN ["{uid(4)}"] '
        f'AND space_id IN ["{uid(1)}"] '
        f'AND tag_ids IN ["{uid(5)}", "{uid(6)}"] AND tag_ids IN ["{uid(7)}"] '
        f'AND contact_group_ids IN ["{uid(8)}"] AND document_type_group_ids IN ["{uid(9)}"] '
        "AND document_date 1788220800 TO 1790726400 "
        'AND lane IN ["green", "processing"]'
    )


def test_the_filter_of_a_search_over_everything() -> None:
    everything = Visibility(frozenset(), everything=True)
    assert filter_expression(everything, DocumentFilter()) is None
    query = search_query(
        "x", everything, filter=DocumentFilter(contacts=frozenset({ContactId(uid(3))}))
    )
    assert filter_expression(query.visibility, query.filter) == f'contact_id IN ["{uid(3)}"]'


def test_the_filter_for_confirmed_documents() -> None:
    """A document indexed before the attribute existed counts as not confirmed."""
    everything = Visibility(frozenset(), everything=True)
    assert filter_expression(everything, DocumentFilter(confirmed=True)) == "confirmed = true"
    assert filter_expression(everything, DocumentFilter(confirmed=False)) == (
        "NOT confirmed = true"
    )


def test_segments() -> None:
    mark = HIGHLIGHT_START
    end = HIGHLIGHT_END
    assert segments("") == ()
    assert segments("plain") == (Segment("plain"),)
    assert segments(f"{mark}all{end}") == (Segment("all", match=True),)
    assert segments(f"a {mark}b{end} c {mark}d{end}") == (
        Segment("a "),
        Segment("b", match=True),
        Segment(" c "),
        Segment("d", match=True),
    )
    assert segments(f"open {mark}never closed") == (
        Segment("open "),
        Segment("never closed", match=True),
    )
