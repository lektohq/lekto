"""Templates in Liquid (`python-liquid`), for users: no other templates (`include`, `render`
are not tags here), no attributes of Python objects (Liquid looks up keys only), bounded loops
and output, and bounded results of filters (`_Bounded`).

Values come as the domain has them and are given to Liquid in forms its filters understand: a
number is a float that writes itself as its exact decimal text (Liquid's arithmetic filters
know no `Decimal`), an amount a mapping of `amount` and `currency` that writes itself in the
locale (`3.650,00 EUR` in `de`), a date stays a date. The filters `datetime`, `currency` and
`decimal` format in the locale (Babel); `datetime` takes a date without shifting it into a time
zone. `json` writes a value as JSON in the forms of the API (`fields.field_to_json`), for the
bodies of webhooks.
"""

import json
import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any

from babel import Locale, UnknownLocaleError
from babel.dates import format_date
from babel.numbers import format_currency
from liquid import BoundTemplate, Environment, FalsyStrictUndefined, Undefined
from liquid.exceptions import LiquidError, UndefinedError
from liquid.extra import Currency, DateTime, Number
from liquid.filter import liquid_filter

from lekto.core.domain.errors import MissingValueError, ValidationError
from lekto.core.domain.fields import Money, Writing
from lekto.core.domain.periods import Period
from lekto.core.domain.templates import TemplateValue

_UNDEFINED = re.compile(r"^'?(?P<path>.+?)'? is undefined$")
_LOCATION = re.compile(r"' (?P<line>\d+):(?P<column>\d+)\n")
_FORBIDDEN_TAGS = ("include", "render")


def parse_locale(text: str) -> str:
    """The locale `text` names (`de`, `de-AT`, `de_AT`) as Babel names it; ValueError if it
    names none."""
    try:
        return str(Locale.parse(text.replace("-", "_")))
    except (ValueError, UnknownLocaleError):
        raise ValueError(f"unknown locale {text!r}") from None


class _Environment(Environment):
    context_depth_limit = 10
    local_namespace_limit = 10_000
    loop_iteration_limit = 1_000
    output_stream_limit = 10_000


MAX_RESULT = _Environment.output_stream_limit
"""The characters a filter's result may have at most: as many as the output. A list may have as
many entries, and as many characters in its texts; a number as many digits."""
_MAX_NUMBER = 10**MAX_RESULT


class _Bounded:
    """A filter whose result stops the render once it is larger than `MAX_RESULT`. Liquid's own
    limits look at what is assigned and written out, not at what the filters of an expression
    make on the way: three `replace` made 1.6 billion characters of 200, 3 GB, before the output
    was refused. `before` looks at the arguments of a filter that multiplies in a single call,
    before it runs. Everything else of the filter (`with_context`, `with_environment`) is the
    filter's own."""

    def __init__(
        self, name: str, inner: Callable[..., object], before: "_Before | None" = None
    ) -> None:
        self._name = name
        self._inner = inner
        self._before = before

    def __getattr__(self, attribute: str) -> object:
        return getattr(self._inner, attribute)

    def __call__(self, left: object, *args: Any, **kwargs: Any) -> object:
        if self._before is not None:
            self._before(self._name, left, *args)
        result = self._inner(left, *args, **kwargs)
        _check_result(self._name, result)
        return result


type _Before = Callable[..., None]


def _check_result(name: str, result: object) -> None:
    match result:
        case str() if len(result) > MAX_RESULT:
            raise _too_large(name, "characters")
        case list() | tuple() if len(result) > MAX_RESULT:
            raise _too_large(name, "entries")
        case list() | tuple() if sum(len(item) for item in result if isinstance(item, str)) > (
            MAX_RESULT
        ):
            raise _too_large(name, "characters")
        case int() if not isinstance(result, bool) and abs(result) >= _MAX_NUMBER:
            raise _too_large(name, "digits")


