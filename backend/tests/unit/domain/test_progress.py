"""Working through selected documents in the background: a rule applied to them and a bulk
action count alike (DB-06)."""

from collections.abc import Callable

import pytest

from lekto.core.domain.bulk import BulkAction, BulkKind, BulkOperation
from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentId, RuleId, UserId, new_id
from lekto.core.domain.progress import Progress, ProgressStatus
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.rules import RuleApplication
from tests.builders import NOW


def documents(count: int) -> tuple[DocumentId, ...]:
    return tuple(DocumentId(new_id()) for _ in range(count))


def makers(selected: tuple[DocumentId, ...]) -> list[Callable[[], Progress]]:
    user = UserId(new_id())
    return [
        lambda: RuleApplication.create(
            rule_id=RuleId(new_id()),
            rule_version=1,
            user_id=user,
            documents=selected,
            accept_conflicts=frozenset(),
            now=NOW,
        ),
        lambda: BulkOperation.create(
            user_id=user, action=BulkAction(BulkKind.CONFIRM), documents=selected, now=NOW
        ),
    ]


def test_both_go_through_the_documents_one_after_the_other() -> None:
    selected = documents(3)
    skipped = because(ReasonCode.SKIP_NOT_AVAILABLE)
    for make in makers(selected):
        progress = make()
        assert (progress.status, progress.remaining) == (ProgressStatus.QUEUED, selected)
        progress.record_unchanged()
        progress.record_skipped(selected[1], skipped)
        assert (progress.status, progress.position) == (ProgressStatus.RUNNING, 2)
        assert (progress.unchanged, progress.skipped, progress.remaining) == (
            1,
            [(selected[1], skipped)],
            selected[2:],
        )
        assert not progress.finished
        progress.finish(NOW, error="broken")
        assert (progress.status, progress.error, progress.finished) == (
            ProgressStatus.FAILED,
            "broken",
            True,
        )


@pytest.mark.parametrize("selected", [(), (DocumentId(new_id()),) * 2])
def test_both_need_documents_each_once(selected: tuple[DocumentId, ...]) -> None:
    for make in makers(selected):
        with pytest.raises(ValidationError):
            make()
