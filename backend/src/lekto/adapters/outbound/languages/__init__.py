"""The words of a language that the search treats apart, read from `languages/<locale>/` (the
locale as `LEKTO_SEARCH_LOCALES` names it, such as `deu`):

- `stop_words.txt`: a word per line; the search leaves them out.
- `synonyms.txt`: a group per line, its words separated by commas; each finds what the others
  find.

Lines starting with `#` are comments. A language without a file has none of them; a new
language is a new folder. Shared infrastructure of the search adapters, not an adapter: the
Meilisearch adapter hands the words to its index, the in-memory one leaves the stop words out
itself (`words`).
"""

import re
import unicodedata
from collections import defaultdict
from collections.abc import Collection
from functools import cache
from importlib.resources import files

MAX_SYNONYMS = 50  # Meilisearch ignores the synonyms of a word beyond
_WORD = re.compile(r"\w+")


def words(text: str, stop_words: Collection[str] = ()) -> list[str]:
    """The words of `text` as the stop words are written (NFC, casefolded), in their order,
    without `stop_words`; nothing is left of a text of stop words alone ("und", "wie ich")."""
    found = (unicodedata.normalize("NFC", word.casefold()) for word in _WORD.findall(text))
    return [word for word in found if word not in stop_words]


@cache
def _lines(locale: str, name: str) -> tuple[str, ...]:
    path = files(__name__).joinpath(locale, name)
    if not path.is_file():
        return ()
    text = path.read_text(encoding="utf-8")
    return tuple(
        line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")
    )


def stop_word_list(locale: str) -> tuple[str, ...]:
    return _lines(locale, "stop_words.txt")


def synonym_groups(locale: str) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(word.strip() for word in line.split(",") if word.strip())
        for line in _lines(locale, "synonyms.txt")
    )


def stop_words(locales: Collection[str]) -> list[str]:
    """The stop words of the languages, sorted (as Meilisearch keeps them)."""
    return sorted({word for locale in locales for word in stop_word_list(locale)})


def synonyms(locales: Collection[str]) -> dict[str, list[str]]:
    """The synonyms of the languages, as Meilisearch takes them: for each word the others of
    its groups, sorted."""
    found: defaultdict[str, set[str]] = defaultdict(set)
    for locale in locales:
        for group in synonym_groups(locale):
            for word in group:
                found[word].update(other for other in group if other != word)
    return {word: sorted(others) for word, others in sorted(found.items())}
