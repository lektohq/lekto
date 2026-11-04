"""Searching documents: full text and, with embeddings, meaning, in one call.

The index is derived data and lags a little behind the database, so it is a pre-selection only:
the rights are in the query to the index (`Visibility`), and every hit is checked against the
database once more before it is returned (`document_access`), together with the filter. A
share that was withdrawn or a lane that changed since the index was written costs a hit, never
a leak. That is why a page can hold fewer items than `limit`; `next_offset` counts index hits,
so paging over the pages still reaches every hit.

A search says how it searched (`SearchPage.mode`): by words and meaning, or by words alone, and
then why (`SearchPage.reason`): no embeddings, the service down, too slow or answering with a
vector of another length. The words are the fallback that always stays. A query whose meaning
was not ready in time goes on being embedded in the background; its vector is kept a while for
the same query, and the searcher learns when it is ready (`SearchMeaningReady`, handed to the
listeners, `listen`). Before a search, `warm` has the model of the embeddings loaded.
"""

import asyncio
import logging
import re
from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from lekto.core.domain.document_facts import fact_tokens
from lekto.core.domain.documents import Document
from lekto.core.domain.errors import (
    EmbeddingsError,
    NotFoundError,
    SearchUnavailableError,
    ValidationError,
)
from lekto.core.domain.events import SearchMeaningReady
from lekto.core.domain.ids import DocumentId, SpaceId, UserId
from lekto.core.domain.occurrences import Occurrence
from lekto.core.domain.permissions import Reach, document_access, reach_access
from lekto.core.domain.reasons import Action, Reason, ReasonCode, because
from lekto.core.domain.search import Segment, Visibility
from lekto.core.domain.spaces import Space, SpaceRole
from lekto.core.domain.text_places import TextPlaces
from lekto.core.ports.clock import Clock
from lekto.core.ports.embeddings import Embeddings
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.repository import DocumentFilter, DocumentOrder, SortKey
from lekto.core.ports.search_index import (
    MAX_HITS,
    MAX_LIMIT,
    SEARCH_PAGE,
    SearchIndex,
    SearchQuery,
    TextMatch,
    check_search,
)
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from lekto.core.services._access import (
    check_fact_filter,
    load_actor,
    load_lister,
    readable_document,
)
from lekto.core.services._tags import expanded, group_lookup, matches
from lekto.core.services.inbox import in_inbox
from lekto.core.services.objects import load_layout, load_text

log = logging.getLogger(__name__)

KEEP_VECTORS = timedelta(minutes=10)
"""How long the vector of a query is kept for the same query again."""
WARM_EVERY = timedelta(minutes=1)
"""At most one embedding to warm the model in this time (`SearchService.warm`)."""
_KEEP_AT_MOST = 200  # vectors of queries kept
_PENDING_AT_MOST = 8  # queries embedded at once; beyond, a slow one is given up
_WARM_TEXT = "Dokument"
SHORTEST_PLACE = 3
"""Characters a place of a search's words has at least, unless a word asked for is that short:
Meilisearch also names the leftovers of its splitting ("en" of "Weihnachten")."""
_WORD = re.compile(r"\w+")


@dataclass(frozen=True, kw_only=True)
class SearchPolicy:
    """Configuration: the composition sets it from the settings, whose defaults are the one
    source."""

    semantic_ratio: float  # weight of the meaning against the words, 0 to 1
    embed_timeout: timedelta  # for the query; then plain full text
    query_prefix: str = ""  # put before the query, for models that ask for it
    dimensions: int | None = None  # the length of the vectors; a query of another goes by words
    # A document found by the meaning alone below this score is left out; none: every one.
    meaning_min_score: float | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.semantic_ratio <= 1:
            raise ValueError("semantic_ratio must be between 0 and 1")
        if self.meaning_min_score is not None and not 0 <= self.meaning_min_score <= 1:
            raise ValueError("meaning_min_score must be between 0 and 1")


