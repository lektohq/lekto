"""The flow of a document through a webhook, as the tests of the tasks, the model calls and the
rule steps drive it: the pipeline, the deliveries and the ends of tasks run until nothing is due,
and a request is answered through its task's id and token. Also the mail a document came with."""

from uuid import UUID

from lekto.core.domain.documents import Document
from lekto.core.domain.ids import MailboxId, MailRecordId, TaskId, UserId, new_id
from lekto.core.domain.mail_intake import MailOrigin, OriginRole
from lekto.core.ports.webhook_sender import WebhookRequest
from lekto.core.services.pipeline import PipelineService
from lekto.core.services.tasks.service import AnswerReceipt
from tests.builders import NOW
from tests.unit.services.rules_support import incoming_pdf
from tests.unit.services.support import World


async def run_due(world: World, pipeline: PipelineService) -> None:
    """Run the due jobs: the nodes, the deliveries and the ends of tasks."""
    delivery = world.webhook_delivery()
    while (
        await pipeline.run_next_job()
        or await delivery.run_next_job()
        or await world.tasks.run_next_job()
    ):
        pass


async def stored(world: World, document: Document) -> Document:
    async with world.uow() as uow:
        return await uow.documents.get(document.id)


async def arrive(world: World, pipeline: PipelineService, by: UserId) -> Document:
    """A PDF `by` uploads, once nothing is due any more."""
    received = await pipeline.receive(by, incoming_pdf(), filename="a.pdf")
    await run_due(world, pipeline)
    return await stored(world, received)


def sent_to(world: World, url: str) -> list[WebhookRequest]:
    return [request for request in world.sender.requests if request.url == url]


def task_of(request: WebhookRequest) -> TaskId:
    return TaskId(UUID(request.headers["lekto-task-id"]))


def token_of(request: WebhookRequest) -> str:
    return request.headers["lekto-task-token"]


async def answer_task(
    world: World, request: WebhookRequest, body: bytes, *, token: str | None = None
) -> AnswerReceipt:
    """Answer the task `request` asks with `body`, by its token unless another is given."""
    return await world.tasks.answer(task_of(request), token or token_of(request), body)


async def mailed(world: World, document: Document, filename: str) -> MailOrigin:
    """`document` came as an attachment of a mail (`filename`); the origin, stored."""
    origin = MailOrigin(
        document_id=document.id,
        record_id=MailRecordId(new_id()),
        mailbox_id=MailboxId(new_id()),
        mailbox="Post",
        rule="Scans",
        role=OriginRole.ATTACHMENT,
        letter=1,
        message_id="<scans@example.org>",
        sender=(),
        to=(),
        cc=(),
        subject="Scans",
        sent_at=None,
        arrived_at=NOW,
        filename=filename,
    )
    async with world.uow() as uow:
        await uow.mail_origins.add(origin)
        await uow.commit()
    return origin
