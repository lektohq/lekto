"""The API on in-memory adapters (`support.Api`). Callers authenticate for real: test users get
an API token (`tests.api.auth`) or sign in with their password (`Api.sign_in`)."""

from collections.abc import AsyncIterator

import pytest

from lekto.adapters.outbound.memory import FAKE_VISION, FakeOcr
from tests.unit.adapters.rest.support import Api, api_with


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with api_with() as made:
        yield made


@pytest.fixture
async def vision_api() -> AsyncIterator[Api]:
    """The API with a vision language model (`FAKE_VISION`)."""
    async with api_with(adapters={"ocr": FakeOcr(vision=FAKE_VISION)}) as made:
        yield made
