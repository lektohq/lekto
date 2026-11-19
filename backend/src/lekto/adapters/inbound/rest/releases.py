"""The version of Lekto and whether a newer one is out
(`.knowledge/open/update-notifier-fas.md`)."""

from fastapi import APIRouter

from lekto.adapters.inbound.rest.auth import PROTECTED, CurrentUser, area
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.problems import problem_responses
from lekto.adapters.inbound.rest.schemas.releases import ReleaseOut, VersionOut
from lekto.adapters.inbound.rest.version import API_VERSION
from lekto.core.domain.rights import TokenRight

SYSTEM_AREA = area(TokenRight.SYSTEM_READ, TokenRight.SYSTEM_WRITE)
router = APIRouter(
    route_class=SYSTEM_AREA, prefix="/version", tags=["system"], dependencies=PROTECTED
)


@router.get(
    "",
    summary="The version and whether a newer one is out",
    description=(
        "The running versions of Lekto and of this API, and what the last look at Lekto's "
        "releases found (the worker asks GitHub every hour unless `LEKTO_UPDATE_CHECK` is off)."
    ),
    response_model=VersionOut,
    responses=problem_responses(401, 403),
)
async def version(user: CurrentUser, context: Context) -> VersionOut:
    status = await context.updates.status(user)
    return VersionOut(
        lekto_version=status.running,
        api_version=API_VERSION,
        update_check=status.checking,
        checked_at=status.checked_at,
        latest=None if status.latest is None else ReleaseOut.of(status.latest),
        update_available=status.update_available,
    )
