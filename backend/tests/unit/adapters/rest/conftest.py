"""The API on in-memory adapters (`support.Api`). Callers authenticate for real: test users get
an API token (`tests.api.auth`) or sign in with their password (`Api.sign_in`)."""

import dataclasses
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import httpx2
import pytest

from lekto.adapters.outbound.memory import FAKE_VISION, FakeOcr, ManualClock
from lekto.composition.container import Container, build_memory_container, build_services
from lekto.core.ports.clock import Clock
from tests import builders
from tests.unit.adapters.rest.support import Api, make_app


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with _api(build_memory_container) as made:
        yield made


@pytest.fixture
async def vision_api() -> AsyncIterator[Api]:
    """The API with a vision language model (`FAKE_VISION`)."""

    def container(clock: Clock) -> Container:
        return dataclasses.replace(build_memory_container(clock), ocr=FakeOcr(vision=FAKE_VISION))

    async with _api(container) as made:
        yield made


@asynccontextmanager
async def _api(container: Callable[[Clock], Container]) -> AsyncIterator[Api]:
    clock = ManualClock(builders.NOW)
    built = container(clock)
    services = build_services(built)
    builders.skip_classification(services.pipeline)
    app = make_app(built, services)
    transport = httpx2.ASGITransport(app=app)
    async with httpx2.AsyncClient(transport=transport, base_url="https://lekto") as client:
        yield Api(built, services, app, client, clock)