@dataclass(frozen=True)
class SearchItem:
    document: Document
    access: SpaceRole  # of the caller
    score: float | None
    snippet: tuple[Segment, ...]
    in_inbox: bool = False  # it stands open in the caller's inbox (`inbox.in_inbox`)


class SearchMode(StrEnum):
    HYBRID = "hybrid"  # words and meaning
    WORDS = "words"  # words alone


@dataclass(frozen=True)
class SearchPage:
    items: list[SearchItem]  # best first; may be fewer than asked for
    estimated_total: int  # of the hits, as far as the caller may see them; not exact
    next_offset: int | None  # where the next page starts; None after the last one
    mode: SearchMode
    reason: Reason | None = None  # why by words alone, where the meaning was to take part
    meaning_pending: bool = False  # the meaning is still being made: `SearchMeaningReady` follows
    word_total: int = 0  # of the hits of the words; those beyond were found by the meaning

    @property
    def semantic(self) -> bool:
        """Whether the meaning took part."""
        return self.mode is SearchMode.HYBRID


@dataclass(frozen=True)
class SearchPlaces:
    """Where the words of a search stand in a document: how many places its text has (none:
    found by the meaning alone, or not at all), and where its pages show them, in the order of
    the text, the best `own` (the line with the most of the words, the first of them)."""

    matched: int
    occurrences: tuple[Occurrence, ...] = ()


@dataclass(frozen=True)
class _Meaning:
    """The vector of a query, or why there is none, and whether it is still being made."""

    vector: tuple[float, ...] | None
    reason: Reason | None = None
    pending: bool = False


class _OtherLengthError(Exception):
    def __init__(self, got: int, wanted: int) -> None:
        super().__init__(f"the query vector has {got} numbers, not {wanted}")
        self.got, self.wanted = got, wanted


class _UtcNow:
    def now(self) -> datetime:
        return datetime.now(UTC)


