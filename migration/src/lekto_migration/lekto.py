"""Writing to Lekto through its REST API with pylekto, with an admin's API token. Nothing else is
used.

pylekto repeats nothing (.knowledge/decisions/2026-11-18-pylekto-architecture.md, point 4): a
server error, a dropped connection and too many requests are repeated here, a few times. The
answers go on as JSON values, as Lekto wrote them; every refusal is an `ApiError`."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any, Protocol

import httpx2
from pylekto import (
    API_VERSION,
    LEKTO_VERSION,
    LektoApiError,
    LektoClient,
    LektoConflictError,
    LektoConnectionError,
    LektoError,
    LektoRateLimitError,
    LektoResponseError,
    LektoServerError,
    api_fit,
)
from pylekto.models import (
    ContactCreate,
    ContactPatch,
    DocumentPatch,
    DocumentTypeCreate,
    DocumentTypePatch,
    FieldCreate,
    FieldPatch,
    MemberIn,
    ProfilePatch,
    SpaceCreate,
    TagCreate,
    UserCreate,
    UserPatch,
)

RETRY_STATUS = {500, 502, 503, 504}
DELAYS = (1.0, 3.0, 10.0)


PAGE_SIZE = 200
"""Documents of one page of `GET /documents`: as many as Lekto gives (`PAGE_LIMIT`)."""


class ApiError(Exception):
    """A request Lekto refused. `existing` is the document a duplicate upload collided with."""

    def __init__(self, status: int, detail: str, existing: str | None = None) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail
        self.existing = existing


class _Model(Protocol):
    """What the client reads of pylekto's models: their JSON."""

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _Request[M](Protocol):
    """A pylekto model of a request body, made from values."""

    def model_validate(self, obj: Any, /) -> M: ...


def unfit(api_version: str | None) -> str | None:
    """Why this client does not work with a Lekto that speaks the API `api_version`; None if it
    fits (`pylekto.api_fit`)."""
    ours = f"this client speaks the API {API_VERSION} of Lekto {LEKTO_VERSION}"
    match api_fit(api_version):
        case "fits":
            return None
        case "newer":
            return f"Lekto speaks the API {api_version}, {ours}: use the client of that Lekto"
        case "older":
            return f"Lekto speaks the API {api_version}, {ours}: update Lekto"
        case _:
            return f"Lekto names no API version, {ours}: update Lekto"


