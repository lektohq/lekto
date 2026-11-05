"""A change of an entity given part by part: what is left `UNSET` stays as it is."""

from collections.abc import Callable
from enum import Enum

from lekto.core.domain.errors import ValidationError


class Unset(Enum):
    UNSET = "unset"


UNSET = Unset.UNSET
"""Marks a part of a change that is left as it is."""


def apply_changes(entity: object, changes: object, check: Callable[[], None]) -> None:
    """Set every part of `changes` (a dataclass whose fields name the entity's) that is not
    `UNSET` on `entity`, then `check` the result; a ValidationError from it puts everything
    back and goes on. A part the entity does not have is a mistake (AttributeError)."""
    before = dict(vars(entity))
    for name in vars(changes):
        if name not in before:
            raise AttributeError(f"{type(entity).__name__} has no part {name!r}")
    for name, value in vars(changes).items():
        if value is not UNSET:
            setattr(entity, name, value)
    try:
        check()
    except ValidationError:
        for name, value in before.items():
            setattr(entity, name, value)
        raise
