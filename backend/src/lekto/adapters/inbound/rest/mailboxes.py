"""`/mailboxes`: the mailboxes Lekto fetches from, for admins."""

from uuid import UUID

from fastapi import APIRouter

from lekto.adapters.inbound.rest.auth import PROTECTED, CurrentUser
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.problems import problem_responses
from lekto.adapters.inbound.rest.schemas.mailboxes import (
    ConnectionTestBody,
    ConnectionTestOut,
    MailboxCreate,
    MailboxOut,
    MailboxPatch,
)
from lekto.core.domain.ids import MailboxId

router = APIRouter(prefix="/mailboxes", tags=["mailboxes"], dependencies=PROTECTED)

WHO = "Only admins (403)."
CHECKS = (
    "The person of the fallback must be an active user, the type of the mail text a document "
    "type; a day with `since_date`, a person with `everything` (422). 409: a mailbox has that "
    "name (regardless of case)."
)


@router.get(
    "",
    summary="List mailboxes",
    description=f"All mailboxes by name, with the status of their fetches. {WHO}",
    response_model=list[MailboxOut],
    responses=problem_responses(401, 403),
)
async def list_mailboxes(user: CurrentUser, context: Context) -> list[MailboxOut]:
    return [MailboxOut.of(item) for item in await context.mailboxes.list_mailboxes(user)]


@router.post(
    "",
    status_code=201,
    summary="Create a mailbox",
    description=f"The password is stored encrypted and never shown again. {CHECKS} {WHO}",
    response_model=MailboxOut,
    responses=problem_responses(401, 403, 409, 422),
)
async def create_mailbox(body: MailboxCreate, user: CurrentUser, context: Context) -> MailboxOut:
    mailbox = await context.mailboxes.create(
        user,
        name=body.name,
        host=body.host,
        port=body.port,
        security=body.security,
        username=body.username,
        password=body.password,
        changes=body.settings(),
    )
    return MailboxOut.of(mailbox)


@router.post(
    "/test",
    summary="Test a connection",
    description=(
        "Signs in and lists the account's folders (`INBOX` first), for picking them. A failure "
        "is an answer too (`ok` false, `error` says why: unreachable, no secure connection, "
        "user name or password refused, the server's error). Without `password`, the stored "
        f"one of `mailbox_id` (422 if neither is given). {WHO}"
    ),
    response_model=ConnectionTestOut,
    responses=problem_responses(401, 403, 404, 422),
)
async def test_connection(
    body: ConnectionTestBody, user: CurrentUser, context: Context
) -> ConnectionTestOut:
    test = await context.mailboxes.test_connection(
        user,
        host=body.host,
        port=body.port,
        security=body.security,
        username=body.username,
        password=body.password,
        mailbox_id=None if body.mailbox_id is None else MailboxId(body.mailbox_id),
    )
    return ConnectionTestOut.of(test)


@router.get(
    "/{id}",
    summary="A mailbox",
    description=WHO,
    response_model=MailboxOut,
    responses=problem_responses(401, 403, 404, 422),
)
async def get_mailbox(id: UUID, user: CurrentUser, context: Context) -> MailboxOut:
    return MailboxOut.of(await context.mailboxes.get(user, MailboxId(id)))


@router.patch(
    "/{id}",
    summary="Change a mailbox",
    description=f"Checks as when creating; without `password` the stored one stays. {WHO}",
    response_model=MailboxOut,
    responses=problem_responses(401, 403, 404, 409, 422),
)
async def update_mailbox(
    id: UUID, body: MailboxPatch, user: CurrentUser, context: Context
) -> MailboxOut:
    mailbox = await context.mailboxes.change(
        user, MailboxId(id), body.changes(), password=body.password
    )
    return MailboxOut.of(mailbox)


@router.delete(
    "/{id}",
    status_code=204,
    summary="Delete a mailbox",
    description=f"What it brought in stays. {WHO}",
    responses=problem_responses(401, 403, 404, 422),
)
async def delete_mailbox(id: UUID, user: CurrentUser, context: Context) -> None:
    await context.mailboxes.delete(user, MailboxId(id))
