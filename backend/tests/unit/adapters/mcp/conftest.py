"""The fixtures of the MCP tests: the API with the endpoint, and a scene of users and documents."""

from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from lekto.composition.settings import Settings
from lekto.core.domain.ids import DocumentId
from lekto.core.services.objects import text_key
from tests.unit.adapters.mcp.support import TEXT, running
from tests.unit.adapters.rest.support import Api, Scene, api_with, indexed_scene


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    """The API with the MCP endpoint, its lifespan running."""
    # A piece of text holds 100 characters (`LEKTO_MCP_TEXT_MAX`).
    settings = Settings.model_construct(mcp_text_max=100)
    async with api_with(settings=settings, mcp=True) as made, running(made.app):
        yield made


@pytest.fixture
async def scene(api: Api) -> Scene:
    scene = await indexed_scene(api)
    for which in (scene.green, scene.yellow):
        await api.container.object_store.put(
            text_key(DocumentId(UUID(which))),
            TEXT.encode(),
            content_type="text/markdown",
        )
    return scene
