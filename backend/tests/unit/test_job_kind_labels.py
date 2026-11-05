"""Every kind of job the worker runs has a name in the web UI (`web/src/lib/jobs.ts`), so the
jobs page never shows a bare key such as `mail.fetch`."""

import re
from dataclasses import fields
from pathlib import Path

from lekto.composition.container import build_memory_container, build_services

LABELS = Path(__file__).resolve().parents[3] / "web" / "src" / "lib" / "jobs.ts"


def test_every_job_kind_has_a_name_in_the_web_ui() -> None:
    services = build_services(build_memory_container())
    kinds = {
        kind
        for field in fields(services)
        for kind in getattr(getattr(services, field.name), "job_kinds", ())
    }
    assert "mail.fetch" in kinds and "webhooks.deliver" in kinds  # the services are found
    named = set(re.findall(r"^\t'([a-z_]+\.[a-z_]+)':", LABELS.read_text(encoding="utf-8"), re.M))
    assert sorted(kinds - named) == []