class Lekto:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx2.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        delays: tuple[float, ...] = DELAYS,
    ) -> None:
        # pylekto keeps the settings of a client passed in, and leaves closing it to us.
        self._http = httpx2.AsyncClient(
            timeout=httpx2.Timeout(300.0, connect=10.0),
            transport=transport,
            event_hooks={"response": [_plain]},
        )
        self._lekto = LektoClient(base_url, token, client=self._http)
        self._sleep = sleep
        self._delays = delays

    async def close(self) -> None:
        await self._http.aclose()

    async def _call[T](self, send: Callable[[], Awaitable[T]]) -> T:
        """What `send` returns. Server errors, a dropped connection and too many requests are
        repeated a few times; every other refusal is an `ApiError`."""
        for attempt in range(len(self._delays) + 1):
            last = attempt == len(self._delays)
            try:
                return await send()
            except LektoRateLimitError as error:
                if last:
                    raise _error(error) from None
                await self._sleep(_wait(error.retry_after))
            except (LektoServerError, LektoConnectionError) as error:
                if last:
                    raise _error(error) from None
                await self._sleep(self._delays[attempt])
            except LektoError as error:
                raise _error(error) from None
        raise AssertionError("unreachable")

    async def _one(self, send: Callable[[], Awaitable[_Model]]) -> dict[str, Any]:
        return (await self._call(send)).model_dump(mode="json")

    async def _all(self, send: Callable[[], Awaitable[list[Any]]]) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in await self._call(send)]

    # --- reading -----------------------------------------------------------------------------

    async def me(self) -> dict[str, Any]:
        return await self._one(self._lekto.auth.me)

    async def users(self) -> list[dict[str, Any]]:
        return await self._all(self._lekto.users.list)

    async def contacts(self) -> list[dict[str, Any]]:
        return await self._all(self._lekto.contacts.list)

    async def document_types(self) -> list[dict[str, Any]]:
        return await self._all(self._lekto.document_types.list)

    async def tags(self) -> list[dict[str, Any]]:
        return await self._all(self._lekto.tags.list)

    async def fields(self) -> list[dict[str, Any]]:
        return await self._all(self._lekto.fields.list)

    async def spaces(self) -> list[dict[str, Any]]:
        """Every space: the list follows the reach an admin asks for (`all_users`)."""
        return await self._all(lambda: self._lekto.spaces.list(all_users=True))

    async def documents(self, *, cursor: str | None = None) -> dict[str, Any]:
        return await self._one(
            lambda: self._lekto.documents.page(cursor=cursor, limit=PAGE_SIZE, all_users=True)
        )

    async def document(self, id: str) -> dict[str, Any]:
        return await self._one(lambda: self._lekto.documents.get(id))

    async def log(self, id: str) -> list[dict[str, Any]]:
        return await self._all(lambda: self._lekto.documents.log(id))

    async def text(self, id: str) -> str:
        """The whole text of a document's archive, piece by piece."""
        pieces: list[str] = []
        offset: int | None = 0
        while offset is not None:
            piece = await self._call(partial(self._lekto.documents.text, id, offset=offset))
            pieces.append(piece.text)
            offset = piece.next_offset
        return "".join(pieces)

    async def reading(self, id: str) -> dict[str, Any]:
        return await self._one(lambda: self._lekto.documents.reading(id))

    # --- writing -----------------------------------------------------------------------------

    async def create_user(self, username: str) -> dict[str, Any]:
        user = _body(UserCreate, {"username": username})
        return await self._one(lambda: self._lekto.users.create(user))

    async def set_active(self, id: str, active: bool) -> dict[str, Any]:
        changes = _body(UserPatch, {"active": active})
        return await self._one(lambda: self._lekto.users.update(id, changes))

    async def profile(self, id: str) -> dict[str, Any]:
        return await self._one(lambda: self._lekto.users.profile(id))

    async def change_profile(self, id: str, changes: dict[str, Any]) -> dict[str, Any]:
        patch = _body(ProfilePatch, changes)
        return await self._one(lambda: self._lekto.users.update_profile(id, patch))

    async def create_contact(self, name: str) -> dict[str, Any]:
        contact = _body(ContactCreate, {"name": name})
        return await self._one(lambda: self._lekto.contacts.create(contact))

    async def create_document_type(self, name: str) -> dict[str, Any]:
        document_type = _body(DocumentTypeCreate, {"name": name})
        return await self._one(lambda: self._lekto.document_types.create(document_type))

    async def create_tag(self, name: str, scope: str, parent_id: str | None) -> dict[str, Any]:
        values: dict[str, Any] = {"name": name, "scope": scope}
        if parent_id is not None:
            values["parent_id"] = parent_id
        tag = _body(TagCreate, values)
        return await self._one(lambda: self._lekto.tags.create(tag))

    async def set_contact_groups(self, id: str, group_ids: list[str]) -> dict[str, Any]:
        changes = _body(ContactPatch, {"group_ids": group_ids})
        return await self._one(lambda: self._lekto.contacts.update(id, changes))

    async def set_document_type_groups(self, id: str, group_ids: list[str]) -> dict[str, Any]:
        changes = _body(DocumentTypePatch, {"group_ids": group_ids})
        return await self._one(lambda: self._lekto.document_types.update(id, changes))

    async def create_field(
        self, name: str, data_type: str, choices: tuple[str, ...]
    ) -> dict[str, Any]:
        values: dict[str, Any] = {"name": name, "data_type": data_type}
        if choices:
            values["choices"] = list(choices)
        created = _body(FieldCreate, values)
        return await self._one(lambda: self._lekto.fields.create(created))

    async def set_choices(self, id: str, choices: list[str]) -> dict[str, Any]:
        changes = _body(FieldPatch, {"choices": choices})
        return await self._one(lambda: self._lekto.fields.update(id, changes))

    async def create_space(self, name: str, members: dict[str, str]) -> dict[str, Any]:
        """A shared space with `members` (user id -> `read` or `edit`); the executing admin
        is not one of them."""
        listed = [{"user_id": user, "role": role} for user, role in members.items()]
        space = _body(SpaceCreate, {"name": name, "members": listed})
        return await self._one(lambda: self._lekto.spaces.create(space))

    async def set_member(self, space_id: str, user_id: str, role: str) -> dict[str, Any]:
        member = _body(MemberIn, {"role": role})
        return await self._one(lambda: self._lekto.spaces.set_member(space_id, user_id, member))

    async def upload(
        self,
        path: Path,
        filename: str,
        *,
        uploaded_by: str,
        space_id: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """Upload a file of the migration (`channel=migration`) with its uploader, space and
        metadata (`ImportedMetadataIn`); each attempt reads the file anew."""

        async def send() -> _Model:
            with path.open("rb") as handle:
                return await self._lekto.documents.upload(
                    handle,
                    filename,
                    space_id=space_id,
                    channel="migration",
                    uploaded_by=uploaded_by,
                    metadata=metadata,
                )

        return await self._one(send)

    async def align(self, id: str, changes: dict[str, Any], *, dry_run: bool = False) -> Any:
        """Change a migrated document like its source without confirming it; with `dry_run`,
        what would happen (the rules included)."""
        documents, patch = self._lekto.documents, _body(DocumentPatch, changes)
        if dry_run:
            return await self._one(lambda: documents.dry_run(id, patch, confirm=False))
        return await self._one(lambda: documents.update(id, patch, confirm=False))

    async def move(self, id: str, space_id: str) -> None:
        await self._call(lambda: self._lekto.documents.move(id, space_id))


async def _plain(response: httpx2.Response) -> None:
    """An answer that is sent on to another address (the client follows none) or that holds no
    JSON (a proxy's page, say) is refused as such, not as a model it does not fit (MI-07)."""
    if response.is_redirect:
        location = response.headers.get("location", "?")
        raise ApiError(response.status_code, f"sent on to {location}: set that address")
    kind = response.headers.get("content-type", "")
    if response.is_success and response.status_code != 204 and "json" not in kind:
        raise ApiError(response.status_code, f"no JSON in the answer ({kind or 'no content type'})")


def _body[M](model: _Request[M], values: dict[str, Any]) -> M:
    """A request body as pylekto's model of it; a value it refuses is an `ApiError` (422, as
    Lekto would answer), and nothing is sent."""
    try:
        return model.model_validate(values)
    except ValueError as error:  # pydantic's ValidationError
        raise ApiError(422, f"not sent: {error}") from None


def _wait(seconds: float | None) -> float:
    """Seconds to wait after too many requests (`Retry-After`); five if Lekto names none."""
    return 5.0 if seconds is None else min(max(seconds, 0.0), 60.0)


def _error(error: LektoError) -> ApiError:
    if isinstance(error, LektoApiError):
        existing = error.existing_document_id if isinstance(error, LektoConflictError) else None
        detail = error.problem.detail or error.problem.title
        return ApiError(error.status, detail, None if existing is None else str(existing))
    if isinstance(error, LektoResponseError):
        return ApiError(0, f"{error} ({API_VERSION} is the API this client speaks)")
    return ApiError(0, str(error))
