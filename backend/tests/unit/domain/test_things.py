"""The nouns a reason names are the ones `Thing` lists (`x-things` for the clients).

A client words a reason's `thing` in its language from that list. A noun the core writes
without listing it stands in English in a translated sentence, so the code is read for them:
what a `NotFoundError` is of, what a repository keeps, what a name is the name of, and the
families that come from other enumerations.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

import lekto
from lekto.core.domain.mail import MailAction
from lekto.core.domain.master_data import TagScope
from lekto.core.domain.reasons import PARAMETERS, ReasonCode, Thing, because
from lekto.core.services.documents import DocumentFile

SOURCES = Path(lekto.__file__).parent
THINGS = {thing.value for thing in Thing}
# Functions whose text argument says what a name is the name of (`NAME_EMPTY`, `NAME_TOO_LONG`).
NAMING = {"require_name"}
# Not a noun: the program a process could not start.
NO_NOUN_FILES = {"adapters/outbound/system/process.py"}


def _text(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _thing_parameters() -> dict[str, set[str]]:
    """The parameters of the kind `thing`, by the name of the reason's code."""
    return {
        code.name: {name for name, kind in kinds.items() if kind == "thing"}
        for code, kinds in PARAMETERS.items()
        if "thing" in kinds.values()
    }


def _nouns_in_code() -> dict[str, str]:
    """Every noun written as a text in the code, with a place it stands at."""
    things = _thing_parameters()
    found: dict[str, str] = {}
    for path in sorted(SOURCES.rglob("*.py")):
        place = path.relative_to(SOURCES).as_posix()
        if place in NO_NOUN_FILES:
            continue
        memory = place.startswith("adapters/outbound/memory/")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            for noun in _nouns_of(node, things, memory=memory):
                found.setdefault(noun, f"{place}:{getattr(node, 'lineno', 0)}")
    return found


def _nouns_of(node: ast.AST, things: dict[str, set[str]], *, memory: bool) -> Iterator[str]:
    if isinstance(node, ast.Call):
        name = getattr(node.func, "id", getattr(node.func, "attr", ""))
        if name.endswith("NotFoundError") and node.args:
            yield from _some(_text(node.args[0]))
        elif name in ("because", "_because") and node.args:
            code = ast.unparse(node.args[0]).removeprefix("ReasonCode.").strip("'\"")
            for keyword in node.keywords:
                if keyword.arg in things.get(code, ()):
                    yield from _some(_text(keyword.value))
        elif name in NAMING:
            for argument in [*node.args[1:], *(keyword.value for keyword in node.keywords)]:
                yield from _some(_text(argument))
        elif memory and name == "Table" and node.args:
            # A table of the memory adapter is named as its repository's `kind`.
            yield from _some(_text(node.args[0]))
    elif isinstance(node, ast.FunctionDef) and node.name in NAMING:
        # What a name is called when the caller does not say.
        for default in node.args.defaults:
            yield from _some(_text(default))
    elif isinstance(node, ast.Assign | ast.AnnAssign):
        target = node.targets[0] if isinstance(node, ast.Assign) else node.target
        if getattr(target, "id", "") == "kind" and node.value is not None:
            # What a repository keeps, as its `NotFoundError` says it.
            yield from _some(_text(node.value))


def _some(noun: str | None) -> Iterator[str]:
    if noun is not None:
        yield noun


def test_the_code_names_no_thing_the_list_lacks() -> None:
    written = _nouns_in_code()
    # The reading finds what it is meant to find.
    assert {"document", "space name", "API token", "mailbox", "name"} <= set(written)
    assert {noun: place for noun, place in written.items() if noun not in THINGS} == {}


def test_the_families_of_other_enumerations_are_listed() -> None:
    assert {file.value for file in DocumentFile} <= THINGS
    assert {scope.label for scope in TagScope} <= THINGS
    assert {f"mail_step:{action.value}" for action in MailAction} <= THINGS


def test_a_reason_reads_a_thing_as_it_is_written() -> None:
    reason = because(ReasonCode.NOT_FOUND, kind=Thing.MAIL_RULE.value, id="12345")
    assert reason.text == "mail rule 12345 not found"
