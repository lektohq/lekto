"""Who calls the API: a session cookie (web UI) or `Authorization: Bearer <API token>`.

- With a Bearer header, only the token counts; a cookie in the same request is ignored.
- Requests that change something (any method but GET, HEAD, OPTIONS) need, with a session, the
  header `X-CSRF-Token` with the session's CSRF token (`GET /auth/me`, sign-in answer), and,
  with a token, the scope `read_write`. A POST that only reads (`READS`: words in the body, so
  they stay out of addresses) is open to a `read` token; with a session it needs the header all
  the same. A token of the scope `upload` reaches only the upload (`UPLOADS`), nothing else.
- Every protected router depends on `authenticate`, so a route cannot be added without it. It
  runs before the parameters are checked: without credentials the answer is always 401.
- Managing one's own sign-in (password, TOTP, tokens, sessions, links) needs a session; an API
  token cannot be used to take over an account.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal, TypedDict

from fastapi import Depends, Request, Response
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from lekto.adapters.inbound.bearer import bearer_token
from lekto.adapters.inbound.rest.context import ApiContext, Context
from lekto.adapters.inbound.rest.paths import LOGIN_PATH
from lekto.core.domain.errors import AuthenticationError, PermissionDeniedError
from lekto.core.domain.identity import (
    KNOWN_DEVICE_LIFETIME,
    KNOWN_DEVICES_PER_BROWSER,
    ViaToken,
    csrf_matches,
)
from lekto.core.domain.ids import UserId
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.rights import ADMIN_RIGHTS, READ_RIGHTS, Actor, TokenRight
from lekto.core.services.auth import Principal, SignedIn
from lekto.core.services.oidc import FLOW_LIFETIME

SECURE_SESSION_COOKIE = "__Host-lekto_session"
SESSION_COOKIE = "lekto_session"  # without `Secure`, for development over plain HTTP
SECURE_FLOW_COOKIE = "__Host-lekto_oidc"
FLOW_COOKIE = "lekto_oidc"
# The known device's tokens, sent only to the sign-in: `__Host-` would need the path `/`.
SECURE_DEVICE_COOKIE = "__Secure-lekto_device"
DEVICE_COOKIE = "lekto_device"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
READS_KEY = "x-reads"
READS = {READS_KEY: True}
"""`openapi_extra` of a POST that only reads, such as a search with its words in the body: it
needs the read right of its area."""
RIGHT_KEY = "x-right"
"""The mark of the right an API token needs for an operation: a `TokenRight`, `SESSION` or
`ANY` (`.knowledge/plans/token-rights.md`)."""
SESSION = "session"
"""The mark of an operation only a session reaches, never an API token."""
ANY = "any"
"""The mark of an operation every API token reaches (who the caller is)."""


def right(value: TokenRight | str) -> dict[str, str]:
    """`openapi_extra` of an operation that needs `value`, whatever its area's right."""
    return {RIGHT_KEY: str(value)}


UPLOADS = right(TokenRight.DOCUMENTS_UPLOAD)
"""`openapi_extra` of the upload, the one operation a token of the scope `upload` reaches."""

# Security schemes of the OpenAPI document; `app.openapi` sets them per operation from the
# dependencies of its route.
SECURITY_SCHEMES = {
    "session": {
        "type": "apiKey",
        "in": "cookie",
        "name": SECURE_SESSION_COOKIE,
        "description": (
            "Session cookie from `POST /auth/login` or the OIDC callback (`lekto_session` "
            "when the server runs without `Secure` cookies). Changing requests also need the "
            f"header `{CSRF_HEADER}`."
        ),
    },
    "token": {
        "type": "http",
        "scheme": "bearer",
        "description": (
            "Personal API token (`lekto_…`) with its rights: each operation names the right "
            f"it needs as `{RIGHT_KEY}` (`{SESSION}`: no token reaches it; `{ANY}`: every "
            "token). An admin right also needs an active admin; an admin token without one "
            "acts as a user with the same spaces."
        ),
    },
    "taskToken": {
        "type": "http",
        "scheme": "bearer",
        "description": (
            "The one-time token of a task (`lkt_…`), from its request (`lekto-task-token`); "
            "only for answering that task."
        ),
    },
    "fileSignature": {
        "type": "apiKey",
        "in": "query",
        "name": "signature",
        "description": (
            "Lekto's signature in a link to a file of a model call's document, with `expires`; "
            "from the request of the model call."
        ),
    },
}
SECURITY: list[dict[str, list[str]]] = [{"session": []}, {"token": []}]
TASK_TOKEN: list[dict[str, list[str]]] = [{"taskToken": []}]
FILE_SIGNATURE: list[dict[str, list[str]]] = [{"fileSignature": []}]
SESSION_ONLY: list[dict[str, list[str]]] = [{"session": []}]


