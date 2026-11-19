"""Every service runs the kinds of jobs it names (`job_kinds`, by which the worker wakes it),
and no other: a kind in one of two lists alone would never run or never wake it (SA-09)."""

from collections.abc import Sequence
from dataclasses import fields
from typing import Any

import pytest

from lekto.composition.container import build_memory_container, build_services
from lekto.core.services._jobs import JobRunner


async def test_every_service_runs_the_kinds_it_names(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    async def run_next(self: JobRunner, kinds: Sequence[str], *args: Any) -> bool:
        asked.extend(kinds)
        return False

    monkeypatch.setattr(JobRunner, "run_next", run_next)
    services = build_services(build_memory_container())
    named = 0
    for field in fields(services):
        service = getattr(services, field.name)
        kinds = getattr(service, "job_kinds", None)
        if kinds is None:
            continue
        named += 1
        asked.clear()
        assert not await service.run_next_job()
        assert sorted(asked) == sorted(kinds), field.name
    assert named >= 10  # the services are found
