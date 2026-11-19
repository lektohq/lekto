"""The Liquid renderer passes the contract; its locale shapes dates and amounts."""

import re
import tracemalloc
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest

from lekto.adapters.outbound.liquid import LiquidTemplateRenderer, parse_locale
from lekto.adapters.outbound.liquid.renderer import MAX_RESULT
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.fields import Money, Writing
from lekto.core.domain.periods import Period
from lekto.core.domain.templates import TemplateValue
from tests.contracts.templates import TemplateRendererContract


@pytest.fixture
def template_renderer() -> LiquidTemplateRenderer:
    return LiquidTemplateRenderer(locale="de", currency="EUR")


class TestLiquidTemplateRenderer(TemplateRendererContract):
    pass


def test_the_settings_shape_dates_and_amounts() -> None:
    """`LEKTO_TEMPLATE_LOCALE` writes dates and amounts, `LEKTO_DEFAULT_CURRENCY` is that of
    `currency` without one."""
    values: dict[str, TemplateValue] = {
        "day": date(2026, 3, 31),
        "amount": Money(Decimal("3650"), "USD"),
    }
    english = LiquidTemplateRenderer(locale="en_US", currency="USD")
    assert english.render("{{ day | datetime: format: 'MMMM yyyy' }}", values) == "March 2026"
    assert english.render("{{ amount }}", values) == "3,650.00 USD"
    austrian = LiquidTemplateRenderer(locale="de-AT", currency="EUR")
    assert austrian.render("{{ amount }}", values) == "3.650,00 USD"
    assert english.render("{{ amount.amount | currency }}", values) == "$3,650.00"
    assert austrian.render("{{ amount.amount | currency }}", values) == "€\xa03.650,00"
    # How it writes, to read back what a template rendered for a field.
    assert (english.writing, austrian.writing) == (Writing("en", "USD"), Writing("de", "EUR"))


@pytest.mark.parametrize(
    ("period", "written"),
    [
        (Period.month(2026, 9), "2026-09"),
        (Period.week(2026, 38), "2026-W38"),
        (Period.week(2026, 1), "2026-W01"),  # starts on 29 December 2025
        (Period.quarter(2026, 3), "2026-Q3"),
        (Period.year(2025), "2025"),
        (Period.day(date(2026, 9, 15)), "2026-09-15"),
        (Period(date(2026, 9, 1), date(2026, 9, 14)), "2026-09-01/2026-09-14"),
    ],
)
def test_a_period_writes_what_it_is_in_iso_8601(period: Period, written: str) -> None:
    values: dict[str, TemplateValue] = {"period": period}
    german = LiquidTemplateRenderer(locale="de", currency="EUR")
    english = LiquidTemplateRenderer(locale="en_US", currency="USD")
    # In any locale; `datetime` on its ends writes it in words.
    assert german.render("{{ period }}", values) == english.render("{{ period }}", values)
    assert german.render("{{ period }}", values) == written
    # Its ends are dates, for `date` and `datetime`.
    template = "{{ period.start | date: '%Y-%m-%d' }}/{{ period.end | date: '%Y-%m-%d' }}"
    assert german.render(template, values) == str(period)


def test_a_period_in_words_through_its_start() -> None:
    values: dict[str, TemplateValue] = {"period": Period.month(2026, 9)}
    german = LiquidTemplateRenderer(locale="de", currency="EUR")
    assert german.render("{{ period.start | datetime: format: 'MMMM yyyy' }}", values) == (
        "September 2026"
    )


@pytest.mark.parametrize(("text", "locale"), [("de", "de"), ("de-AT", "de_AT"), ("en_us", "en_US")])
def test_a_locale_is_named_as_babel_names_it(text: str, locale: str) -> None:
    assert parse_locale(text) == locale


@pytest.mark.parametrize("text", ["xx_YY", "de DE", ""])
def test_an_unknown_locale_is_refused(text: str) -> None:
    """With one message, whether Babel does not know the locale or cannot read the name."""
    message = re.escape(f"unknown locale {text!r}")
    with pytest.raises(ValueError, match=message):
        parse_locale(text)
    with pytest.raises(ValueError, match=message):
        LiquidTemplateRenderer(locale=text, currency="EUR")


@contextmanager
def at_most(megabytes: float) -> Iterator[None]:
    """The block allocates at most `megabytes` at once."""
    tracemalloc.start()
    try:
        yield
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < megabytes * 1024**2, f"{peak / 1024**2:.1f} MB"


def test_a_chain_of_filters_stops_at_the_first_result_too_large() -> None:
    """Liquid's limits look at what is assigned and written out: three `replace` made 1.6
    billion characters of 200 before the output was refused (3 GB)."""
    renderer = LiquidTemplateRenderer(locale="de", currency="EUR")
    x = "a" * 200
    bomb = '{% assign x = "' + x + '" %}{{ x | replace: "a", x | replace: "a", x }}'
    with at_most(1), pytest.raises(ValidationError, match="the filter 'replace' has more than"):
        renderer.render(bomb, {})


@pytest.mark.parametrize(
    ("template", "values", "message"),
    [
        (
            '{{ "a" | append: big }}',
            {"big": "b" * MAX_RESULT},
            "'append' has more than 10000 characters",
        ),
        (
            "{{ list | concat: list | size }}",
            {"list": ["c"] * 6000},
            "'concat' has more than 10000 entries",
        ),
        (
            "{{ list | concat: list | size }}",
            {"list": ["c" * 6000]},
            "'concat' has more than 10000 characters",
        ),
        (
            "{% assign n = 1" + "0" * 4000 + " %}{{ n | times: n | times: n }}",
            {},
            "'times' has more than 10000 digits",
        ),
    ],
    ids=["text", "list entries", "list characters", "number"],
)
def test_every_filter_s_result_is_bounded(
    template: str, values: dict[str, TemplateValue], message: str
) -> None:
    renderer = LiquidTemplateRenderer(locale="de", currency="EUR")
    with pytest.raises(
        ValidationError, match=re.escape(f"invalid template: the result of the filter {message}")
    ):
        renderer.render(template, values)


def test_replace_and_join_are_refused_before_they_multiply() -> None:
    """A single call of them writes 10 000 characters for each of 10 000: refused before."""
    renderer = LiquidTemplateRenderer(locale="de", currency="EUR")
    long = "x" * MAX_RESULT
    values: dict[str, TemplateValue] = {"long": long, "many": ["a"] * 5000}
    for template in ('{{ long | replace: "x", long }}', "{{ many | join: long }}"):
        with at_most(1), pytest.raises(ValidationError, match="has more than 10000 characters"):
            renderer.render(template, values)


def test_a_result_at_the_limit_is_written() -> None:
    renderer = LiquidTemplateRenderer(locale="de", currency="EUR")
    half = "y" * (MAX_RESULT // 2)
    assert renderer.render("{{ half | append: half }}", {"half": half}) == half * 2
    assert renderer.render('{{ list | join: "-" }}', {"list": ["a", "b"]}) == "a-b"