def _too_large(name: str, unit: str) -> ValidationError:
    return ValidationError(
        f"invalid template: the result of the filter {name!r} has more than {MAX_RESULT} {unit}"
    )


def _text(value: object) -> str:
    """`value` as a string filter takes it (`liquid.filter.string_filter`)."""
    return "" if value is None else value if isinstance(value, str) else str(value)


def _before_replace(
    name: str, left: object, seq: object = "", sub: object = "", *_: object
) -> None:
    """`replace` writes `sub` for every `seq`: 10 000 characters for each of 10 000."""
    text, seq, sub = _text(left), _text(seq), _text(sub)
    grows = len(sub) - len(seq)
    if grows > 0 and len(text) + text.count(seq) * grows > MAX_RESULT:
        raise _too_large(name, "characters")


def _before_join(name: str, left: object, separator: object = " ", *_: object) -> None:
    """`join` writes the separator between every two entries: 10 000 characters 10 000 times."""
    if isinstance(left, (list, tuple)):
        texts = sum(len(item) for item in left if isinstance(item, str))
        if texts + max(0, len(left) - 1) * len(_text(separator)) > MAX_RESULT:
            raise _too_large(name, "characters")


_BEFORE: Mapping[str, _Before] = {"replace": _before_replace, "join": _before_join}


class _DateTime(DateTime):
    """Babel's `datetime`, with a date as a date (Liquid's would make it midnight, UTC)."""

    def __init__(self, locale: str) -> None:
        super().__init__(default_locale=locale, default_timezone="UTC")
        self._locale = locale

    def __call__(self, left: object, *args: Any, **kwargs: Any) -> str:
        if isinstance(left, date) and not isinstance(left, datetime):
            format = str(kwargs.get("format") or "medium")
            return format_date(left, format=format, locale=self._locale)
        return str(super().__call__(left, *args, **kwargs))


class _Json:
    """`json`: a value as JSON text, as the API writes it (`fields.field_to_json`): a number as
    its exact decimal text, an amount as `{amount, currency}`, a date in ISO 8601, a period as
    `{start, end}`; text, yes/no, lists and mappings as they are. A missing value is missing
    (`| default: nil` makes it `null`)."""

    name = "json"

    @liquid_filter
    def __call__(self, value: object) -> str:
        return json.dumps(_plain(value), ensure_ascii=False)


def _plain(value: object) -> object:
    match value:
        case Undefined():
            str(value)  # raises UndefinedError, naming the value
            return None
        case _Number():
            return str(value)
        case _Amount():
            return {"amount": str(value["amount"]), "currency": value["currency"]}
        case _Period():
            start, end = value["start"], value["end"]
            assert isinstance(start, date) and isinstance(end, date)
            return {"start": start.isoformat(), "end": end.isoformat()}
        case date():
            return value.isoformat()
        case None | bool() | int() | float() | str():
            return value
        case Mapping():
            return {str(key): _plain(item) for key, item in value.items()}
        case Sequence():
            return [_plain(item) for item in value]
    raise TypeError(f"not a template value: {type(value).__name__}")


