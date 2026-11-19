"""Where text conditions hit: in the text the rules read (`evidence.normalise`, the text without
markup), traced back to the text as stored."""

import pytest

from lekto.core.domain.evidence import (
    contains,
    normalise,
    traced_normalise,
    traced_without_markup,
    without_markup,
)
from lekto.core.domain.text_hits import contained, pattern_text
from tests.builders import SAMPLES

TEXT = "Stadtwerke  Süd\nIhre Stromrechnung\n  Nr. 4711\nIBAN DE89 3704 0044 0532 0130 00"


def test_whole_words_any_case_any_whitespace() -> None:
    (hit,) = contained(TEXT, "stadtwerke süd")
    assert TEXT[slice(*hit)] == "Stadtwerke  Süd"
    assert contained(TEXT, "Strom") == ()  # not a whole word
    (number,) = contained(TEXT, "nr. 4711")
    assert TEXT[slice(*number)] == "Nr. 4711"


def test_a_long_value_without_its_spaces() -> None:
    (iban,) = contained(TEXT, "DE89370400440532013000")
    assert TEXT[slice(*iban)] == "DE89 3704 0044 0532 0130 00"


@pytest.mark.parametrize(
    ("text", "value", "shown"),
    [
        ("Herr Mueller zahlt", "Müller", "Mueller"),
        ("Herr Müller zahlt", "Mueller", "Müller"),
        ("Ihre Rech-\nnung vom Mai", "Rechnung", "Rech-\nnung"),
        ("Musterstraße 1", "musterstrasse", "Musterstraße"),
        ("Vertrag mit AT&amp;T", "AT&T", "AT&amp;T"),
        ("Die **Rechnung** Nr. 4711", "Rechnung Nr. 4711", "Rechnung** Nr. 4711"),
        ("| Rechnung | Nr. 4711 |", "rechnung nr. 4711", "Rechnung | Nr. 4711"),
        ("Steuer-ID: ﬁle 12", "file 12", "ﬁle 12"),  # the ligature, NFKC
    ],
)
def test_what_the_rule_finds_the_preview_shows(text: str, value: str, shown: str) -> None:
    """The rule reads the normalised text (`evidence.contains`); the preview finds the same,
    in the text as stored."""
    assert contains(normalise(text), value)
    (hit,) = contained(text, value)
    assert text[slice(*hit)] == shown


def test_a_pattern_runs_on_the_text_without_markup_as_in_the_rules() -> None:
    text = "Die **Rechnung** Nr. 4711\n| Datum | 01.03.2026 |"
    searched = pattern_text(text, 1000)
    assert searched.text == "Die Rechnung Nr. 4711 Datum 01.03.2026"
    start = searched.text.index("Rechnung Nr. 4711")
    begin, end = searched.span(start, start + len("Rechnung Nr. 4711"))
    assert text[begin:end] == "Rechnung** Nr. 4711"
    assert pattern_text(text, 8).text == "Die Rech"


EDGES = [
    "",
    "  \n\t ",
    "AT&amp;T &auml; &#252; &#xFC; &ampx &notit; & alone",
    "Straße ẞ ß ﬁ ﬂ ² ½ Ⅻ \uff46\uff55\uff4c\uff4c",
    "é ä Cafȩ́",  # combining marks
    "각 한",  # Hangul jamo: composed across characters
    "Rech-\nnung Kunden- \n nummer 12-\n34 soft\xadhyphen",
    "**fett** __kursiv__ `code` > Zitat # Titel ~~weg~~ ****4711 *** x",
    "| a | b |\n|---|---|\n| 1 | 2 |",
    "İstanbul ǅ ﬀ ŉ ΐ",
]


@pytest.mark.parametrize("text", EDGES)
def test_the_traced_texts_are_the_texts_the_rules_read(text: str) -> None:
    assert traced_normalise(text).text == normalise(text)
    assert traced_without_markup(text).text == without_markup(text)


def test_the_traced_texts_of_the_samples_are_the_texts_the_rules_read() -> None:
    for path in sorted(SAMPLES.glob("*")):
        if path.suffix not in (".txt", ".md", ".eml", ".html"):
            continue
        text = path.read_bytes().decode("utf-8", "replace")
        assert traced_normalise(text).text == normalise(text), path.name