def session_cookie_name(context: ApiContext) -> str:
    return SECURE_SESSION_COOKIE if context.cookie_secure else SESSION_COOKIE


def flow_cookie_name(context: ApiContext) -> str:
    return SECURE_FLOW_COOKIE if context.cookie_secure else FLOW_COOKIE


def device_cookie_name(context: ApiContext) -> str:
    return SECURE_DEVICE_COOKIE if context.cookie_secure else DEVICE_COOKIE


async def authenticate(request: Request, context: Context) -> Principal:
    """The caller, checked once per request; AuthenticationError (401) without valid
    credentials, PermissionDeniedError (403) for a change without CSRF token, and for an API
    token without the right the operation needs (`RIGHT_KEY`)."""
    cached: Principal | None = getattr(request.state, "principal", None)
    if cached is not None:
        return cached
    header = request.headers.get("authorization")
    if header is not None:
        principal = await context.auth.authenticate_token(bearer_token(header))
        _check_right(request, principal)
    else:
        session_token = request.cookies.get(session_cookie_name(context))
        if not session_token:
            raise AuthenticationError(because(ReasonCode.AUTHENTICATION_REQUIRED))
        principal = await context.auth.authenticate_session(session_token)
        if request.method not in SAFE_METHODS and not csrf_matches(
            session_token, request.headers.get(CSRF_HEADER, "")
        ):
            raise PermissionDeniedError(because(ReasonCode.CSRF_MISSING, header=CSRF_HEADER))
    request.state.principal = principal
    return principal


def _check_right(request: Request, principal: Principal) -> None:
    """PermissionDeniedError unless the caller's token carries the right the request's route
    needs. A route without a mark is refused, as one only a session reaches. A token that only
    uploads reaches nothing else, not even `ANY`; one of a preset is refused as before the
    rights (one that only reads)."""
    route = request.scope.get("route")
    marked = (route.openapi_extra or {}).get(RIGHT_KEY) if isinstance(route, APIRoute) else None
    if marked is None or marked == SESSION:
        raise PermissionDeniedError(because(ReasonCode.SESSION_NEEDED))
    needed = None if marked == ANY else TokenRight(marked)
    if principal.only_uploads and needed is not TokenRight.DOCUMENTS_UPLOAD:
        # It reads nothing, not even who it is (`.knowledge/architecture/pwa-and-push.md`).
        raise PermissionDeniedError(because(ReasonCode.UPLOAD_ONLY_TOKEN))
    if needed is None or principal.may(needed):
        return
    rights = principal.rights or frozenset()
    if needed not in READ_RIGHTS and rights <= READ_RIGHTS | ADMIN_RIGHTS:
        raise PermissionDeniedError(because(ReasonCode.READ_ONLY_TOKEN))
    raise PermissionDeniedError(because(ReasonCode.TOKEN_LACKS_RIGHT, right=needed.value))


def _needs_session(dependant: Dependant) -> bool:
    """Whether `dependant` (an operation's dependencies) asks for a session."""
    return any(
        item.call is session_principal or _needs_session(item) for item in dependant.dependencies
    )


class MarkedRoute(APIRoute):
    """A route that marks the right an API token needs (`RIGHT_KEY`): `SESSION` if it asks
    for a session; else what its `openapi_extra` names, or for a router of an area (`area`)
    its read right for GET and an operation marked `READS`, its write right for the rest."""

    reads: TokenRight | None = None
    writes: TokenRight | None = None

    def __init__(self, path: str, endpoint: Callable[..., Any], **kwargs: Any) -> None:
        super().__init__(path, endpoint, **kwargs)
        extra = dict(self.openapi_extra or {})
        if _needs_session(self.dependant):
            extra[RIGHT_KEY] = SESSION
        elif RIGHT_KEY not in extra and self.reads is not None and self.writes is not None:
            safe = self.methods is not None and self.methods <= SAFE_METHODS
            reading = safe or bool(extra.get(READS_KEY))
            extra[RIGHT_KEY] = (self.reads if reading else self.writes).value
        self.openapi_extra = extra or None


