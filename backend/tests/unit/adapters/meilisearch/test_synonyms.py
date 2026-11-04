"""The synonym list: groups that Meilisearch takes as they are."""

from collections import Counter

import pytest

from lekto.adapters.outbound.meilisearch import synonyms as module
from lekto.adapters.outbound.meilisearch.synonyms import GERMAN, MAX_PER_WORD, synonyms


def test_the_groups_hold_each_word_once() -> None:
    assert all(len(group) >= 2 for group in GERMAN)
    assert all(len(set(group)) == len(group) for group in GERMAN)
    twice = [word for word, count in Counter(w for g in GERMAN for w in g).items() if count > 1]
    assert twice == []  # a word in two groups would join them through it


def test_no_word_has_more_synonyms_than_meilisearch_takes() -> None:
    assert max(len(others) for others in synonyms(["deu"]).values()) <= MAX_PER_WORD


def test_a_word_in_two_groups_gets_the_words_of_both(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = (("Rechnung", "Faktura"), ("Rechnung", "Abrechnung"))
    monkeypatch.setitem(module.BY_LOCALE, "deu", groups)
    assert synonyms(["deu"])["Rechnung"] == ["Abrechnung", "Faktura"]
