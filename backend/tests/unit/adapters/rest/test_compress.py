"""gzip for the answers that shrink (`Compress`): the web UI's files and the API's JSON."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from lekto.adapters.inbound.rest import PREFIX
from lekto.adapters.inbound.rest.middleware import COMPRESS_FROM, Compress
from tests.unit.adapters.rest.support import api_with

BODY = b'{"items": ["' + b"Muster " * 400 + b'"]}'
GZIP = {"Accept-Encoding": "gzip"}


def _app() -> Compress:
    """An app that answers every path with `BODY`, as the type `?type=` names it."""

    async def answer(request: Request) -> Response:
        size = int(request.query_params.get("size", len(BODY)))
        media = request.query_params.get("type", "application/json")
        return Response(BODY[:size], media_type=media)

    return Compress(Starlette(routes=[Route("/{path:path}", answer)]), plain=(f"{PREFIX}/auth/",))


@pytest.fixture
async def client() -> AsyncIterator[httpx2.AsyncClient]:
    transport = httpx2.ASGITransport(app=_app())
    async with httpx2.AsyncClient(transport=transport, base_url="https://lekto") as found:
        yield found


async def test_json_and_text_shrink_for_a_client_that_takes_gzip(
    client: httpx2.AsyncClient,
) -> None:
    for media in ("application/json", "text/html", "text/css", "text/javascript"):
        response = await client.get(f"{PREFIX}/documents", params={"type": media}, headers=GZIP)
        assert response.headers["content-encoding"] == "gzip", media
        assert "Accept-Encoding" in response.headers["vary"]
        assert int(response.headers["content-length"]) < len(BODY) // 5
        assert response.content == BODY  # the client reads what was sent

    plain = await client.get(f"{PREFIX}/documents", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.content == BODY


async def test_the_sign_in_and_the_session_stay_plain(client: httpx2.AsyncClient) -> None:
    # Their answers carry the CSRF token: no secret in a compressed answer (BREACH).
    for path in ("/auth/me", "/auth/login", "/auth/oidc/callback"):
        response = await client.get(PREFIX + path, headers=GZIP)
        assert "content-encoding" not in response.headers, path
        assert response.content == BODY
    # Only below it: another path that starts alike is compressed.
    other = await client.get(f"{PREFIX}/authors", headers=GZIP)
    assert other.headers["content-encoding"] == "gzip"


@pytest.mark.parametrize(
    "media",
    ["application/pdf", "image/png", "image/svg+xml", "message/rfc822", "text/event-stream"],
)
async def test_files_and_event_streams_go_as_they_are(
    client: httpx2.AsyncClient, media: str
) -> None:
    response = await client.get(f"{PREFIX}/documents/1/file", params={"type": media}, headers=GZIP)
    assert "content-encoding" not in response.headers
    assert response.content == BODY


async def test_a_small_answer_goes_as_it_is(client: httpx2.AsyncClient) -> None:
    small = await client.get(PREFIX, params={"size": COMPRESS_FROM - 1}, headers=GZIP)
    assert "content-encoding" not in small.headers
    large = await client.get(PREFIX, params={"size": COMPRESS_FROM}, headers=GZIP)
    assert large.headers["content-encoding"] == "gzip"


async def test_lekto_compresses_its_api_and_its_web_ui(tmp_path: Path) -> None:
    script = "export const words = [" + ", ".join(f'"muster{n}"' for n in range(400)) + "];"
    build = tmp_path / "build"
    (build / "_app" / "immutable").mkdir(parents=True)
    (build / "index.html").write_text("<!doctype html><title>lekto</title>", encoding="utf-8")
    (build / "_app" / "immutable" / "start.Bx1y2z.js").write_text(script, encoding="utf-8")
    async with api_with(ui_directory=build) as api:
        described = await api.client.get(f"{PREFIX}/openapi.json", headers=GZIP)
        assert described.status_code == 200
        assert described.headers["content-encoding"] == "gzip"
        assert described.json()["info"]["title"] == "Lekto DMS API"

        file = await api.client.get("/ui/_app/immutable/start.Bx1y2z.js", headers=GZIP)
        assert file.headers["content-encoding"] == "gzip"
        assert file.text == script
        # Its cache headers stay: compressed or not, the hashed file never changes.
        assert "immutable" in file.headers["cache-control"]

        user = await api.user()
        async with api.sign_in(user) as session:
            me = await session.client.get(f"{PREFIX}/auth/me", headers=GZIP)
            assert me.status_code == 200
            assert "content-encoding" not in me.headers
