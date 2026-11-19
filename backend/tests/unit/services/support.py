"""What the service tests share: `World`, the services on one in-memory unit of work, and
`Raises`. The `world` fixture is in `conftest.py`."""

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Self

from lekto.adapters.outbound.memory import (
    FakeCipher,
    FakeImageNormaliser,
    FakeOidcProvider,
    FakePageComposer,
    FakePageRenderer,
    FakePasswordHasher,
    FakeTotp,
    FakeWebhookSender,
    ManualClock,
    MemoryDatabase,
    MemoryEventBus,
    MemoryMailServer,
    MemoryObjectStore,
    MemoryUnitOfWork,
    MemoryUnitOfWorkFactory,
    fake_pdf,
)
from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.core.domain.documents import Document, DocumentChanges
from lekto.core.domain.editing import EditPart, PagePick
from lekto.core.domain.events import DomainEvent
from lekto.core.domain.ids import ContactId, DocumentTypeId, UserId
from lekto.core.domain.links import Links
from lekto.core.domain.master_data import Contact, DocumentType
from lekto.core.domain.pipeline import NODES, Node, NodeResult, NodeRun, Outcome, ProcessingHistory
from lekto.core.domain.reasons import ReasonCode, written
from lekto.core.domain.spaces import Space
from lekto.core.domain.users import Role, User
from lekto.core.ports.logos import LogoFetcher
from lekto.core.ports.ocr import VisionModel
from lekto.core.ports.repository import PAGE_LIMIT, DocumentFilter
from lekto.core.services.auth import AuthService
from lekto.core.services.documents import DocumentService
from lekto.core.services.editing import EditingService
from lekto.core.services.inbox import InboxService
from lekto.core.services.lenses import LensService
from lekto.core.services.logos import LogoService
from lekto.core.services.mail_intake import MailIntakeService
from lekto.core.services.mail_rules import MailRuleService
from lekto.core.services.mailboxes import MailboxService
from lekto.core.services.maintenance import MaintenanceService
from lekto.core.services.master_data import NORMALISE_BATCH, MasterDataService
from lekto.core.services.oidc import OidcService
from lekto.core.services.open_identifiers import OpenIdentifierService
from lekto.core.services.pipeline import NodeExecutor, PipelineService
from lekto.core.services.rules.nodes import ApplyRulesNode
from lekto.core.services.spaces import SpaceService
from lekto.core.services.tasks.desk import TaskDesk
from lekto.core.services.tasks.service import TaskService
from lekto.core.services.users import UserService
from lekto.core.services.webhooks import WebhookDeliveryService, WebhookPolicy, WebhookService
from tests import builders
from tests.builders import SAMPLES, TEMPLATES, PlaceholderNode, incoming

LINK_BASE = builders.PUBLIC_URL
"""`LEKTO_PUBLIC_URL` of the services that need it."""
MAINTENANCE_INTERVAL = timedelta(hours=1)
RETENTION = timedelta(days=7)
STACK = fake_pdf(3, "three payslips")
"""A document of three pages (`received`)."""


class Raises:
    """Node executor that raises `times` times, then returns OK."""

    def __init__(self, times: int) -> None:
        self.times = times
        self.calls = 0

    async def run(self, document: Document) -> NodeResult:
        self.calls += 1
        if self.calls <= self.times:
            raise OSError("scanner glitch")
        return builders.OK


class CancelledCommit:
    """Units of work on `inner` whose first commit once `armed` is stored and then cancelled:
    a request stopped, or a connection lost, while the database answered its commit."""

    def __init__(self, inner: MemoryUnitOfWorkFactory) -> None:
        self._inner = inner
        self.armed = False

    def __call__(self) -> MemoryUnitOfWork:
        work = self._inner()
        commit = work.commit

        async def stored_then_cancelled() -> None:
            await commit()
            if self.armed:
                self.armed = False
                raise asyncio.CancelledError

        work.commit = stored_then_cancelled  # type: ignore[method-assign]
        return work


