"""`/mail-rules`: what the mailboxes' mails bring in, for admins."""

from uuid import UUID

from fastapi import APIRouter

from lekto.adapters.inbound.rest.auth import PROTECTED, CurrentUser
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.problems import problem_responses
from lekto.adapters.inbound.rest.schemas.mail_rules import (
    DryRunMailOut,
    MailRuleCreate,
    MailRuleDryRun,
    MailRuleOut,
    MailRulePatch,
)
from lekto.core.domain.ids import MailboxId, MailRuleId
from lekto.core.services.mail_rules import DRY_RUN_MAILS

router = APIRouter(prefix="/mail-rules", tags=["mail rules"], dependencies=PROTECTED)

WHO = "Only admins (403)."
HOW = (
    "Of a mailbox's active rules the first that matches a mail decides, by priority (smaller "
    "first), the same priority by name; a mail no rule takes goes by the mailbox's fallback."
)
CHECKS = (
    "The person must be active, the space one they file into, the type one that exists; a "
    "person is needed unless the rule takes nothing, a folder with `move` (422)."
)


@router.get(
    "",
    summary="List mail rules",
    description=f"Every mail rule, by mailbox, priority and name. {HOW} {WHO}",
    response_model=list[MailRuleOut],
    responses=problem_responses(401, 403),
)
async def list_mail_rules(user: CurrentUser, context: Context) -> list[MailRuleOut]:
    return [MailRuleOut.of(rule) for rule in await context.mail_rules.list_rules(user)]


@router.post(
    "",
    status_code=201,
    summary="Create a mail rule",
    description=f"{HOW} {CHECKS} {WHO}",
    response_model=MailRuleOut,
    responses=problem_responses(401, 403, 404, 422),
)
async def create_mail_rule(
    body: MailRuleCreate, user: CurrentUser, context: Context
) -> MailRuleOut:
    rule = await context.mail_rules.create(
        user, MailboxId(body.mailbox_id), body.changes(body.name)
    )
    return MailRuleOut.of(rule)


@router.post(
    "/dry-run",
    summary="Dry run of a mail rule",
    description=(
        f"What a rule (saved or not; with `rule_id` in place of the stored one) would do with the "
        f"mailbox's latest {DRY_RUN_MAILS} mails, as Lekto recorded them when it fetched them: "
        "whether its conditions hold and who would decide each, this rule, another before it, or "
        f"the mailbox's fallback. Reads only; the mail server is not asked. {WHO}"
    ),
    response_model=list[DryRunMailOut],
    responses=problem_responses(401, 403, 404, 422),
)
async def dry_run_mail_rule(
    body: MailRuleDryRun, user: CurrentUser, context: Context
) -> list[DryRunMailOut]:
    found = await context.mail_rules.dry_run(
        user,
        MailboxId(body.mailbox_id),
        body.changes(body.name),
        rule=None if body.rule_id is None else MailRuleId(body.rule_id),
    )
    return [DryRunMailOut.of(item) for item in found]


@router.get(
    "/{id}",
    summary="A mail rule",
    description=WHO,
    response_model=MailRuleOut,
    responses=problem_responses(401, 403, 404, 422),
)
async def get_mail_rule(id: UUID, user: CurrentUser, context: Context) -> MailRuleOut:
    return MailRuleOut.of(await context.mail_rules.get(user, MailRuleId(id)))


@router.patch(
    "/{id}",
    summary="Change a mail rule",
    description=f"Checks as when creating. {WHO}",
    response_model=MailRuleOut,
    responses=problem_responses(401, 403, 404, 409, 422),
)
async def update_mail_rule(
    id: UUID, body: MailRulePatch, user: CurrentUser, context: Context
) -> MailRuleOut:
    rule = await context.mail_rules.change(user, MailRuleId(id), body.changes(body.name))
    return MailRuleOut.of(rule)


@router.delete(
    "/{id}",
    status_code=204,
    summary="Delete a mail rule",
    description=WHO,
    responses=problem_responses(401, 403, 404, 422),
)
async def delete_mail_rule(id: UUID, user: CurrentUser, context: Context) -> None:
    await context.mail_rules.delete(user, MailRuleId(id))
