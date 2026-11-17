"""JSON forms of field values; enums of the API."""

from datetime import date
from decimal import Decimal
from typing import get_args

import pytest

from lekto.adapters.inbound.rest.schemas.documents import ReprocessNode
from lekto.adapters.inbound.rest.schemas.inbox import ResumeNode, Signal
from lekto.adapters.inbound.rest.schemas.push import Locale, NoticeKind, PushPreferencesBody
from lekto.adapters.inbound.schemas import MoneyValue, PeriodValue, field_json
from lekto.core.domain.documents import REPROCESSABLE_NODES, RESUMABLE_NODES
from lekto.core.domain.fields import Money, Url
from lekto.core.domain.ids import UserId, new_id
from lekto.core.domain.periods import Period
from lekto.core.domain.pipeline import SIGNALS, Node
from lekto.core.domain.push import DEFAULT_KINDS, LOCALES, PushPreferences


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("5.335E+7"), "53350000"),
        (Decimal("1E+2"), "100"),
        (Decimal("12.50"), "12.50"),
        (Decimal("-0.001"), "-0.001"),
        (Decimal("7"), "7"),
    ],
)
def test_numbers_are_written_in_plain_notation(value: Decimal, expected: str) -> None:
    assert field_json(value) == expected


def test_amounts_are_written_in_plain_notation() -> None:
    assert field_json(Money(Decimal("5.335E+7"), "EUR")) == MoneyValue(
        amount="53350000", currency="EUR"
    )
    assert field_json(Money(Decimal("84.20"), "EUR")) == MoneyValue(amount="84.20", currency="EUR")


def test_other_types_keep_their_form() -> None:
    assert field_json("text") == "text"
    assert field_json(True) is True
    assert field_json(Url("https://example.org/x")) == "https://example.org/x"
    assert field_json(date(2026, 3, 31)) == "2026-03-31"


def test_periods_are_their_start_and_end() -> None:
    assert field_json(Period.month(2026, 9)) == PeriodValue(
        start=date(2026, 9, 1), end=date(2026, 9, 30)
    )


def test_the_enums_of_the_api_are_built_from_the_core() -> None:
    """A value the core adds reaches the API, not a 500 (RA-06, RB-10)."""
    assert [signal.value for signal in Signal] == [node.value for node in Node if node in SIGNALS]
    assert [node.value for node in ReprocessNode] == [node.value for node in REPROCESSABLE_NODES]
    assert [node.value for node in ResumeNode] == [node.value for node in RESUMABLE_NODES]
    assert set(get_args(NoticeKind)) == {kind.value for kind in DEFAULT_KINDS}
    assert get_args(Locale) == LOCALES
    every = PushPreferencesBody.of(PushPreferences(id=UserId(new_id())))
    assert set(every.kinds) == {kind.value for kind in DEFAULT_KINDS}
