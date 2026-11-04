"""`/documents/{id}/origin`: where a document came from."""

from uuid import UUID

from fastapi import APIRouter

from lekto.adapters.inbound.rest.auth import PROTECTED, CurrentUser
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.problems import problem_responses
from lekto.adapters.inbound.rest.schemas.origins import MailOriginOut, OriginOut
from lekto.core.domain.ids import DocumentId

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=PROTECTED)


@router.get(
    "/{id}/origin",
    summary="Where a document came from",
    description=(
        "Needs read access. For a document a mail brought: the mailbox, the rule, sender, "
        "recipients, subject, its dates and who forwarded it; `mail` is null for any other."
    ),
    response_model=OriginOut,
    responses=problem_responses(401, 404, 422),
)
async def origin(id: UUID, user: CurrentUser, context: Context) -> OriginOut:
    found = await context.mail_intake.origin(user, DocumentId(id))
    return OriginOut(mail=None if found is None else MailOriginOut.of(found))
