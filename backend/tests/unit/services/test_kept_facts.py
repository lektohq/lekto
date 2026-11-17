"""Keeping a document's facts (`kept_facts`): where each fact stands is found once, when the
text is read outside the event loop; the facts are merged outside it too, with the text
normalised once (SA-02)."""

import asyncio
import threading
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest

from lekto.adapters.outbound.memory import FakeCodeReader
from lekto.core.domain import document_facts, holders
from lekto.core.domain.document_facts import FactOrigin, HolderKind, ReadFact, found_facts
from lekto.core.domain.evidence import normalise
from lekto.core.domain.holders import ReadHolder
from lekto.core.domain.identifiers import IdentifierKind, identifiers_in, places_in, referred_in
from lekto.core.domain.pipeline import Node, NodeResult, NodeRun, Outcome
from lekto.core.services.classification import kept_facts
from lekto.core.services.classification.answers import read_fact_to_json
from lekto.core.services.classification.kept_facts import TextFacts, keep_facts
from lekto.core.services.classification.signals import MODEL_FACTS, FactsResult, FactsSignal
from tests import builders
from tests.unit.services.support import World
from tests.unit.services.test_signals import stored

TEXT = (
    "Muster Bank\nKontoauszug\nIBAN DE02 1203 0000 0000 2020 51\n"
    "Kundennummer 12345\nIhre Rechnung Nr. 4711 ist bezahlt.\n"
    "Gutschrift auf DE02120300000000202051\n"
)
IBAN = (IdentifierKind.IBAN, "DE02120300000000202051")
CODED = (IdentifierKind.IBAN, "DE89370400440532013000")


def _refused(name: str) -> Callable[..., Any]:
    def refused(*args: object) -> Any:
        raise AssertionError(f"{name} again")

    return refused


async def test_where_the_facts_stand_is_found_once_when_the_text_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    read = await TextFacts.read(TEXT)
    expected = found_facts(TEXT, identifiers_in(TEXT), {CODED}, places_in(TEXT), referred_in(TEXT))
    assert [fact.written for fact in expected] == [
        "DE02 1203 0000 0000 2020 51",
        "12345",
        "4711",
        None,  # only in a code
    ]
    monkeypatch.setattr(document_facts, "identifier_spans", _refused("searched the text"))
    assert read.found({CODED}) == expected
    assert read.found() == expected[:-1]


async def test_the_facts_are_merged_outside_the_loop_with_the_text_normalised_once(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = await world.user()
    document = await stored(world, owner, TEXT)
    read = await TextFacts.read(TEXT)
    model = [
        ReadFact(
            kind="customer_number", value="12345", role="contact", evidence="Kundennummer 12345"
        )
    ]
    told = [
        ReadHolder(
            kind="iban",
            value=IBAN[1],
            holder="recipient",
            evidence="IBAN DE02 1203 0000 0000 2020 51",
        )
    ]
    merging = kept_facts.merged_facts
    threads: list[int] = []

    def merged(*args: Any) -> Any:
        threads.append(threading.get_ident())
        return merging(*args)

    def normalising(text: str) -> str:
        assert text != TEXT, "the whole text normalised again"
        return normalise(text)

    monkeypatch.setattr(kept_facts, "merged_facts", merged)
    monkeypatch.setattr(document_facts, "normalise", normalising)
    monkeypatch.setattr(holders, "normalise", normalising)
    async with world.uow() as uow:
        report = await keep_facts(uow, document.id, read, model, in_codes=(), holders={}, told=told)
        facts = {fact.key: fact for fact in await uow.document_facts.of_document(document.id)}
    assert threads and threads[0] != threading.get_ident()
    assert report == {"taken": 1, "refused": [], "holders": {"taken": 1, "refused": []}}
    customer = facts[(IdentifierKind.CUSTOMER_NUMBER, "12345")]
    assert customer.origins == {FactOrigin.PATTERN, FactOrigin.MODEL}
    holder = facts[IBAN].holder
    assert holder is not None and holder.kind is HolderKind.RECIPIENT


async def test_the_facts_signal_waits_for_the_model_s_half_before_it_reads_it(
    world: World,
) -> None:
    """The model's signal keeps its facts holding the lock, not committed yet; the facts signal
    stores meanwhile. It reads the model's facts from the log after the lock, so both halves
    stay (SA-14): read before, it wrote the patterns' alone over the model's."""
    owner = await world.user()
    document = await stored(world, owner, TEXT)
    patterns = await FactsSignal(world.uow, world.object_store, FakeCodeReader([])).run(document)
    assert isinstance(patterns, FactsResult)
    model = [
        ReadFact(
            kind="customer_number", value="12345", role="contact", evidence="Kundennummer 12345"
        )
    ]
    keeping = world.uow()
    async with keeping as uow:
        await uow.processing_log.append(
            NodeRun(
                document_id=document.id,
                node=Node.SIGNAL_LLM,
                run=1,
                result=NodeResult(
                    outcome=Outcome.OK,
                    output={MODEL_FACTS: [read_fact_to_json(fact) for fact in model]},
                ),
                pipeline_version="1",
                started_at=builders.NOW,
                duration=timedelta(seconds=1),
            )
        )
        await keep_facts(uow, document.id, await TextFacts.read(TEXT), model)

        async def store_patterns() -> None:
            async with world.uow() as other:
                current = await other.documents.get(document.id)
                await patterns.apply(other, current, builders.NOW)
                await other.commit()

        storing = asyncio.create_task(store_patterns())
        for _ in range(5):
            await asyncio.sleep(0)  # it starts and waits for the lock
        await uow.commit()
    await storing
    async with world.uow() as uow:
        facts = {fact.key: fact for fact in await uow.document_facts.of_document(document.id)}
    customer = facts[(IdentifierKind.CUSTOMER_NUMBER, "12345")]
    assert customer.origins == {FactOrigin.PATTERN, FactOrigin.MODEL}
