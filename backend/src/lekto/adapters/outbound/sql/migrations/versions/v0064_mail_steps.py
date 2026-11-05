"""Mail rules do steps on a mail on the server, in order

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-05 18:00:00.000000

What becomes of a mail on the server is an ordered list of steps (Tobi, 05.11.2026): read or
unread, flagged in a colour or not, a keyword added or removed, and at most one last that moves
it to a folder or to the trash. `mail_rules.steps` holds them as JSON; the one action a rule had
becomes its list (`nothing`: none, `move` with `move_to`), and `after` and `move_to` go. A
mailbox keeps when a step last failed and why (`step_failed_at`, `step_failed`).

The columns have no keys, so SQLite adds and drops them in place. The downgrade gives a rule
the last of its steps that was an action before (move, trash, read), or nothing.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_rules = sa.table(
    "mail_rules",
    sa.column("id", sa.Uuid()),
    sa.column("after", sa.Text()),
    sa.column("move_to", sa.Text()),
    sa.column("steps", types.json_type()),
)


def upgrade() -> None:
    op.add_column(
        "mail_rules", sa.Column("steps", types.json_type(), nullable=False, server_default="[]")
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(_rules.c.id, _rules.c.after, _rules.c.move_to)).all()
    for id_, after, move_to in rows:
        steps: list[dict[str, Any]] = []
        if after == "move" and move_to:
            steps = [{"action": "move", "value": move_to}]
        elif after in ("read", "trash"):
            steps = [{"action": after}]
        connection.execute(sa.update(_rules).where(_rules.c.id == id_).values(steps=steps))
    # Not batch operations: on SQLite, they would copy the table.
    op.drop_column("mail_rules", "move_to")
    op.drop_column("mail_rules", "after")
    op.add_column("mailboxes", sa.Column("step_failed_at", types.UtcDateTime(), nullable=True))
    op.add_column("mailboxes", sa.Column("step_failed", types.json_type(), nullable=True))


def downgrade() -> None:
    op.drop_column("mailboxes", "step_failed")
    op.drop_column("mailboxes", "step_failed_at")
    op.add_column(
        "mail_rules", sa.Column("after", sa.Text(), nullable=False, server_default="nothing")
    )
    op.add_column("mail_rules", sa.Column("move_to", sa.Text(), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.select(_rules.c.id, _rules.c.steps)).all()
    for id_, steps in rows:
        kept = [step for step in steps or () if step.get("action") in ("move", "trash", "read")]
        last = kept[-1] if kept else {"action": "nothing"}
        connection.execute(
            sa.update(_rules)
            .where(_rules.c.id == id_)
            .values(after=last["action"], move_to=last.get("value"))
        )
    op.drop_column("mail_rules", "steps")