def area(reads: TokenRight, writes: TokenRight) -> type[MarkedRoute]:
    """The route class of a router whose operations need `reads` or `writes` by default."""
    return type(f"{reads.name.title()}Route", (MarkedRoute,), {"reads": reads, "writes": writes})


async def still_authenticated(request: Request, context: ApiContext, user: UserId) -> bool:
    """Whether the request's credentials still authenticate `user` (for long requests such as
    event streams: a session may have been revoked, the account deactivated)."""
    request.state.principal = None
    try:
        return (await authenticate(request, context)).id == user
    except (AuthenticationError, PermissionDeniedError):
        return False


async def current_user(principal: Annotated[Principal, Depends(authenticate)]) -> Actor:
    """The authenticated user, with the rights they act with."""
    return principal.actor


async def via_token(principal: Annotated[Principal, Depends(authenticate)]) -> ViaToken | None:
    """The API token the caller acts through, for what records their decisions; None in a
    session."""
    return principal.via


async def session_principal(principal: Annotated[Principal, Depends(authenticate)]) -> Principal:
    """The caller, who must use a session (not an API token)."""
    if principal.session is None:
        raise PermissionDeniedError(because(ReasonCode.SESSION_NEEDED))
    return principal


Authenticated = Annotated[Principal, Depends(authenticate)]
CurrentUser = Annotated[Actor, Depends(current_user)]
Via = Annotated[ViaToken | None, Depends(via_token)]
SessionPrincipal = Annotated[Principal, Depends(session_principal)]
PROTECTED = [Depends(authenticate)]


async def optional_session(request: Request, context: Context) -> Principal | None:
    """The user signed in with a session cookie, if any (for the OIDC callback)."""
    token = request.cookies.get(session_cookie_name(context))
    if not token:
        return None
    try:
        return await context.auth.authenticate_session(token)
    except AuthenticationError:
        return None


class _CookieAttributes(TypedDict):
    path: str
    secure: bool
    httponly: bool
    samesite: Literal["lax"]


def _cookie_attributes(context: ApiContext) -> _CookieAttributes:
    """Of the session's and the OIDC flow's cookie: for the whole site, `Secure` unless the
    server runs without, out of reach of scripts, and sent along when a link from elsewhere is
    followed (the provider's redirect back)."""
    return {"path": "/", "secure": context.cookie_secure, "httponly": True, "samesite": "lax"}


def set_session_cookie(response: Response, context: ApiContext, signed_in: SignedIn) -> None:
    response.set_cookie(
        session_cookie_name(context),
        signed_in.token,
        max_age=int(context.auth.session_policy.max_age.total_seconds()),
        **_cookie_attributes(context),
    )


def clear_session_cookie(response: Response, context: ApiContext) -> None:
    response.delete_cookie(session_cookie_name(context), **_cookie_attributes(context))


def set_flow_cookie(response: Response, context: ApiContext, value: str) -> None:
    response.set_cookie(
        flow_cookie_name(context),
        value,
        max_age=int(FLOW_LIFETIME.total_seconds()),
        **_cookie_attributes(context),
    )


def clear_flow_cookie(response: Response, context: ApiContext) -> None:
    response.delete_cookie(flow_cookie_name(context), **_cookie_attributes(context))


def known_devices(request: Request, context: ApiContext) -> list[str]:
    """The tokens of known devices this browser keeps (`set_device_cookie`)."""
    value = request.cookies.get(device_cookie_name(context), "")
    return [token for token in value.split(".") if token][-KNOWN_DEVICES_PER_BROWSER:]


def set_device_cookie(response: Response, context: ApiContext, signed_in: SignedIn) -> None:
    """After a sign-in with the password: the known devices' tokens (URL-safe, joined by dots),
    for the sign-in only, out of reach of scripts, sent on requests of the site only."""
    if not signed_in.devices:
        return
    response.set_cookie(
        device_cookie_name(context),
        ".".join(signed_in.devices),
        max_age=int(KNOWN_DEVICE_LIFETIME.total_seconds()),
        path=LOGIN_PATH,
        secure=context.cookie_secure,
        httponly=True,
        samesite="strict",
    )


def client_address(request: Request) -> str | None:
    """The client's address (behind trusted proxies: from X-Forwarded-For, set by Uvicorn)."""
    return request.client.host if request.client is not None else None
