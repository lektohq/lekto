import zlib
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).parent


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--shard",
        metavar="K/N",
        help="run only the K-th of N parts of the tests, split by their ids (CI runs the parts "
        "side by side)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark tests by directory: `tests/unit` is `unit`, `tests/integration` is `integration`.
    With `--shard K/N`, keep only the tests of part K."""
    for item in items:
        relative = Path(item.path).relative_to(_TESTS_DIR)
        kind = relative.parts[0]
        if kind not in {"unit", "integration"}:
            raise pytest.UsageError(f"{relative}: tests belong in tests/unit or tests/integration")
        item.add_marker(getattr(pytest.mark, kind))
    shard = config.getoption("--shard")
    if shard:
        part, parts = _shard(shard)
        # By a hash of the id: the same part in every xdist worker and in every run.
        kept: list[pytest.Item] = []
        left: list[pytest.Item] = []
        for item in items:
            mine = zlib.crc32(item.nodeid.encode()) % parts == part - 1
            (kept if mine else left).append(item)
        config.hook.pytest_deselected(items=left)
        items[:] = kept


def _shard(value: str) -> tuple[int, int]:
    try:
        part, parts = (int(number) for number in value.split("/"))
    except ValueError:
        part = parts = 0
    if not 1 <= part <= parts:
        raise pytest.UsageError(f"--shard {value}: expected K/N with 1 <= K <= N")
    return part, parts
