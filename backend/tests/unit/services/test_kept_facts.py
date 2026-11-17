"""Keeping a document's facts (`kept_facts`): where each fact stands is found once, when the
text is read outside the event loop; the facts are merged outside it too, with the text
normalised once (SA-02)."""

import threading
from collections.abc import Callable
from typing import Any

import pytest

from lekto.core.domain import document_facts, holders
from lekto.core.domain.document_facts import FactOrigin, HolderKind, ReadFact, found_facts
from lekto.core.domain.evidence import normalise
from lekto.core.domain.holders import ReadHolder
from lekto.core.domain.identifiers import IdentifierKind, identifiers_in, places_in, referred_in
from lekto.core.services.classification import kept_facts
from lekto.core.services.classification.kept_facts import TextFacts, keep_facts
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
