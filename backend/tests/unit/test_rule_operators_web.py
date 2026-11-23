"""The web UI offers each condition the comparisons the core takes (`web/src/lib/rules/model.ts`,
`web/src/lib/mail-traits.ts`): a table that differs offers what saving refuses, or hides what it
takes. The OpenAPI document names only all operators, not those of each field (WT2-09)."""

import re
from pathlib import Path

from lekto.core.domain.rules import (
    _FIELD_OPERATORS,  # the table the core checks a condition against
    FIELD_TYPE_OPERATORS,
    ConditionField,
)

WEB = Path(__file__).resolve().parents[3] / "web" / "src" / "lib"


def _constants(source: str) -> dict[str, list[str]]:
    """`const NAME: readonly Operator[] = ['is', ...];` by name."""
    found = re.findall(r"^const (\w+): readonly \w+\[\] = \[([^\]]*)\];", source, re.M)
    return {name: re.findall(r"'(\w+)'", items) for name, items in found}


def _record(source: str, name: str, known: dict[str, list[str]]) -> dict[str, set[str]]:
    """The entries of `export const NAME: Record<…> = { key: value, … };`, each value a list of
    operators, a constant of the file or another table's entry (`MAIL_FIELD_OPERATORS.sender`)."""
    body = re.search(rf"export const {name}: Record<[^=]*= \{{(.*?)\n\}};", source, re.S)
    assert body, f"no table {name}"
    table: dict[str, set[str]] = {}
    for key, value in re.findall(r"^\t(\w+): (.+?),?$", body.group(1), re.M):
        if value.startswith("["):
            table[key] = set(re.findall(r"'(\w+)'", value))
        else:
            table[key] = set(known[value])
    return table


def _web_tables() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    traits = (WEB / "mail-traits.ts").read_text(encoding="utf-8")
    mail = _record(traits, "MAIL_FIELD_OPERATORS", _constants(traits))
    model = (WEB / "rules" / "model.ts").read_text(encoding="utf-8")
    known = _constants(model) | {
        f"MAIL_FIELD_OPERATORS.{field}": sorted(ops) for field, ops in mail.items()
    }
    return (
        _record(model, "CONDITION_FIELD_OPERATORS", known),
        _record(model, "FIELD_TYPE_OPERATORS", known),
    )


def test_each_condition_offers_the_comparisons_of_the_core() -> None:
    fields, _ = _web_tables()
    core = {
        field.value: {op.value for op in ops}
        for field, ops in _FIELD_OPERATORS.items()
        if field is not ConditionField.FIELD
    }
    assert "contact" in fields and "mail_subject" in fields  # the table is read
    assert fields == core


def test_a_custom_field_offers_the_comparisons_of_its_type() -> None:
    _, types = _web_tables()
    core = {kind.value: {op.value for op in ops} for kind, ops in FIELD_TYPE_OPERATORS.items()}
    assert "period" in types  # the table is read
    assert types == core
