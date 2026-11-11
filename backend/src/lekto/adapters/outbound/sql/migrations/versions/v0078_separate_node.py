"""The node `separate` between `receive` and `ocr`/`pages`

Revision ID: 0078
Revises: 0077
Create Date: 2026-11-11 12:00:00.000000

A scanned stack is split at its separator sheets when it comes in (Tobi, 10.11.2026;
Umsetzungsplan "Trennblatt und Zusammenführen"), in a node before OCR and the page images. Every
document came in before it and gets it `skipped`, as revision 0050 did for `relate`: nothing
waits on it, and nothing is split after the fact.

The downgrade drops the node from the states, the log, the jobs and the undelivered events; a
document whose `separate` had not run yet gets jobs for OCR and the page images. A version made
of a stack's first part (`separated`) counts as an edited one.
"""

import os
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

from lekto.adapters.outbound.sql import types

revision: str = "0078"
down_revision: str | None = "0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEPARATE = "separate"
_AFTER = ("ocr", "pages")
_NODE_JOBS = ("pipeline.node", "pipeline.catch_up")
_NODE_EVENTS = ("document.node_started", "document.node_completed", "document.node_deferred")
_ACTIVE = ("queued", "running")

_documents = sa.table(
    "documents",
    sa.column("id", sa.Uuid()),
    sa.column("processing_run", sa.Integer()),
    sa.column("processing_nodes", types.json_type()),
)
_versions = sa.table("document_versions", sa.column("kind", sa.Text()))
_log = sa.table("processing_log", sa.column("node", sa.Text()))
_jobs = sa.table(
    "jobs",
    sa.column("id", sa.Uuid()),
    sa.column("kind", sa.Text()),
    sa.column("payload", types.json_type()),
    sa.column("dedup_key", sa.Text()),
    sa.column("status", sa.Text()),
    sa.column("attempts", sa.Integer()),
    sa.column("releases", sa.Integer()),
    sa.column("run_at", types.UtcDateTime()),
)
_outbox = sa.table(
    "outbox",
    sa.column("seq"),
    sa.column("type", sa.Text()),
    sa.column("payload", types.json_type()),
)


def upgrade() -> None:
    connection = op.get_bind()
    for row in connection.execute(sa.select(_documents.c.id, _documents.c.processing_nodes)):
        nodes = dict(row.processing_nodes or {})
        nodes[_SEPARATE] = _state("skipped")
        _store(connection, row.id, nodes)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.update(_versions).where(_versions.c.kind == "separated").values(kind="edited")
    )
    connection.execute(sa.delete(_log).where(_log.c.node == _SEPARATE))
    for row in connection.execute(
        sa.select(_jobs.c.id, _jobs.c.payload).where(_jobs.c.kind.in_(_NODE_JOBS))
    ).mappings():
        if _node_of(row["payload"]) == _SEPARATE:
            connection.execute(sa.delete(_jobs).where(_jobs.c.id == row["id"]))
    for row in connection.execute(
        sa.select(_outbox.c.seq, _outbox.c.payload).where(_outbox.c.type.in_(_NODE_EVENTS))
    ).mappings():
        if _node_of(row["payload"]) == _SEPARATE:
            connection.execute(sa.delete(_outbox).where(_outbox.c.seq == row["seq"]))
    waiting = []
    for row in connection.execute(sa.select(_documents)).mappings():
        nodes = dict(row["processing_nodes"] or {})
        separate = nodes.pop(_SEPARATE, {})
        if separate.get("status") in ("waiting", "running"):
            waiting.append((row["id"], row["processing_run"]))
        _store(connection, row["id"], nodes)
    for document, run in waiting:
        for node in _AFTER:
            if not _has_job(connection, document, run, node):
                _queue(connection, document, run, node)


def _state(status: str) -> dict[str, Any]:
    return {"status": status, "outcome": None, "started_at": None, "finished_at": None}


def _store(connection: sa.Connection, document: Any, nodes: dict[str, Any]) -> None:
    connection.execute(
        sa.update(_documents).where(_documents.c.id == document).values(processing_nodes=nodes)
    )


def _node_of(payload: Any) -> str | None:
    node = payload.get("node") if isinstance(payload, dict) else None
    return node if isinstance(node, str) else None


def _has_job(connection: sa.Connection, document: Any, run: int, node: str) -> bool:
    found = connection.execute(
        sa.select(_jobs.c.id).where(
            _jobs.c.dedup_key == f"{document}:{run}:{node}", _jobs.c.status.in_(_ACTIVE)
        )
    ).first()
    return found is not None


def _queue(connection: sa.Connection, document: Any, run: int, node: str) -> None:
    connection.execute(
        sa.insert(_jobs).values(
            id=_new_id(),
            kind="pipeline.node",
            payload={"document_id": str(document), "node": node, "run": run},
            dedup_key=f"{document}:{run}:{node}",
            status="queued",
            attempts=0,
            releases=0,
            run_at=datetime.now(UTC),
        )
    )


def _new_id() -> uuid.UUID:
    """A UUIDv7, as `lekto.core.domain.ids.new_id` makes it today (a revision keeps its own
    copy)."""
    milliseconds = time.time_ns() // 1_000_000 & ((1 << 48) - 1)
    random = int.from_bytes(os.urandom(10))
    value = milliseconds << 80 | random
    value = value & ~(0xF << 76) | 0x7 << 76  # version 7
    value = value & ~(0x3 << 62) | 0x2 << 62  # variant RFC 9562
    return uuid.UUID(int=value)
