"""The jobs of a kind due first

Revision ID: 0080
Revises: 0079
Create Date: 2026-11-19 14:00:00.000000

A worker claims the jobs of each kind it runs on its own; the indexes knew only the status
and when a job is due, so with thousands of jobs of one kind waiting (a rebuild of the search
index) every claim of another kind read them all. An index of kind, status, due time and id (the
order a claim takes them in) lets each claim read one row (SQ-07).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0080"
down_revision: str | None = "0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_jobs_kind_status_run_at_id"), "jobs", ["kind", "status", "run_at", "id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_kind_status_run_at_id"), table_name="jobs")
