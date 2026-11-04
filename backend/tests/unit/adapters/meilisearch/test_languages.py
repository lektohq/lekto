"""The language files of the search: lists Meilisearch takes as they are."""

from collections import Counter
from importlib.resources import files

import pytest

from lekto.adapters.outbound.meilisearch import languages
from lekto.adapters.outbound.meilisearch.languages import (
    MAX_SYNONYMS,
    stop_word_list,
    stop_words,
    synonym_groups,
    synonyms,
)
from lekto.composition.settings import Settings

# A folder of a language holds its lists (not the `__pycache__` beside them).
LOCALES = sorted(
    item.name
    for item in files(languages).iterdir()
    if item.is_dir() and any(entry.name.endswith(".txt") for entry in item.iterdir())
)


def test_a_folder_is_named_as_a_locale_of_the_settings() -> None:
    assert "deu" in LOCALES
    for locale in LOCALES:
        Settings.model_validate({"search_locales": locale})  # three small letters


@pytest.mark.parametrize("locale", LOCALES)
def test_the_stop_words_are_single_small_words_once(locale: str) -> None:
    words = stop_word_list(locale)
    assert words
    assert all(word == word.lower() and " " not in word for word in words)
    assert len(set(words)) == len(words)


@pytest.mark.parametrize("locale", LOCALES)
def test_the_synonym_groups_hold_each_word_once(locale: str) -> None:
    groups = synonym_groups(locale)
    assert all(len(group) >= 2 for group in groups)
    words = Counter(word for group in groups for word in group)
    assert [word for word, count in words.items() if count > 1] == []  # it would join groups
    assert not any("." in word for word in words)  # Meilisearch splits a phrase at a point
    assert max(len(others) for others in synonyms([locale]).values()) <= MAX_SYNONYMS


def test_a_language_without_files_has_none() -> None:
    assert stop_words(["xyz"]) == []
    assert synonyms(["xyz"]) == {}


def test_the_lists_of_the_languages_are_joined() -> None:
    german = stop_words(["deu"])
    assert german == sorted(german)
    assert stop_words(["deu", "xyz"]) == german
    found = synonyms(["deu"])
    assert "Einmalzahlung" in found["Weihnachtsgeld"]
    assert "Weihnachtsgeld" in found["Einmalzahlung"]  # both ways
    assert "Weihnachtsgeld" not in found["Weihnachtsgeld"]
    assert all(others == sorted(others) for others in found.values())


def test_a_word_in_two_groups_gets_the_words_of_both(monkeypatch: pytest.MonkeyPatch) -> None:
    groups = (("Rechnung", "Faktura"), ("Rechnung", "Abrechnung"))
    monkeypatch.setattr(languages, "synonym_groups", lambda locale: groups)
    assert synonyms(["deu"])["Rechnung"] == ["Abrechnung", "Faktura"]
