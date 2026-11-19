"""How far work through documents a person selected has come, in the background: a rule
applied to them (`rules.RuleApplication`) or a bulk action (`bulk.BulkOperation`). Both go
through the same steps: one document after the other, each done, unchanged or skipped with
why, until they finish or fail ([[rule-dry-run]]: "the same machinery"; DB-06)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentId
from lekto.core.domain.reasons import Reason
from lekto.core.domain.validation import require_utc


class ProgressStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(kw_only=True)
class Progress:
    """`position`: how many of `documents` are done; `unchanged` of them were as the work wants
    them already, `skipped` left as they were, each with why."""

    documents: tuple[DocumentId, ...]
    status: ProgressStatus = ProgressStatus.QUEUED
    position: int = 0
    unchanged: int = 0
    skipped: list[tuple[DocumentId, Reason]] = field(default_factory=list)
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if not self.documents:
            raise ValidationError("select at least one document")
        if len(set(self.documents)) != len(self.documents):
            raise ValidationError("a document is selected twice")
        self.created_at = require_utc(self.created_at, "created_at")

    @property
    def remaining(self) -> tuple[DocumentId, ...]:
        return self.documents[self.position :]

    @property
    def finished(self) -> bool:
        return self.status in (ProgressStatus.DONE, ProgressStatus.FAILED)

    def record_unchanged(self) -> None:
        """One more document done: it was as the work wants it already."""
        self.unchanged += 1
        self._next()

    def record_skipped(self, document: DocumentId, reason: Reason) -> None:
        """One more document done: left as it was, for `reason`."""
        self.skipped.append((document, reason))
        self._next()

    def _next(self) -> None:
        self.position += 1
        self.status = ProgressStatus.RUNNING

    def finish(self, now: datetime, error: str | None = None) -> None:
        self.status = ProgressStatus.FAILED if error else ProgressStatus.DONE
        self.error = error
        self.finished_at = require_utc(now, "finished_at")
