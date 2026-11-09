"""The core hands out links without knowing the prefixes (review 0.12.2, C-05): no literal of
the API's or the web UI's prefix stands in it, and every page of the web UI it links to exists."""

import re
from pathlib import Path

from lekto.core.domain import links

CORE = Path(__file__).resolve().parents[2] / "src" / "lekto" / "core"
ROUTES = Path(__file__).resolve().parents[3] / "web" / "src" / "routes" / "(app)"
PREFIX_LITERAL = re.compile(r"""["'](?:/api/v1|/ui)(?:/|["'?])""")
UI_PATHS = [
    links.HOME,
    links.DOCUMENT,
    links.INBOX,
    links.NOTIFICATIONS,
    links.MAILBOX,
    links.WEBHOOK,
    links.JOBS,
]


def test_the_core_names_no_prefix() -> None:
    found = [
        f"{path.relative_to(CORE)}:{number}"
        for path in sorted(CORE.rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if PREFIX_LITERAL.search(line)
    ]
    assert found == []


def test_every_page_the_core_links_to_is_a_route_of_the_web_ui() -> None:
    for path in UI_PATHS:
        route = re.sub(r"\{(\w+)\}", r"[\1]", path.split("?")[0]).strip("/")
        assert (ROUTES / route / "+page.svelte").is_file(), path


def test_links_put_the_prefixes_and_the_public_url_in_front() -> None:
    made = links.Links(public="https://lekto.example/", api_prefix="/api", ui_prefix="/app")
    assert (
        made.api(links.TASK_RESULT.format(id="t"))
        == "https://lekto.example/api/external/tasks/t/result"
    )
    assert made.ui(links.INBOX) == "/app/inbox"
    assert (
        made.ui_absolute(links.DOCUMENT.format(id="d")) == "https://lekto.example/app/documents/d"
    )
    nowhere = links.Links(public=None, api_prefix="/api", ui_prefix="/app")
    assert (nowhere.api(links.TASKS), nowhere.ui_absolute(links.HOME)) == (None, None)