@dataclass
class World:
    """Services on in-memory adapters, plus helpers to seed and inspect state."""

    clock: ManualClock = field(default_factory=lambda: ManualClock(builders.NOW))
    database: MemoryDatabase = field(default_factory=MemoryDatabase)
    object_store: MemoryObjectStore = field(default_factory=MemoryObjectStore)
    executors: dict[Node, NodeExecutor] = field(
        default_factory=lambda: {
            node: PlaceholderNode() for node in NODES if node is not Node.RECEIVE
        }
    )
    hasher: FakePasswordHasher = field(default_factory=FakePasswordHasher)
    cipher: FakeCipher = field(default_factory=FakeCipher)
    totp: FakeTotp = field(default_factory=FakeTotp)
    idp: FakeOidcProvider = field(default_factory=FakeOidcProvider)
    sender: FakeWebhookSender = field(default_factory=FakeWebhookSender)
    mail_server: MemoryMailServer = field(default_factory=MemoryMailServer)
    images: FakeImageNormaliser = field(default_factory=FakeImageNormaliser)
    composer: FakePageComposer = field(default_factory=FakePageComposer)
    normalise_batch: int = NORMALISE_BATCH

    @property
    def uow(self) -> MemoryUnitOfWorkFactory:
        return MemoryUnitOfWorkFactory(self.database)

    @property
    def users(self) -> UserService:
        return UserService(self.uow, self.clock, self.hasher)

    @property
    def auth(self) -> AuthService:
        return AuthService(
            self.uow,
            self.clock,
            hasher=self.hasher,
            cipher=self.cipher,
            totp=self.totp,
            sessions=builders.SESSIONS,
        )

    def oidc(self, *, auto_create: bool = False) -> OidcService:
        return OidcService(
            self.uow,
            self.clock,
            self.auth,
            self.idp,
            self.cipher,
            display_name="Test IdP",
            auto_create=auto_create,
        )

    @property
    def spaces(self) -> SpaceService:
        return SpaceService(self.uow, self.clock)

    @property
    def master_data(self) -> MasterDataService:
        return MasterDataService(
            self.uow,
            self.clock,
            builders.TEMPLATES,
            store=self.object_store,
            normalise_batch=self.normalise_batch,
        )

    @property
    def open_identifiers(self) -> OpenIdentifierService:
        return OpenIdentifierService(self.uow, self.object_store, self.master_data)

    @property
    def logos(self) -> LogoService:
        return LogoService(self.uow, self.clock, self.object_store, self.images)

    def fetching(self, fetcher: LogoFetcher) -> tuple[MasterDataService, LogoService]:
        """Master data and logos with fetching on."""
        master = MasterDataService(
            self.uow, self.clock, builders.TEMPLATES, store=self.object_store, fetch_logos=True
        )
        return master, LogoService(self.uow, self.clock, self.object_store, self.images, fetcher)

    @property
    def documents(self) -> DocumentService:
        return DocumentService(self.uow, self.clock, self.object_store)

    @property
    def editing(self) -> EditingService:
        return EditingService(
            self.uow,
            self.clock,
            self.object_store,
            self.composer,
            FakePageRenderer(pages=2),
            pipeline_version="test",
        )

    @property
    def inbox(self) -> InboxService:
        return InboxService(self.uow, self.clock)

    @property
    def webhooks(self) -> WebhookService:
        return WebhookService(
            self.uow,
            self.clock,
            self.cipher,
            builders.WEBHOOKS,
            builders.TEMPLATES,
            retention=builders.RETENTION,
        )

    @property
    def lenses(self) -> LensService:
        return LensService(self.uow, self.clock)

    @property
    def mailboxes(self) -> MailboxService:
        return MailboxService(self.uow, self.clock, self.cipher, self.mail_server)

    @property
    def mail_rules(self) -> MailRuleService:
        return MailRuleService(self.uow, self.clock)

    def mail_intake(
        self, pipeline: PipelineService | None = None, *, max_attachment: int = 10_000_000
    ) -> MailIntakeService:
        return MailIntakeService(
            self.uow,
            self.clock,
            self.cipher,
            self.mail_server,
            pipeline or self.pipeline(),
            max_attachment=max_attachment,
        )

    def webhook_delivery(self, policy: WebhookPolicy | None = None) -> WebhookDeliveryService:
        return WebhookDeliveryService(
            self.uow,
            self.clock,
            self.cipher,
            self.sender,
            policy or builders.WEBHOOKS,
            builders.TEMPLATES,
            links=builders.LINKS,
            store=self.object_store,
        )

    def maintenance(self, bus: MemoryEventBus | None = None) -> MaintenanceService:
        """The cleanup, every `MAINTENANCE_INTERVAL`, keeping what ended `RETENTION` long."""
        return MaintenanceService(
            self.uow,
            self.clock,
            bus or MemoryEventBus(self.database, clock=self.clock, retry=builders.EVENT_RETRY),
            interval=MAINTENANCE_INTERVAL,
            retention=RETENTION,
            session_idle=builders.DEFAULT_SETTINGS.session_idle_timeout,
            object_store=self.object_store,
        )

    @property
    def tasks(self) -> TaskService:
        return TaskService(self.uow, self.clock, self.cipher, self.object_store)

    def desk(self, links: Links | None = None) -> TaskDesk:
        """Places tasks; without `links` at `builders.LINKS`."""
        return TaskDesk(self.cipher, builders.TEMPLATES, links=links or builders.LINKS)

    def pipeline(
        self,
        executors: Mapping[Node, NodeExecutor] | None = None,
        *,
        vision: VisionModel | None = None,
        vision_lease: timedelta | None = None,
        facts: NodeExecutor | None = None,
    ) -> PipelineService:
        return builders.pipeline_service(
            self.uow,
            self.clock,
            self.object_store,
            {**self.executors, **(executors or {})},
            vision=vision,
            vision_lease=vision_lease,
            facts=facts,
        )

    async def user(self, name: str | None = None, role: Role = Role.USER) -> User:
        """A user with their personal space, seeded directly."""
        return await builders.seed_user(self.uow, name, role=role)

    async def account(
        self, name: str | None = None, role: Role = Role.USER, password: str = builders.PASSWORD
    ) -> User:
        """A user with their personal space and password."""
        return await builders.seed_account(
            self.uow, self.hasher, name, role=role, password=password
        )

    async def personal_space(self, user: User) -> Space:
        async with self.uow() as uow:
            return await uow.spaces.get_personal(user.id)

    async def visible(self, user: UserId) -> list[Document]:
        """The documents within `user`'s reach, oldest first (as the lists read them)."""
        async with self.uow() as uow:
            found = await uow.documents.query_visible(user, DocumentFilter(), limit=PAGE_LIMIT)
        return found[::-1]

    async def drain(self, pipeline: PipelineService | None = None) -> int:
        """Run due jobs until none is left; returns how many ran."""
        return await builders.drain(pipeline or self.pipeline())

    def events(self) -> list[DomainEvent]:
        return list(self.database.outbox)

    def event_types(self) -> list[str]:
        return [event.type for event in self.database.outbox]


