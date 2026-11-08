"""One contract number: policy, membership and loan numbers become contract numbers

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-08 14:00:00.000000

Issue #215 (Tobi, 08.11.2026): a policy, a membership and a loan are contracts; one kind holds
their numbers. Every stored value of the kinds `policy_number`, `membership_number` and
`loan_number` becomes a `contract_number`: the identifiers of contacts and of persons' profiles
(and those a person declined), the facts of documents, the fact conditions of rules (also of
mail rules), the fact criteria of lenses and the evidence of relations.

Where a value stands twice after that, one stays: at contacts the one a person decided (entered
before rejected before learned; one already a contract number first), in a profile and among a
document's facts the one a person decided (a document's fact whose state is not `found`), else
the one already a contract number. Processing logs keep the kinds they recorded.

The downgrade changes nothing: which kind a contract number was before is gone.
"""

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0071"
down_revision: str | None = "0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONTRACT = "contract_number"
MERGED = ("policy_number", "membership_number", "loan_number")
KINDS = (CONTRACT, *MERGED)
_SOURCES = {"manual": 0, "rejected": 1, "learned": 2}


def upgrade() -> None:
    bind = op.get_bind()
    _contact_identifiers(bind)
    for name in ("user_identifiers", "user_declined_identifiers"):
        _per_owner(bind, name, "user_id", decided=None)
    _per_owner(bind, "document_facts", "document_id", decided="state")
    _json(bind, "rule_versions", ("rule_id", "number"), "conditions", _conditions)
    _json(bind, "mail_rules", ("id",), "conditions", _conditions)
    _json(bind, "lenses", ("id",), "filter", _lens_filter)
    _relations(bind)


def downgrade() -> None:
    pass


def _contact_identifiers(bind: sa.Connection) -> None:
    """Kind and value are unique across all contacts: per value one row stays."""
    table = sa.table(
        "contact_identifiers", sa.column("kind"), sa.column("value"), sa.column("source")
    )
    rows = bind.execute(
        sa.select(table.c.kind, table.c.value, table.c.source).where(table.c.kind.in_(KINDS))
    ).all()
    by_value: dict[str, list[Any]] = defaultdict(list)
    for row in rows:
        by_value[row.value].append(row)
    for value, found in by_value.items():
        kept = min(found, key=lambda row: (_SOURCES.get(row.source, 3), row.kind != CONTRACT))
        for row in found:
            if row is not kept:
                bind.execute(
                    table.delete().where((table.c.kind == row.kind) & (table.c.value == value))
                )
        if kept.kind != CONTRACT:
            bind.execute(
                table.update()
                .where((table.c.kind == kept.kind) & (table.c.value == value))
                .values(kind=CONTRACT)
            )


def _per_owner(bind: sa.Connection, name: str, owner: str, *, decided: str | None) -> None:
    """Kind and value are unique per owner (a user, a document)."""
    columns: list[sa.ColumnClause[Any]] = [sa.column(owner), sa.column("kind"), sa.column("value")]
    if decided is not None:
        columns.append(sa.column(decided))
    table = sa.table(name, *columns)
    rows = bind.execute(sa.select(*table.c).where(table.c.kind.in_(KINDS))).all()
    by_key: dict[tuple[Any, str], list[Any]] = defaultdict(list)
    for row in rows:
        by_key[(getattr(row, owner), row.value)].append(row)

    def rank(row: Any) -> tuple[bool, bool]:
        undecided = decided is None or getattr(row, decided) == "found"
        return (undecided, row.kind != CONTRACT)

    for (who, value), found in by_key.items():
        kept = min(found, key=rank)
        mine = (table.c[owner] == who) & (table.c.value == value)
        for row in found:
            if row is not kept:
                bind.execute(table.delete().where(mine & (table.c.kind == row.kind)))
        if kept.kind != CONTRACT:
            bind.execute(
                table.update().where(mine & (table.c.kind == kept.kind)).values(kind=CONTRACT)
            )


def _json(bind: sa.Connection, name: str, keys: tuple[str, ...], column: str, change: Any) -> None:
    """Rewrite a JSON column where `change` returns a changed value (None: unchanged)."""
    table = sa.table(name, *map(sa.column, keys), sa.column(column, types.json_type()))
    for row in bind.execute(sa.select(*(table.c[key] for key in keys), table.c[column])).all():
        changed = change(row[-1])
        if changed is not None:
            where = sa.and_(
                *(table.c[key] == value for key, value in zip(keys, row[:-1], strict=True))
            )
            bind.execute(table.update().where(where).values({column: changed}))


def _conditions(data: Any) -> Any:
    """A rule's conditions with every `fact_kind` of the merged kinds a contract number; None
    where nothing changes."""
    changed = False

    def walk(node: Any) -> Any:
        nonlocal changed
        if isinstance(node, dict):
            result = {key: walk(value) for key, value in node.items()}
            if result.get("fact_kind") in MERGED:
                result["fact_kind"] = CONTRACT
                changed = True
            return result
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    result = walk(data)
    return result if changed else None


def _lens_filter(data: Any) -> Any:
    """A lens's filter with the kind of each fact criterion of the merged kinds a contract
    number; None where nothing changes."""
    if not isinstance(data, dict) or not any(
        isinstance(item, dict) and item.get("kind") in MERGED for item in data.get("facts") or ()
    ):
        return None
    facts = [
        {**item, "kind": CONTRACT}
        if isinstance(item, dict) and item.get("kind") in MERGED
        else item
        for item in data["facts"]
    ]
    return {**data, "facts": facts}


def _relations(bind: sa.Connection) -> None:
    table = sa.table(
        "document_relations",
        sa.column("newer_id"),
        sa.column("older_id"),
        sa.column("evidence", types.json_type()),
    )
    for row in bind.execute(sa.select(table.c.newer_id, table.c.older_id, table.c.evidence)).all():
        changed = _conditions(row.evidence)
        if changed is not None:
            bind.execute(
                table.update()
                .where((table.c.newer_id == row.newer_id) & (table.c.older_id == row.older_id))
                .values(evidence=changed)
            )
