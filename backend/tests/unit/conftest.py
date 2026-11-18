import logging
import os
from collections.abc import Iterator

import pytest
import structlog

from tests.builders import SECRET_KEY, TRUSTED_PROXY

NOT_ROOT = 1000


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The process environment (devcontainer, CI) must not leak into unit tests."""
    for name in list(os.environ):
        if name.upper().startswith("LEKTO_"):
            monkeypatch.delenv(name)
    # Required for the API; tests that check the requirement remove it.
    monkeypatch.setenv("LEKTO_SECRET_KEY", SECRET_KEY)
    monkeypatch.setenv("LEKTO_FORWARDED_ALLOW_IPS", TRUSTED_PROXY)
    # `lekto` stops as root unless `PUID=0` means it: whoever runs pytest, it runs as a user
    # here (TC-05); the test of that check sets the uid itself.
    monkeypatch.delenv("PUID", raising=False)
    monkeypatch.setattr(os, "geteuid", lambda: NOT_ROOT)


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:], root.level = handlers, level
    structlog.reset_defaults()