class SearchService:
    def __init__(
        self,
        uow: UnitOfWorkFactory,
        index: SearchIndex,
        policy: SearchPolicy,
        embeddings: Embeddings | None = None,
        clock: Clock | None = None,
        store: ObjectStore | None = None,
    ) -> None:
        """`store`: where the texts and the words of the pages are, for `places`; without it
        they name no places on the pages."""
        self._uow = uow
        self._store = store
        self._index = index
        self._embeddings = embeddings
        self._policy = policy
        self._clock: Clock = clock or _UtcNow()
        self._vectors: dict[str, tuple[datetime, tuple[float, ...]]] = {}
        self._pending: dict[str, asyncio.Task[tuple[float, ...]]] = {}
        self._waiting: dict[str, set[tuple[UserId, str]]] = defaultdict(set)
        self._listeners: list[Callable[[SearchMeaningReady], None]] = []
        self._warmed_at: datetime | None = None

    @property
    def meaning(self) -> bool:
        """Whether the search takes the meaning into account: embeddings are set up."""
        return self._embeddings is not None

    def listen(self, listener: Callable[[SearchMeaningReady], None]) -> None:
        """Hand `SearchMeaningReady` to `listener` (the event streams of the API)."""
        self._listeners.append(listener)

    async def warm(self, actor: UserId) -> bool:
        """Have the model of the embeddings loaded before a search needs it (a person starts
        typing): one embedding in the background, at most once in `WARM_EVERY`. Whether one
        was started. AuthenticationError for a deactivated caller."""
        async with self._uow() as uow:
            await load_actor(uow, actor)
        now = self._clock.now()
        if self._embeddings is None:
            return False
        if self._warmed_at is not None and now - self._warmed_at < WARM_EVERY:
            return False
        self._warmed_at = now
        key = self._policy.query_prefix + _WARM_TEXT
        return key in self._pending or self._embed_later(key) is not None

    async def settled(self) -> None:
        """Wait for the embeddings still running in the background."""
        await asyncio.gather(*self._pending.values(), return_exceptions=True)

    async def hits(
        self,
        actor: UserId,
        text: str,
        filter: DocumentFilter | None = None,
        *,
        all_users: bool = False,
    ) -> tuple[DocumentId, ...]:
        """Every hit of `search`, as far as the index reaches (`MAX_HITS`), best first: what an
        action on many and a count over documents with words take."""
        found: dict[DocumentId, None] = {}
        offset: int | None = 0
        while offset is not None and offset < MAX_HITS:
            page = await self.search(
                actor, text, filter, offset=offset, limit=MAX_LIMIT, all_users=all_users
            )
            found.update((item.document.id, None) for item in page.items)
            offset = page.next_offset
        return tuple(found)

    async def search(
        self,
        actor: UserId,
        text: str,
        filter: DocumentFilter | None = None,
        *,
        offset: int = 0,
        limit: int = SEARCH_PAGE,
        semantic_ratio: float | None = None,
        order: DocumentOrder | None = None,
        all_users: bool = False,
    ) -> SearchPage:
        """Documents within the caller's reach that match `text` (and `filter`), by relevance
        or in `order`; with `all_users` (admins only), any document. Each says whether it stands
        open in the caller's inbox (with `all_users`, in every user's).

        ValidationError for an empty text, a paging outside the limits or an order by a field
        (the index holds no field values), AuthenticationError
        for a deactivated caller, PermissionDeniedError for `all_users` without being an admin,
        SearchUnavailableError if the index cannot be reached.
        """
        filter = filter or DocumentFilter()
        ratio = self._policy.semantic_ratio if semantic_ratio is None else semantic_ratio
        check_search(text, ratio, offset, limit)
        if order is not None and order.key is SortKey.FIELD:
            raise ValidationError("sort: the search cannot sort by a field")
        async with self._uow() as uow:
            user = await load_lister(uow, actor, all_users, Action.SEARCH_ALL_DOCUMENTS)
            check_fact_filter(user, filter)
            spaces = await uow.spaces.list_accessible(actor)
            filter = await expanded(uow, filter)
        if offset >= MAX_HITS:
            return SearchPage([], 0, None, SearchMode.WORDS)
        limit = min(limit, MAX_HITS - offset)

        meaning = await self._meaning(actor, text) if ratio > 0 else _Meaning(None)
        try:
            result = await self._index.search(
                SearchQuery(
                    text=text,
                    visibility=replace(
                        Visibility.of(Reach.of(actor, spaces)), everything=all_users
                    ),
                    filter=filter,
                    vector=meaning.vector,
                    semantic_ratio=ratio,
                    order=order,
                    offset=offset,
                    limit=limit,
                    meaning_min_score=self._policy.meaning_min_score,
                )
            )
        except SearchUnavailableError as error:
            log.warning("the search index cannot be reached: %s", error)
            raise SearchUnavailableError(because(ReasonCode.SEARCH_INDEX_UNAVAILABLE)) from error

        items = []
        by_id: dict[SpaceId, Space] = {space.id: space for space in spaces}
        async with self._uow() as uow:
            contacts, types = await group_lookup(uow, filter)
            for hit in result.hits:
                document = await uow.documents.find(hit.id)
                if document is None:
                    continue  # deleted since the index was written
                if document.space_id not in by_id:
                    by_id[document.space_id] = await uow.spaces.get(document.space_id)
                space = by_id[document.space_id]
                allowed = all_users or reach_access(user, document, space) is not None
                access = document_access(user, document, space)
                facts = (
                    fact_tokens(await uow.document_facts.of_document(document.id))
                    if filter.facts
                    else frozenset()
                )
                if (
                    not allowed
                    or access is None
                    or not matches(document, filter, contacts, types, facts)
                ):
                    continue  # the index is behind: a membership or a lane has changed
                items.append(SearchItem(document, access, hit.score, hit.snippet))
            waiting = await in_inbox(
                uow, actor, [item.document for item in items], all_users=all_users
            )
        items = [replace(item, in_inbox=item.document.id in waiting) for item in items]
        if len(items) < len(result.hits):
            log.info(
                "search hits dropped after the check against the database",
                extra={"user_id": str(actor), "dropped": len(result.hits) - len(items)},
            )

        end = offset + len(result.hits)
        # A search with meaning can reach every document, whatever the estimate of the words.
        reach = MAX_HITS if result.semantic else min(result.estimated_total, MAX_HITS)
        more = len(result.hits) == limit and end < reach
        if result.semantic:
            mode, reason, pending = SearchMode.HYBRID, None, False
        else:
            mode, reason, pending = SearchMode.WORDS, meaning.reason, meaning.pending
        words = result.estimated_total if result.word_total is None else result.word_total
        return SearchPage(
            items,
            result.estimated_total,
            end if more else None,
            mode,
            reason,
            pending,
            word_total=words,
        )

    async def places(self, actor: UserId, document: DocumentId, text: str) -> SearchPlaces:
        """Where the words of a search for `text` stand in `document`, as the search matches
        them, for one who reads it: what the Beam marks for a hit. ValidationError for an empty
        text, NotFoundError for a document they do not read, SearchUnavailableError if the index
        cannot be reached."""
        check_search(text, 0, 0, 1)
        async with self._uow() as uow:
            user = await load_actor(uow, actor)
            found, _ = await readable_document(uow, user, document)
        # Read access is checked against the database; the index needs no reach of its own.
        try:
            matches = await self._index.matches(
                found.id, text, Visibility(frozenset(), everything=True)
            )
        except SearchUnavailableError as error:
            log.warning("the search index cannot be reached: %s", error)
            raise SearchUnavailableError(because(ReasonCode.SEARCH_INDEX_UNAVAILABLE)) from error
        if not matches or self._store is None:
            return SearchPlaces(len(matches))
        try:
            content = (await load_text(self._store, found.id)).decode("utf-8", "replace")
        except NotFoundError:
            return SearchPlaces(0)
        matches = _worth_marking(content, matches, text)
        pages = await load_layout(self._store, found.id)
        if not matches or not pages:
            return SearchPlaces(len(matches))
        places = await asyncio.to_thread(TextPlaces, content, pages)
        best = _best(content, matches)
        occurrences = tuple(
            Occurrence(located, own=match == best)
            for match in matches
            if (located := places.locations(match.start, match.end))
        )
        return SearchPlaces(len(matches), occurrences)

    async def _meaning(self, actor: UserId, text: str) -> _Meaning:
        """The vector of the query, or why there is none: without embeddings, or with the
        service down, too slow or answering with a vector of another length, the search goes
        by words alone (it should not depend on it). A vector is kept for the same query; one
        too slow goes on being made in the background, and the searcher learns when it is
        ready (`SearchMeaningReady`)."""
        if self._embeddings is None:
            return _Meaning(None, because(ReasonCode.SEARCH_NO_EMBEDDINGS))
        key = self._policy.query_prefix + text
        if (vector := self._kept(key)) is not None:
            return _Meaning(vector)
        seconds = self._policy.embed_timeout.total_seconds()
        task = self._pending.get(key) or self._embed_later(key)
        try:
            if task is None:  # too many in the background already: given up when too slow
                vector = await asyncio.wait_for(self._vector_of(key), seconds)
            else:
                vector = await asyncio.wait_for(asyncio.shield(task), seconds)
        except TimeoutError:
            log.warning("searching without meaning, the query was not embedded in time")
            waited = int(seconds) if seconds.is_integer() else seconds
            reason = because(ReasonCode.SEARCH_EMBED_TIMEOUT, seconds=waited)
            if task is None:
                return _Meaning(None, reason)
            self._waiting[key].add((actor, text))
            return _Meaning(None, reason, pending=True)
        except EmbeddingsError as error:
            log.warning("searching without meaning, the query was not embedded: %s", error)
            return _Meaning(None, because(ReasonCode.SEARCH_EMBED_FAILED))
        except _OtherLengthError as error:
            log.warning("searching without meaning, %s", error)
            reason = because(ReasonCode.SEARCH_EMBED_DIMENSIONS, got=error.got, wanted=error.wanted)
            return _Meaning(None, reason)
        return _Meaning(vector)

    async def _vector_of(self, key: str) -> tuple[float, ...]:
        """The vector of a query (with its prefix). EmbeddingsError if the service fails,
        `_OtherLengthError` for a vector of another length than the index's."""
        assert self._embeddings is not None
        result = await self._embeddings.embed([key])
        if not result.vectors:
            raise EmbeddingsError("no vector for the query")
        vector = tuple(result.vectors[0])
        wanted = self._policy.dimensions
        if wanted is not None and len(vector) != wanted:
            raise _OtherLengthError(len(vector), wanted)
        return vector

    def _embed_later(self, key: str) -> asyncio.Task[tuple[float, ...]] | None:
        """Embed a query in a task of its own, which goes on when a search stops waiting; None
        with too many such tasks running already."""
        if len(self._pending) >= _PENDING_AT_MOST:
            return None
        task = asyncio.create_task(self._vector_of(key))
        self._pending[key] = task
        task.add_done_callback(lambda done: self._embedded(key, done))
        return task

    def _embedded(self, key: str, task: asyncio.Task[tuple[float, ...]]) -> None:
        """A query is embedded: keep its vector, and tell the searchers that gave up waiting."""
        self._pending.pop(key, None)
        waiting = self._waiting.pop(key, set())
        if task.cancelled() or task.exception() is not None:
            return  # they keep the words
        self._keep(key, task.result())
        for user, text in waiting:
            event = SearchMeaningReady(occurred_at=self._clock.now(), user_id=user, query=text)
            for listener in self._listeners:
                try:
                    listener(event)
                except Exception:
                    log.exception("a listener failed on %s", event.type)

    def _kept(self, key: str) -> tuple[float, ...] | None:
        kept = self._vectors.get(key)
        if kept is None:
            return None
        until, vector = kept
        if until <= self._clock.now():
            del self._vectors[key]
            return None
        return vector

    def _keep(self, key: str, vector: tuple[float, ...]) -> None:
        now = self._clock.now()
        self._vectors = {k: kept for k, kept in self._vectors.items() if kept[0] > now}
        while len(self._vectors) >= _KEEP_AT_MOST:
            del self._vectors[next(iter(self._vectors))]
        self._vectors[key] = (now + KEEP_VECTORS, vector)


def _worth_marking(content: str, matches: list[TextMatch], text: str) -> list[TextMatch]:
    """The places that show a word asked for: inside the text, and not a short leftover of the
    splitting, unless such a short word was asked for ("HU")."""
    short = {word.casefold() for word in _WORD.findall(text) if len(word) < SHORTEST_PLACE}
    return [
        match
        for match in matches
        if 0 <= match.start < match.end <= len(content)
        and (
            match.end - match.start >= SHORTEST_PLACE
            or content[match.start : match.end].casefold() in short
        )
    ]


def _best(content: str, matches: list[TextMatch]) -> TextMatch:
    """The first place in the line that holds the most different words of the search."""
    breaks = [at for at, character in enumerate(content) if character == "\n"]
    by_line: dict[int, set[str]] = defaultdict(set)
    first: dict[int, TextMatch] = {}
    for match in matches:
        line = bisect_right(breaks, match.start)
        by_line[line].add(content[match.start : match.end].casefold())
        first.setdefault(line, match)
    line = min(by_line, key=lambda number: (-len(by_line[number]), number))
    return first[line]
