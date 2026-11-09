"""Pieces more than one area of the API uses."""

from collections.abc import Callable
from datetime import timedelta
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from lekto.core.domain.validation import MAX_NAME

Name = Annotated[str, Field(min_length=1, max_length=MAX_NAME, examples=["ACME Energy"])]


class NameIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"name": "ACME Energy"}]},
    )

    name: Name


def following_offset(offset: int, count: int, total: int) -> int | None:
    """The `offset` of the page after one of `count` items from `offset` among `total`; None on
    the last page."""
    end = offset + count
    return end if count and end < total else None


def ms(value: timedelta) -> float:
    """A duration in milliseconds, to a tenth."""
    return round(value.total_seconds() * 1000, 1)


def each_once[T](items: list[T], key: Callable[[T], object], what: str) -> list[T]:
    """`items` unchanged, if no two share their `key`; else the error a validator raises
    ("each field once")."""
    if len({key(item) for item in items}) != len(items):
        raise ValueError(f"each {what} once")
    return items
