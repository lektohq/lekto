"""Every adapter class names its port among its bases (`class S3ObjectStore(ObjectStore)`), and
`adapters/outbound/README.md` lists every port with its adapters as the classes declare them
(.knowledge/decisions/2026-11-26-explicit-ports.md). The test imports the modules: what it lists
is what Python sees, not what the source text suggests."""

import importlib
import inspect
import pkgutil
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import is_protocol

import lekto.adapters.outbound as outbound
import lekto.core.ports as ports

OUTBOUND = Path(outbound.__file__).parent
README = OUTBOUND / "README.md"
START, END = "<!-- ports:start -->", "<!-- ports:end -->"


def _modules(package: ModuleType) -> Iterator[ModuleType]:
    """The modules of `package`, without the entry points of child processes and the Alembic
    revisions (importing those runs them)."""
    for info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
        if info.name.endswith(".__main__") or ".sql.migrations" in info.name:
            continue
        yield importlib.import_module(info.name)


def _defined(module: ModuleType) -> Iterator[type]:
    for value in vars(module).values():
        if inspect.isclass(value) and value.__module__ == module.__name__:
            yield value


def port_protocols() -> list[type]:
    """The protocols of `core/ports`, by module and in the order they are defined."""
    modules = sorted(_modules(ports), key=lambda module: module.__name__)
    return [cls for module in modules for cls in _defined(module) if is_protocol(cls)]


def adapters() -> dict[type, list[type]]:
    """The classes of `adapters/outbound` by the port they name among their bases."""
    found: dict[type, list[type]] = {}
    for module in _modules(outbound):
        for cls in _defined(module):
            if is_protocol(cls):
                continue
            for base in cls.__bases__:
                if is_protocol(base) and base.__module__.startswith(f"{ports.__name__}."):
                    found.setdefault(base, []).append(cls)
    return found


def _link(cls: type) -> str:
    path = Path(inspect.getfile(cls)).relative_to(OUTBOUND, walk_up=True).as_posix()
    return f"[`{cls.__name__}`]({path})"


def table() -> str:
    found = adapters()
    rows = ["| Port | Adapters |", "| --- | --- |"]
    for port in port_protocols():
        if port in found:
            classes = sorted(found[port], key=lambda cls: (cls.__module__, cls.__name__))
            rows.append(f"| {_link(port)} | {', '.join(_link(cls) for cls in classes)} |")
    return "\n".join(rows)


def test_the_ports_and_adapters_are_found() -> None:
    found = adapters()
    names = {port.__name__: {cls.__name__ for cls in found[port]} for port in found}
    assert {"S3ObjectStore", "FilesystemObjectStore", "MemoryObjectStore"} <= names["ObjectStore"]
    assert {"SqlUnitOfWork", "MemoryUnitOfWork"} <= names["UnitOfWork"]


def test_every_port_has_an_adapter() -> None:
    """A port no class names is only a base of other ports (`Repository`); any other has lost
    its adapter's declaration."""
    declared = set(adapters())
    protocols = port_protocols()
    bases = {base for port in protocols for base in port.__bases__}
    assert [port.__name__ for port in protocols if port not in declared | bases] == []


def test_the_readme_lists_the_ports_and_their_adapters() -> None:
    text = README.read_text(encoding="utf-8")
    assert START in text and END in text
    listed = text.split(START, 1)[1].split(END, 1)[0].strip()
    expected = table()
    assert listed == expected, f"Replace the table in {README} with:\n\n{expected}\n"
