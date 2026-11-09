"""The OpenAPI document the web UI's client is generated from (`web/openapi.json`)."""

from pathlib import Path
from typing import Any

from lekto.adapters.inbound.limits import MAX_SELECTED, in_words
from lekto.composition.openapi import main, openapi_document, render
from lekto.core.domain.inbox import DONE_PERIOD
from lekto.core.services.places import PLACES
from lekto.core.services.stream import LIMIT as STREAM_LIMIT

CHECKED_IN = Path(__file__).resolve().parents[3] / "web" / "openapi.json"


def test_the_web_ui_has_the_current_openapi_document() -> None:
    assert CHECKED_IN.read_text(encoding="utf-8") == render(openapi_document()), (
        "web/openapi.json is out of date: run `uv run python -m lekto.composition.openapi "
        "../web/openapi.json` in backend/, then `pnpm gen:api` in web/"
    )


def test_the_command_writes_the_document(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    assert main([str(target)]) == 0
    assert target.read_text(encoding="utf-8") == render(openapi_document())


def test_the_command_refuses_extra_arguments() -> None:
    assert main(["a", "b"]) == 2


def test_the_descriptions_take_their_numbers_from_the_constants() -> None:
    """A limit changed in the code changes the text clients read: these are interpolated."""
    paths: Any = openapi_document()["paths"]
    ids = next(
        each for each in paths["/api/v1/documents"]["get"]["parameters"] if each["name"] == "ids"
    )
    assert ids["schema"]["anyOf"][0]["maxItems"] == MAX_SELECTED
    assert f"the last {DONE_PERIOD.days} days" in paths["/api/v1/inbox"]["get"]["description"]
    assert (
        f"the {STREAM_LIMIT} newest documents"
        in (paths["/api/v1/documents/stream"]["get"]["description"])
    )
    assert (
        f"at most {in_words(PLACES)}:"
        in (paths["/api/v1/identifiers/places/{kind}/{ref}"]["get"]["description"])
    )


def test_numbers_up_to_ten_are_written_as_words() -> None:
    assert [in_words(number) for number in (0, 5, 10, 11)] == ["zero", "five", "ten", "11"]
