"""ASGI middleware of the API.

Paths given to them may name a segment `{id}`: it stands for one segment of any value."""

import re
from collections.abc import Collection, Mapping, Sequence

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware.gzip import DEFAULT_EXCLUDED_CONTENT_TYPES, GZipMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lekto.adapters.inbound.rest.problems import PRIVATE_HEADERS, problem


class RequestTooLargeError(HTTPException):
    """The request body exceeds the limit. An HTTPException, so that FastAPI passes it on
    while it reads a body instead of turning it into 400."""

    def __init__(self, limit: int) -> None:
        super().__init__(413, f"the request body is larger than {limit} bytes")


def _pattern(path: str) -> re.Pattern[str]:
    return re.compile(
        "/".join(r"[^/]+" if part == "{id}" else re.escape(part) for part in path.split("/"))
    )


class LimitRequestBody:
    """Bounds request bodies: by `Content-Length` before anything is read, and by the bytes
    received otherwise. Routes in `exempt` (method, path) have limits of their own, such as the
    uploads; routes in `limits` a smaller one than `limit`, such as the public sign-in. FastAPI
    reads JSON bodies completely before validating them, so without this a client could make the
    process hold any amount of data."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        limit: int,
        exempt: Collection[tuple[str, str]],
        limits: Mapping[tuple[str, str], int] | None = None,
    ) -> None:
        self._app = app
        self._limit = limit
        self._exempt = [(method, _pattern(path)) for method, path in exempt]
        self._limits = [
            (method, _pattern(path), size) for (method, path), size in (limits or {}).items()
        ]

    def _exempted(self, method: str, path: str) -> bool:
        return any(method == wanted and pattern.fullmatch(path) for wanted, pattern in self._exempt)

    def _limit_of(self, method: str, path: str) -> int:
        for wanted, pattern, size in self._limits:
            if method == wanted and pattern.fullmatch(path):
                return size
        return self._limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._exempted(scope["method"], scope["path"]):
            await self._app(scope, receive, send)
            return
        limit = self._limit_of(scope["method"], scope["path"])
        headers = dict(scope["headers"])
        length = headers.get(b"content-length", b"").decode("latin-1")
        if length.isdigit() and int(length) > limit:
            error = RequestTooLargeError(limit)
            await problem(413, error.detail)(scope, receive, send)
            return
        received = 0

        async def limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise RequestTooLargeError(limit)
            return message

        await self._app(scope, limited, send)


class NoStore:
    """Marks every answer below `prefix` `Cache-Control: no-store`,
    `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` (a PDF opened from the
    API names no address to the links in it), also errors and redirects: the API's answers are
    personal (documents, users, logs) and some carry CSRF tokens, TOTP secrets, recovery codes
    and API tokens, which no browser or proxy cache may keep. `public` names the paths below
    the prefix that are not personal (health, the API description). On `cacheable` paths, a
    successful answer keeps the `Cache-Control` its route gives (a logo with its version in the
    URL); every other answer there is marked as well."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        prefix: str,
        public: Sequence[str] = (),
        cacheable: Sequence[str] = (),
    ) -> None:
        self._app = app
        self._prefix = prefix.rstrip("/")
        self._public = tuple(public)
        self._cacheable = [_pattern(path) for path in cacheable]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] != "http"
            or not (path == self._prefix or path.startswith(self._prefix + "/"))
            or path in self._public
        ):
            await self._app(scope, receive, send)
            return
        cacheable = scope["method"] in ("GET", "HEAD") and any(
            pattern.fullmatch(path) for pattern in self._cacheable
        )

        async def marked(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                kept = cacheable and message["status"] == 200 and "cache-control" in headers
                for name, value in PRIVATE_HEADERS.items():
                    if name != "Cache-Control" or not kept:
                        headers[name] = value
            await send(message)

        await self._app(scope, receive, marked)


FILES = ("application/pdf", "application/octet-stream", "image/*", "message/rfc822")
"""The media types of the files Lekto sends as they are (a document's original, its archive
PDF, a page, a logo): they are compressed already or large, and gzip would only cost time."""

COMPRESS_FROM = 1024
"""Bytes from which an answer is compressed; a smaller one fits a packet either way."""


class Compress:
    """gzip for the answers that shrink: the files of the web UI and the JSON of the API, for a
    client that accepts it. Neither Lekto nor the proxy examples compressed anything, so a
    first load of the web UI fetched three times the bytes it needs.

    Not compressed: the paths in `plain` (the sign-in and the session, whose answers carry the
    CSRF token: a secret and something an attacker could have reflected must not share a
    compressed answer, BREACH), the files Lekto sends as they are (`FILES`), event streams and
    partial answers (Starlette's own exclusions), and anything below `COMPRESS_FROM`."""

    def __init__(self, app: ASGIApp, *, plain: Sequence[str]) -> None:
        self._app = app
        self._plain = tuple(plain)
        # Level 6 (zlib's default): close to the smallest, at a fraction of the time of 9.
        self._gzip = GZipMiddleware(
            app,
            minimum_size=COMPRESS_FROM,
            compresslevel=6,
            exclude_content_types=(*DEFAULT_EXCLUDED_CONTENT_TYPES, *FILES),
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not scope["path"].startswith(self._plain):
            await self._gzip(scope, receive, send)
        else:
            await self._app(scope, receive, send)
