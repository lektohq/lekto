"""Mail rules get the tree of conditions every rule has

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-05 14:00:00.000000

A mail rule's conditions are a tree as a document rule's (Tobi, 05.11.2026): groups of `all` or
`any`, each may be turned around (`not`), in the same JSON form (`{"all": [...]}`); NULL for a
rule without conditions (every mail). The list and its `any` become the tree's top group;
`mail_rules.any` goes. Postgres changes the table in place; SQLite builds it anew (nothing
refers to it), keeping its rows.

The downgrade turns a tree of conditions only, not turned around, back into the list and
`any`; a rule with subgroups or `not` cannot be told that way, so it goes.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "id",
    "mailbox_id",
    "name",
    "priority",
    "conditions",
    "parts",
    "user_id",
    "space_id",
    "text_type_id",
    "after",
    "move_to",
    "enabled",
    "disabled_reason",
    "created_at",
    "updated_at",
    "version",
)


def _rules(name: str = "mail_rules") -> sa.TableClause:
    return sa.table(
        name,
        sa.column("id", sa.Uuid()),
        sa.column("any", sa.Boolean()),
        sa.column("conditions", types.json_type()),
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _rebuild(tree=True)
        return
    op.alter_column("mail_rules", "conditions", existing_type=types.json_type(), nullable=True)
    _to_trees(_rules())
    op.drop_column("mail_rules", "any")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        _rebuild(tree=False)
        return
    op.add_column(
        "mail_rules",
        sa.Column("any", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    _to_lists(_rules())
    op.alter_column("mail_rules", "conditions", existing_type=types.json_type(), nullable=False)
    op.alter_column("mail_rules", "any", existing_type=sa.Boolean(), server_default=None)


def _to_trees(table: sa.TableClause) -> None:
    """The list and `any` of each rule as the top group of a tree; no conditions NULL."""
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.any, table.c.conditions)).all()
    for id_, any_, conditions in rows:
        items = [_condition(item) for item in conditions or ()]
        tree = {"any" if any_ else "all": items} if items else None
        connection.execute(
            sa.update(table)
            .where(table.c.id == id_)
            .values(conditions=sa.null() if tree is None else tree)
        )


def _to_lists(table: sa.TableClause) -> None:
    """A plain tree back as the list and `any`; a rule with subgroups or `not` goes."""
    connection = op.get_bind()
    rows = connection.execute(sa.select(table.c.id, table.c.conditions)).all()
    for id_, tree in rows:
        if tree is None:
            values: dict[str, Any] = {"any": False, "conditions": []}
        else:
            mode = "any" if "any" in tree else "all"
            items = tree[mode]
            if tree.get("not") or any("all" in item or "any" in item for item in items):
                connection.execute(sa.delete(table).where(table.c.id == id_))
                continue
            values = {"any": mode == "any", "conditions": [_flat(item) for item in items]}
        connection.execute(sa.update(table).where(table.c.id == id_).values(**values))


def _rebuild(*, tree: bool) -> None:
    """Build `mail_rules` anew on SQLite, with the tree (NULL allowed, no `any`) or as before;
    its rows are turned in a copy and stay."""
    connection = op.get_bind()
    count = int(connection.exec_driver_sql("SELECT count(*) FROM mail_rules").scalar() or 0)
    op.execute("CREATE TEMP TABLE _mail_rules_0062 AS SELECT * FROM mail_rules")
    if tree:
        _to_trees(_rules("_mail_rules_0062"))
    else:
        op.execute('ALTER TABLE _mail_rules_0062 ADD COLUMN "any" BOOLEAN NOT NULL DEFAULT 0')
        _to_lists(_rules("_mail_rules_0062"))
        count = int(
            connection.exec_driver_sql("SELECT count(*) FROM _mail_rules_0062").scalar() or 0
        )
    op.drop_index(op.f("ix_mail_rules_mailbox_id"), table_name="mail_rules")
    op.drop_table("mail_rules")
    columns: list[sa.schema.SchemaItem] = [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("mailbox_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
    ]
    if not tree:
        columns.append(sa.Column("any", sa.Boolean(), nullable=False))
    columns += [
        sa.Column("conditions", types.json_type(), nullable=tree),
        sa.Column("parts", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("space_id", sa.Uuid(), nullable=True),
        sa.Column("text_type_id", sa.Uuid(), nullable=True),
        sa.Column("after", sa.Text(), nullable=False),
        sa.Column("move_to", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("disabled_reason", types.json_type(), nullable=True),
        sa.Column("created_at", types.UtcDateTime(), nullable=False),
        sa.Column("updated_at", types.UtcDateTime(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    ]
    op.create_table(
        "mail_rules",
        *columns,
        sa.ForeignKeyConstraint(
            ["mailbox_id"],
            ["mailboxes.id"],
            name=op.f("fk_mail_rules_mailbox_id_mailboxes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_rules")),
    )
    op.create_index(op.f("ix_mail_rules_mailbox_id"), "mail_rules", ["mailbox_id"])
    names = ", ".join(f'"{name}"' for name in (*_COLUMNS, *(() if tree else ("any",))))
    op.execute(f"INSERT INTO mail_rules ({names}) SELECT {names} FROM _mail_rules_0062")
    op.execute("DROP TABLE _mail_rules_0062")
    copied = connection.exec_driver_sql("SELECT count(*) FROM mail_rules").scalar()
    if copied != count:
        raise RuntimeError(f"revision 0062 copied {copied} of {count} mail rules")


def _condition(item: dict[str, Any]) -> dict[str, Any]:
    """A condition in the tree's form: no `value` where it has none."""
    found = {"field": item["field"], "op": item["op"]}
    if item.get("value") is not None:
        found["value"] = item["value"]
    return found


def _flat(item: dict[str, Any]) -> dict[str, Any]:
    return {"field": item["field"], "op": item["op"], "value": item.get("value")}
