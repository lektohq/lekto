"""The words Lekto reads in documents stand in `vocabulary` alone, not in the modules that
build their patterns from them."""

from pathlib import Path

import pytest

import lekto.core
from lekto.core.domain import evidence, vocabulary

CORE = Path(lekto.core.__file__).parent


@pytest.mark.parametrize(
    "word", ['"Januar"', '"nein"', '"KW ', "kalenderwoche", '"pfund"', "jänner", "okt"]
)
def test_no_module_of_the_core_holds_words_of_its_own(word: str) -> None:
    """Forms no docstring has: every word in lower case would hit "may", "no" or "true" in the
    text of a hundred modules (TB-01)."""
    words = Path(vocabulary.__file__)
    holding = [
        str(path.relative_to(CORE))
        for path in sorted(CORE.rglob("*.py"))
        if path != words and word in path.read_text(encoding="utf-8")
    ]
    assert holding == []


@pytest.mark.parametrize(
    "between", ["-", "bis", "bis zum", "bis einschl.", "bis einschließlich", "until", "through"]
)
def test_the_words_between_the_ends_of_a_span_still_read(between: str) -> None:
    found = evidence.periods_in(f"01.09.2026 {between} 30.09.2026")
    assert any(
        (period.start.isoformat(), period.end.isoformat()) == ("2026-09-01", "2026-09-30")
        for period in found
    )
