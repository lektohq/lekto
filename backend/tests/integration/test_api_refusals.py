"""What the running API refuses before it reaches the database, on SQLite and on Postgres."""

from collections.abc import AsyncIterator

import pytest

from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.outbound.sql import Database
from lekto.core.domain.users import Role
from lekto.core.ports.object_store import ObjectStore
from tests.api import auth
from tests.integration.e2e import System, running_system


@pytest.fixture
async def system(stores: tuple[Database, ObjectStore]) -> AsyncIterator[System]:
    async with running_system(System, stores) as running:
        yield running


async def test_a_nul_in_a_text_is_a_422_not_a_500(system: System) -> None:
    """Postgres takes no NUL in `text` nor in `jsonb`: its driver's error was a 500 (RB-08)."""
    admin = await system.user(Role.ADMIN)
    id = await system.upload(admin, "Invoice")
    for method, path, body in (
        ("POST", "/tags", {"name": "a\x00b"}),
        ("POST", "/spaces", {"name": "a\x00b"}),
        ("POST", "/fields", {"name": "Plan", "data_type": "choice", "choices": ["a\x00b"]}),
        ("PATCH", f"/documents/{id}", {"title": "a\x00b"}),
    ):
        response = await system.client.request(
            method, PREFIX + path, json=body, headers=auth(admin)
        )
        assert response.status_code == 422, (path, response.text)
        assert "NUL" in response.json()["detail"], path