async def received(world: World) -> tuple[User, Document]:
    """A user and their document of three pages (`STACK`), processed."""
    owner = await world.user()
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain()
    return owner, document


def part(*pages: int | tuple[int, int] | tuple[int, int, int], replaces: bool = False) -> EditPart:
    """A part of pages of the original (a number), or of a source (source, page[, turn])."""
    picks = []
    for page in pages:
        if isinstance(page, int):
            picks.append(PagePick(0, page))
        else:
            picks.append(PagePick(*page))
    return EditPart(tuple(picks), replaces=replaces)


class StoredScene:
    """A user and their personal space, and what tests store there directly: contacts and
    document types (the documents are each test's own)."""

    def __init__(self, world: World, owner: User, space: Space) -> None:
        self.world, self.owner, self.space = world, owner, space

    @classmethod
    async def of(cls, world: World) -> Self:
        owner = await world.user()
        return cls(world, owner, await world.personal_space(owner))

    async def contact(self, name: str) -> ContactId:
        contact = Contact.create(name=name, now=builders.NOW)
        async with self.world.uow() as uow:
            await uow.contacts.add(contact)
            await uow.commit()
        return contact.id

    async def document_type(self, name: str, *, target: bool = False) -> DocumentTypeId:
        kind = DocumentType.create(name=name, now=builders.NOW, relation_target=target)
        async with self.world.uow() as uow:
            await uow.document_types.add(kind)
            await uow.commit()
        return kind.id


def node_run(document: Document, node: Node, output: dict[str, object], *, why: str) -> NodeRun:
    """The first run of `node` that gave `output`: the judge's uncertain about `why`, any other
    node's OK."""
    return NodeRun(
        document_id=document.id,
        node=node,
        run=1,
        result=NodeResult(
            outcome=Outcome.UNCERTAIN if node is Node.JUDGE else Outcome.OK,
            reasons=(written(why),) if node is Node.JUDGE else (),
            output=output,  # type: ignore[arg-type]
        ),
        pipeline_version="1",
        started_at=builders.NOW,
        duration=timedelta(seconds=1),
    )


async def ingest(
    world: World, service: PipelineService, sample: str = "scan.pdf"
) -> tuple[User, Document]:
    """A user's upload of a file of `SAMPLES`, processed by `service`."""
    owner = await world.user()
    data = (SAMPLES / sample).read_bytes()
    document = await service.receive(owner.id, incoming(data), filename=sample)
    await world.drain(service)
    return owner, await world.documents.get(owner.id, document.id)


CONFIRMED_ON = date(2022, 11, 25)
"""The date a person set on the document of `confirmed`."""


@dataclass(frozen=True)
class Confirmed:
    """A user's processed document of three pages (`STACK`) whose contact and date
    (`CONFIRMED_ON`) a person set, and a pipeline whose rules node runs the rules."""

    owner: User
    document: Document
    contact: ContactId
    pipeline: PipelineService


async def confirmed(world: World) -> Confirmed:
    owner = await world.user()
    admin = await world.user(role=Role.ADMIN)
    contact = await world.master_data.create_contact(admin.id, "Muster Versicherung")
    document = await world.pipeline().receive(owner.id, incoming(STACK), filename="stack.pdf")
    await world.drain()
    await world.documents.change_metadata(
        owner.id, document.id, DocumentChanges(contact_id=contact.id, document_date=CONFIRMED_ON)
    )
    rules = ApplyRulesNode(
        world.uow, world.object_store, RegexPatternMatcher(0.2), TEMPLATES, max_text=200_000
    )
    return Confirmed(owner, document, contact.id, world.pipeline({Node.APPLY_RULES: rules}))


async def held_as_a_new_version(world: World, owner: User, document: Document) -> bool:
    """Whether the last run of the rules holds `document` for a review as a new version."""
    log = await world.documents.processing_log(owner.id, document.id)
    entry = ProcessingHistory(log).latest(Node.APPLY_RULES)
    return entry is not None and ReasonCode.NEW_VERSION in {
        reason.code for reason in entry.result.reasons
    }
