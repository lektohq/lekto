"""The words Lekto reads in documents stand in `vocabulary` alone, not in the modules that
build their patterns from them."""

import inspect

import pytest

from lekto.core.domain import evidence, periods
from lekto.core.domain.identifiers import letter_date
from lekto.core.services import indexing


@pytest.mark.parametrize("module", [evidence, periods, indexing, letter_date])
@pytest.mark.parametrize(
    "word", ['"Januar"', '"nein"', '"KW ', "kalenderwoche", '"pfund"', "jänner"]
)
def test_a_module_holds_no_words_of_its_own(module: object, word: str) -> None:
    assert word not in inspect.getsource(module)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "between", ["-", "bis", "bis zum", "bis einschl.", "bis einschließlich", "until", "through"]
)
def test_the_words_between_the_ends_of_a_span_still_read(between: str) -> None:
    found = evidence.periods_in(f"01.09.2026 {between} 30.09.2026")
    assert any(
        (period.start.isoformat(), period.end.isoformat()) == ("2026-09-01", "2026-09-30")
        for period in found
    )
