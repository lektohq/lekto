"""JSON-compatible values for log entries and job payloads, and reading them back: what a value
holds of the expected type, None (or nothing) for anything else. The `require_` readers are for
input that must fit: a ValidationError that names the place otherwise."""

import json
import math
from datetime import date
from typing import Any
from uuid import UUID

from lekto.core.domain.errors import ValidationError

type JsonValue = str | int | float | bool | list[JsonValue] | dict[str, JsonValue] | None
type JsonObject = dict[str, JsonValue]


def loads(text: str | bytes) -> Any:
    """`json.loads` for what someone else wrote: a document nested deeper than the parser goes
    (some 10,000 brackets, 10 KB) is a ValueError like any that is no JSON, not the
    RecursionError the parser raises, which callers of foreign JSON do not expect (XB-08). So is
    a number that is not finite (`NaN`, `Infinity`, `1e999`), which JSON does not know and
    Python writes by default: no comparison, template or `jsonb` takes it (DB-04)."""
    try:
        return json.loads(text, parse_constant=_not_finite, parse_float=_finite)
    except RecursionError:
        raise ValueError("the JSON is nested too deeply") from None


def _not_finite(name: str) -> float:
    raise ValueError(f"{name} is no JSON number")


def _finite(written: str) -> float:
    number = float(written)
    if not math.isfinite(number):
        raise ValueError(f"{written} is too large a number")
    return number


def same_json(first: JsonValue, second: JsonValue) -> bool:
    """Whether two JSON values are the same: an object's keys in any order (Postgres gives
    `jsonb` back with its keys sorted), but `true` is not `1` and `1` not `1.0`."""
    return _canonical(first) == _canonical(second)


def _canonical(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def as_text(value: JsonValue) -> str | None:
    return value if isinstance(value, str) else None


def as_int(value: JsonValue) -> int | None:
    """A whole number; a truth value is none, although Python counts `True` as 1."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def as_number(value: JsonValue) -> float | None:
    """A whole or decimal number as a float; a truth value is none."""
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def as_bool(value: JsonValue) -> bool | None:
    return value if isinstance(value, bool) else None


def as_list(value: JsonValue) -> list[JsonValue]:
    """A list; empty for anything else."""
    return value if isinstance(value, list) else []


def as_texts(value: JsonValue) -> tuple[str, ...]:
    """The texts of a list; empty for anything else."""
    return tuple(item for item in as_list(value) if isinstance(item, str))


def as_object(value: JsonValue) -> JsonObject | None:
    return value if isinstance(value, dict) else None


def as_date(value: JsonValue) -> date | None:
    """A date as ISO 8601 text (YYYY-MM-DD)."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def as_uuid(value: JsonValue) -> UUID | None:
    """An id as text."""
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def require_object(value: JsonValue, where: str) -> JsonObject:
    found = as_object(value)
    if found is None:
        raise ValidationError(f"{where}: expected an object")
    return found


def require_date(value: JsonValue, where: str) -> date:
    found = as_date(value)
    if found is None:
        raise ValidationError(f"{where}: {value!r} is no date (YYYY-MM-DD)")
    return found


def require_uuid(value: JsonValue, where: str) -> UUID:
    found = as_uuid(value)
    if found is None:
        raise ValidationError(f"{where}: {value!r} is no id")
    return found
