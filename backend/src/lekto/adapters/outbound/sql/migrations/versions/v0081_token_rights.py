"""API tokens carry rights instead of a scope

Revision ID: 0081
Revises: 0080
Create Date: 2026-11-19 16:00:00.000000

An API token carries the rights it may use, by area and the admin rights one by one (Tobi,
19.11.2026, `.knowledge/plans/token-rights.md`); its scope (`read`, `read_write`, `upload`)
becomes a preset. Each token gets the rights of its scope, an admin's token of `read` or
`read_write` with every admin right, so that it may what it may now. Bulk operations and
rule applications keep the rights they were started with (none for those started before, which
work with every right of their user, as they did). The downgrade gives a token the scope whose
rights it holds, else `read` (a token with rights chosen one by one may only read then).
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0081"
down_revision: str | None = "0080"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The rights as of this revision; a later right is not part of these presets.
_READ = [
    "documents:count",
    "documents:read",
    "lenses:read",
    "master_data:read",
    "push:read",
    "rules:read",
    "spaces:read",
    "system:read",
    "webhooks:read",
]
_AREAS = sorted(
    [
        *_READ,
        "documents:upload",
        "documents:write",
        "lenses:write",
        "master_data:write",
        "push:write",
        "rules:write",
        "spaces:write",
        "system:write",
        "webhooks:write",
    ]
)
_ADMIN = [
    "admin:count_all",
    "admin:documents_all",
    "admin:mailboxes",
    "admin:manage",
    "admin:private_webhooks",
]
_UPLOAD = ["documents:upload"]


def _rights(scope: str, admin: bool) -> list[str]:
    match scope:
        case "upload":
            return _UPLOAD
        case "read":
            return sorted(_READ + _ADMIN) if admin else _READ
        case _:
            return sorted(_AREAS + _ADMIN) if admin else _AREAS


def _scope(rights: list[str]) -> str:
    chosen = sorted(rights)
    for scope in ("upload", "read", "read_write"):
        if chosen in (_rights(scope, False), _rights(scope, True)):
            return scope
    return "read"


def upgrade() -> None:
    op.add_column("api_tokens", sa.Column("rights", types.json_type(), nullable=True))
    tokens = sa.table(
        "api_tokens",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("scope", sa.Text()),
        sa.column("rights", types.json_type()),
    )
    users = sa.table("users", sa.column("id", sa.Uuid()), sa.column("role", sa.Text()))
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(tokens.c.id, tokens.c.scope, users.c.role).join(
            users, users.c.id == tokens.c.user_id
        )
    ).all()
    for id, scope, role in rows:
        connection.execute(
            tokens.update().where(tokens.c.id == id).values(rights=_rights(scope, role == "admin"))
        )
    with op.batch_alter_table("api_tokens") as batch:
        batch.alter_column("rights", existing_type=types.json_type(), nullable=False)
        batch.drop_column("scope")
    for table in ("bulk_operations", "rule_applications"):
        op.add_column(table, sa.Column("rights", types.json_type(), nullable=True))


def downgrade() -> None:
    for table in ("bulk_operations", "rule_applications"):
        op.drop_column(table, "rights")
    op.add_column("api_tokens", sa.Column("scope", sa.Text(), nullable=True))
    tokens = sa.table(
        "api_tokens",
        sa.column("id", sa.Uuid()),
        sa.column("scope", sa.Text()),
        sa.column("rights", types.json_type()),
    )
    connection = op.get_bind()
    for id, rights in connection.execute(sa.select(tokens.c.id, tokens.c.rights)).all():
        stored = json.loads(rights) if isinstance(rights, str) else rights
        connection.execute(
            tokens.update().where(tokens.c.id == id).values(scope=_scope(list(stored or [])))
        )
    with op.batch_alter_table("api_tokens") as batch:
        batch.alter_column("scope", existing_type=sa.Text(), nullable=False)
        batch.drop_column("rights")