class LiquidTemplateRenderer:
    def __init__(self, *, locale: str, currency: str) -> None:
        """`locale` writes dates and amounts (`LEKTO_TEMPLATE_LOCALE`); `currency` is that
        of the `currency` filter where a template names none (`LEKTO_DEFAULT_CURRENCY`)."""
        self._locale = parse_locale(locale)
        environment = _Environment(undefined=FalsyStrictUndefined)
        for tag in _FORBIDDEN_TAGS:
            del environment.tags[tag]
        environment.filters["datetime"] = _DateTime(self._locale)
        environment.filters["currency"] = Currency(
            default_locale=self._locale, default_currency_code=currency
        )
        environment.filters["decimal"] = Number(default_locale=self._locale)
        environment.filters["json"] = _Json()
        for name, inner in list(environment.filters.items()):
            environment.filters[name] = _Bounded(name, inner, _BEFORE.get(name))
        self._environment = environment
        self._parse = lru_cache(maxsize=512)(self._parsed)
        self._writing = Writing(Locale.parse(self._locale).language, currency)

    @property
    def writing(self) -> Writing:
        return self._writing

    def check(self, template: str) -> frozenset[str]:
        parsed = self._parse(template)
        unknown = sorted(set(parsed.filter_names()) - set(self._environment.filters))
        if unknown:
            raise ValidationError(f"invalid template: unknown filter {unknown[0]!r}")
        return frozenset(parsed.global_variable_paths())

    def render(self, template: str, values: Mapping[str, TemplateValue]) -> str:
        parsed = self._parse(template)
        try:
            return parsed.render(**_mapping(values, self._locale))
        except UndefinedError as error:
            found = _UNDEFINED.match(str(error.message or ""))
            raise MissingValueError(found.group("path") if found else "a value") from None
        except LiquidError as error:
            raise _invalid(error) from None
        except ValidationError:
            raise  # a filter's result too large (`_Bounded`)
        except Exception as error:
            # A valid template can still fail on its values: a time pattern on a date (`HH:mm`,
            # or `mm` meant as the month), a sum over text, a date out of range. The callers
            # handle a `ValidationError` (a rule's step, a preview, a webhook body).
            raise ValidationError(f"invalid template: a filter failed: {error}") from None

    def _parsed(self, template: str) -> BoundTemplate:
        try:
            return self._environment.parse(template)
        except LiquidError as error:
            raise _invalid(error) from None


def _invalid(error: LiquidError) -> ValidationError:
    found = _LOCATION.search(error.detailed_message())
    where = f" (line {found.group('line')}, column {found.group('column')})" if found else ""
    return ValidationError(f"invalid template: {error.message}{where}")


class _Number(float):
    """A number for Liquid's filters that writes itself as its exact decimal text."""

    _text: str

    def __new__(cls, value: Decimal) -> "_Number":
        number = super().__new__(cls, value)
        number._text = format(value, "f")
        return number

    def __str__(self) -> str:
        return self._text

    __repr__ = __str__


class _Amount(Mapping[str, object]):
    """An amount: `amount` and `currency`, written as `3.650,00 EUR` in the locale."""

    def __init__(self, money: Money, locale: str) -> None:
        self._values: dict[str, object] = {
            "amount": _Number(money.amount),
            "currency": money.currency,
        }
        self._text = format_currency(
            money.amount, money.currency, "#,##0.00 ¤¤", locale=locale, currency_digits=True
        )

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __str__(self) -> str:
        return self._text


class _Period(Mapping[str, object]):
    """A period: `start` and `end` (dates for `date` and `datetime`), written in ISO 8601 by
    what it is: `2026-09`, `2026-W38`, `2026-Q3`, `2026`, a day as `2026-09-15`, else its ends,
    `2026-09-01/2026-09-14` (`Period.notation`)."""

    def __init__(self, period: Period) -> None:
        self._values: dict[str, object] = {"start": period.start, "end": period.end}
        self._text = period.notation

    def __getitem__(self, key: str) -> object:
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._values)

    def __len__(self) -> int:
        return len(self._values)

    def __str__(self) -> str:
        return self._text


def _mapping(values: Mapping[str, TemplateValue], locale: str) -> dict[str, object]:
    return {key: _value(value, locale) for key, value in values.items() if value is not None}


def _value(value: TemplateValue, locale: str) -> object:
    match value:
        case bool() | str() | int() | date():
            return value
        case Decimal():
            return _Number(value)
        case Money():
            return _Amount(value, locale)
        case Period():
            return _Period(value)
        case Mapping():
            return _mapping(value, locale)
        case Sequence():
            return [_value(item, locale) for item in value if item is not None]
    raise TypeError(f"not a template value: {type(value).__name__}")
