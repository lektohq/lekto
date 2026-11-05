"""The tree of conditions every kind of rule has (Tobi, 05.11.2026: one model for all rules).

A group holds `all` (and) or `any` (or) of its items, each a condition or a group again; `not`
turns its result around. What a condition is and how it holds is the kind's own: a document
rule's `rules.Condition`, a mail rule's `mail_rules.MailCondition`. The tree, its limits and its
JSON form (`{"all": [...], "not": true}`) are shared.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Literal

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.json_value import JsonObject, JsonValue, require_object

type GroupMode = Literal["all", "any"]

MAX_DEPTH = 5
MAX_CONDITIONS = 50


@dataclass(frozen=True, kw_only=True)
class Group[C]:
    """`all` (and) or `any` (or) of its items; `negate` turns the result around."""

    mode: GroupMode
    items: tuple["C | Group[C]", ...]
    negate: bool = False

    def __post_init__(self) -> None:
        if self.mode not in ("all", "any"):
            raise ValidationError(f"a group is 'all' or 'any', not {self.mode!r}")
        if not self.items:
            raise ValidationError("a group needs at least one condition")

    def conditions(self) -> list[C]:
        """All conditions of the tree, depth first."""
        found: list[C] = []
        for item in self.items:
            if isinstance(item, Group):
                found.extend(item.conditions())
            else:
                found.append(item)
        return found

    @property
    def depth(self) -> int:
        return 1 + max((item.depth for item in self.items if isinstance(item, Group)), default=0)

    def holds(self, test: Callable[[C], bool]) -> bool:
        """Whether the tree holds, `test` telling whether a condition does."""
        results = (
            item.holds(test) if isinstance(item, Group) else test(item) for item in self.items
        )
        result = all(results) if self.mode == "all" else any(results)
        return result != self.negate


def check_limits[C](groups: Iterable[Group[C]]) -> None:
    """The trees of one rule: nested at most `MAX_DEPTH` deep, at most `MAX_CONDITIONS`
    conditions together. ValidationError otherwise."""
    trees = list(groups)
    if any(group.depth > MAX_DEPTH for group in trees):
        raise ValidationError(f"conditions may be nested at most {MAX_DEPTH} deep")
    if sum(len(group.conditions()) for group in trees) > MAX_CONDITIONS:
        raise ValidationError(f"a rule has at most {MAX_CONDITIONS} conditions")


def group_to_json[C](group: Group[C], condition: Callable[[C], JsonObject]) -> JsonObject:
    data: JsonObject = {
        group.mode: [
            group_to_json(item, condition) if isinstance(item, Group) else condition(item)
            for item in group.items
        ]
    }
    if group.negate:
        data["not"] = True
    return data


def group_from_json[C](
    data: JsonValue, condition: Callable[[JsonValue, str], C], where: str = "conditions"
) -> Group[C]:
    """The tree of `data`; `condition` reads one condition (its JSON and where it stands)."""
    object_ = require_object(data, where)
    modes = [mode for mode in ("all", "any") if mode in object_]
    if len(modes) != 1:
        raise ValidationError(f"{where}: a group has exactly one of 'all' and 'any'")
    mode: GroupMode = "all" if modes[0] == "all" else "any"
    unknown = sorted(set(object_) - {mode, "not"})
    if unknown:
        raise ValidationError(f"{where}: unknown key '{unknown[0]}'")
    negate = object_.get("not", False)
    if not isinstance(negate, bool):
        raise ValidationError(f"{where}.not: expected true or false")
    items = object_[mode]
    if not isinstance(items, list):
        raise ValidationError(f"{where}.{mode}: expected a list")
    parsed: list[C | Group[C]] = []
    for index, item in enumerate(items):
        place = f"{where}.{mode}[{index}]"
        if isinstance(item, dict) and ("all" in item or "any" in item):
            parsed.append(group_from_json(item, condition, place))
        else:
            parsed.append(condition(item, place))
    try:
        return Group(mode=mode, items=tuple(parsed), negate=negate)
    except ValidationError as error:
        raise ValidationError(f"{where}: {error}") from None
