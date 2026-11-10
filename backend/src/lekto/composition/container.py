"""Composition root: choose the configured adapter for each port.

Adapters register their factories in the tables below, keyed by the configured adapter name.
A port whose configured adapter does not exist yet fails with AdapterNotAvailableError.
"""

import os
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Protocol

from pydantic import SecretStr

from lekto import __version__
from lekto.adapters.inbound.rest import OIDC_CALLBACK_PATH
from lekto.adapters.inbound.rest.paths import PREFIX as API_PREFIX
from lekto.adapters.inbound.rest.ui import UI_PREFIX
from lekto.adapters.outbound.crypto import (
    AesGcmCipher,
    AesSivRefCipher,
    Argon2PasswordHasher,
    PyotpTotp,
    decode_key,
)
from lekto.adapters.outbound.filesystem import FilesystemObjectStore
from lekto.adapters.outbound.imap import ImapMailServer
from lekto.adapters.outbound.liquid import LiquidTemplateRenderer
from lekto.adapters.outbound.logos import HttpLogoFetcher
from lekto.adapters.outbound.meilisearch import MeilisearchIndex
from lekto.adapters.outbound.memory import (
    FakeCipher,
    FakeClassifier,
    FakeCodeReader,
    FakeImageNormaliser,
    FakeMailRenderer,
    FakeMetadataReader,
    FakeOcr,
    FakePageComposer,
    FakePageRenderer,
    FakeParser,
    FakePasswordHasher,
    FakePushSender,
    FakeRefCipher,
    FakeTextLocator,
    FakeTotp,
    FakeWebhookSender,
    MemoryDatabase,
    MemoryEventBus,
    MemoryMailServer,
    MemoryObjectStore,
    MemorySearchIndex,
    MemoryUnitOfWorkFactory,
    MemoryWakeup,
)
from lekto.adapters.outbound.ocrmypdf import OcrmypdfEngine
from lekto.adapters.outbound.ocrmypdf.vision import VisionSettings
from lekto.adapters.outbound.oidc import AuthlibOidcProvider
from lekto.adapters.outbound.openai_compat import OpenAiCompatEmbeddings, OpenAiCompatLanguageModel
from lekto.adapters.outbound.pdfium import LayoutParser, PdfiumPageRenderer, PdfiumTextLocator
from lekto.adapters.outbound.pikepdf import FileMetadataReader, PikepdfPageComposer
from lekto.adapters.outbound.pillow import PillowImageNormaliser
from lekto.adapters.outbound.regex import RegexPatternMatcher
from lekto.adapters.outbound.s3 import S3ObjectStore
from lekto.adapters.outbound.sklearn import SklearnClassifier
from lekto.adapters.outbound.sql import SqlEventBus, SqlUnitOfWorkFactory, SqlWakeup
from lekto.adapters.outbound.system import SystemClock
from lekto.adapters.outbound.weasyprint import WeasyPrintMailRenderer
from lekto.adapters.outbound.webhooks import HttpWebhookSender
from lekto.adapters.outbound.webpush.sender import WebPushSender
from lekto.adapters.outbound.zxing import ZxingCodeReader
from lekto.composition.database import open_database
from lekto.composition.errors import AdapterNotAvailableError
from lekto.composition.settings import Settings
from lekto.core.domain.jobs import WORK_LEASE_MARGIN, RetryPolicy
from lekto.core.domain.links import Links
from lekto.core.domain.pipeline import Node
from lekto.core.domain.verdict import Thresholds
from lekto.core.domain.webhooks import PrivateTargets
from lekto.core.ports.classifier import Classifier
from lekto.core.ports.clock import Clock
from lekto.core.ports.codes import CodeReader
from lekto.core.ports.composer import PageComposer
from lekto.core.ports.embeddings import Embeddings
from lekto.core.ports.event_bus import DELIVERY_DELAY, DELIVERY_MAX_DELAY, EventBus
from lekto.core.ports.identity import (
    OidcProvider,
    PasswordHasher,
    RefCipher,
    SecretCipher,
    Totp,
)
from lekto.core.ports.images import ImageNormaliser
from lekto.core.ports.llm import LanguageModel
from lekto.core.ports.locator import TextLocator
from lekto.core.ports.logos import LogoFetcher
from lekto.core.ports.mail_renderer import MailRenderer
from lekto.core.ports.mail_server import MailServer
from lekto.core.ports.metadata import MetadataReader
from lekto.core.ports.object_store import ObjectStore
from lekto.core.ports.ocr import Ocr
from lekto.core.ports.pages import PageRenderer
from lekto.core.ports.parser import DocumentParser
from lekto.core.ports.patterns import PatternMatcher
from lekto.core.ports.push import PushSender
from lekto.core.ports.search_index import SearchIndex
from lekto.core.ports.templates import TemplateRenderer
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from lekto.core.ports.wakeup import Wakeup
from lekto.core.ports.webhook_sender import WebhookSender
from lekto.core.services.auth import AuthService, SessionPolicy
from lekto.core.services.automation import AutomationService
from lekto.core.services.bulk import BulkService
from lekto.core.services.classification.nodes import (
    ClassificationPolicy,
    FieldsNode,
    JudgeNode,
    LlmSignal,
)
from lekto.core.services.classification.signals import (
    ClassifierSignal,
    FactsSignal,
    NeighboursPolicy,
    NeighboursSignal,
)
from lekto.core.services.classifier import ClassifierPolicy, ClassifierService
from lekto.core.services.documents import DocumentService
from lekto.core.services.editing import EditingService
from lekto.core.services.expected import ExpectedService
from lekto.core.services.imports import ImportedFieldsNode, ImportedJudgeNode, ImportedSignal
from lekto.core.services.inbox import InboxService
from lekto.core.services.indexing import IndexingPolicy, IndexingService
from lekto.core.services.jobs import JobsService
from lekto.core.services.lenses import LensService
from lekto.core.services.logos import LogoService
from lekto.core.services.mail_intake import MailIntakeService
from lekto.core.services.mail_rules import MailRuleService
from lekto.core.services.mailboxes import MailboxService
from lekto.core.services.maintenance import MaintenanceService
from lekto.core.services.master_data import MasterDataService
from lekto.core.services.nodes import OcrNode, PagesNode, ParseNode
from lekto.core.services.oidc import OidcService
from lekto.core.services.open_identifiers import OpenIdentifierService
from lekto.core.services.pipeline import NodeExecutor, PipelineService
from lekto.core.services.profiles import ProfileService
from lekto.core.services.push import PushService
from lekto.core.services.relating import RelateNode
from lekto.core.services.relations import RelationService
from lekto.core.services.rules import RuleService
from lekto.core.services.rules.changes import ChangeRules
from lekto.core.services.rules.nodes import ApplyRulesNode, FileNode
from lekto.core.services.rules.retroactive import RuleApplicationService
from lekto.core.services.search import SearchPolicy, SearchService
from lekto.core.services.spaces import SpaceService
from lekto.core.services.stream import StreamService
from lekto.core.services.tasks.desk import TaskDesk
from lekto.core.services.tasks.service import TaskService
from lekto.core.services.users import UserService
from lekto.core.services.webhooks import (
    WebhookDeliveryService,
    WebhookPolicy,
    WebhookService,
)

type Factory[T] = Callable[[Settings], T]
type Closer = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class Opened[T]:
    """An adapter and, if it holds something to release (a client, connections), its closer."""

    adapter: T
    close: Closer | None = None


class _Closable(Protocol):
    async def aclose(self) -> None: ...


def _closing[T: _Closable](adapter: T) -> Opened[T]:
    """`adapter`, released by its `aclose`."""
    return Opened(adapter, adapter.aclose)


USER_AGENT = f"Lekto/{__version__}"
"""How Lekto names itself in requests to other sites: logo fetches and webhooks."""


@dataclass(frozen=True)
class Persistence:
    """The database-backed ports. They share one database: repositories, processing log,
    outbox and job queue through the unit of work, and the event bus reading the outbox."""

    unit_of_work: UnitOfWorkFactory
    event_bus: EventBus
    wakeup: Wakeup
    close: Closer


def sql_persistence(settings: Settings) -> Persistence:
    """SQLite or Postgres, per `LEKTO_DB_TYPE`; the schema must be migrated."""
    database = open_database(settings)
    wakeup = SqlWakeup(database)

    async def close() -> None:
        await wakeup.aclose()
        await database.dispose()

    return Persistence(
        unit_of_work=SqlUnitOfWorkFactory(database),
        event_bus=SqlEventBus(database, retry=event_retry_of(settings)),
        wakeup=wakeup,
        close=close,
    )


def filesystem_store(settings: Settings) -> Opened[FilesystemObjectStore]:
    return Opened(FilesystemObjectStore(settings.storage_path))


def s3_store(settings: Settings) -> Opened[S3ObjectStore]:
    # Settings guarantee these for s3.
    assert settings.s3_endpoint_url and settings.s3_bucket
    assert settings.s3_access_key_id and settings.s3_secret_access_key
    return _closing(
        S3ObjectStore(
            endpoint_url=str(settings.s3_endpoint_url),
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id.get_secret_value(),
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            path_style=settings.s3_path_style,
        )
    )


# Keys: `LEKTO_DB_TYPE` (persistence), `LEKTO_STORAGE_TYPE` (object store),
# or the fixed adapter name for ports with a single adapter.
PERSISTENCE: dict[str, Factory[Persistence]] = {
    "sqlite": sql_persistence,
    "postgres": sql_persistence,
}
OBJECT_STORES: dict[str, Factory[Opened[ObjectStore]]] = {
    "filesystem": filesystem_store,
    "s3": s3_store,
}


def openai_language_model(settings: Settings) -> OpenAiCompatLanguageModel:
    # Settings guarantee these together.
    assert settings.llm_base_url is not None and settings.llm_model is not None
    return OpenAiCompatLanguageModel(
        base_url=str(settings.llm_base_url),
        model=settings.llm_model,
        api_key=_secret(settings.llm_api_key),
        temperature=settings.llm_temperature,
        seed=settings.llm_seed,
        timeout=settings.llm_timeout.total_seconds(),
        response_format=settings.llm_response_format,
    )


def openai_embeddings(settings: Settings) -> OpenAiCompatEmbeddings:
    assert settings.embedding_base_url is not None and settings.embedding_model is not None
    return OpenAiCompatEmbeddings(
        base_url=str(settings.embedding_base_url),
        model=settings.embedding_model,
        api_key=_secret(settings.embedding_api_key),
        timeout=settings.embedding_timeout.total_seconds(),
    )


def _secret(value: SecretStr | None) -> str | None:
    return None if value is None else value.get_secret_value()


def meilisearch_index(settings: Settings) -> Opened[MeilisearchIndex]:
    assert settings.meilisearch_url is not None  # the adapter is only selected with a URL
    return _closing(
        MeilisearchIndex(
            url=str(settings.meilisearch_url),
            api_key=_secret(settings.meilisearch_api_key),
            index=settings.meilisearch_index,
            # Vectors only where there is a model to compute them (settings guarantee the length).
            dimensions=settings.embedding_dimensions if settings.embedding_base_url else None,
            locales=settings.search_locales.split("+"),
            timeout=settings.meilisearch_timeout.total_seconds(),
            task_timeout=settings.meilisearch_task_timeout.total_seconds(),
        )
    )


SEARCH_INDEXES: dict[str, Factory[Opened[SearchIndex]]] = {"meilisearch": meilisearch_index}
LANGUAGE_MODELS: dict[str, Factory[Opened[LanguageModel]]] = {
    "openai-compatible": lambda settings: _closing(openai_language_model(settings))
}
EMBEDDINGS: dict[str, Factory[Opened[Embeddings]]] = {
    "openai-compatible": lambda settings: _closing(openai_embeddings(settings))
}


def _cores_per_job(settings: Settings) -> int:
    """The cores are shared by the jobs that run at the same time."""
    return max(1, (os.cpu_count() or 1) // settings.worker_concurrency)


def ocrmypdf_engine(settings: Settings) -> OcrmypdfEngine:
    vision = None
    if settings.vlm_base_url is not None and settings.vlm_model is not None:
        vision = VisionSettings(
            base_url=str(settings.vlm_base_url),
            model=settings.vlm_model,
            api_key=_secret(settings.vlm_api_key),
            timeout=min(VISION_REQUEST_TIMEOUT, settings.vlm_timeout),
        )
    return OcrmypdfEngine(
        languages=settings.ocr_languages.split("+"),
        timeout=settings.ocr_timeout,
        jobs=_cores_per_job(settings),
        vision=vision,
        vision_timeout=settings.vlm_timeout,
        memory=int(settings.child_max_memory),
    )


def layout_parser(settings: Settings) -> LayoutParser:
    return LayoutParser()


OCR_ENGINES: dict[str, Factory[Ocr]] = {"ocrmypdf": ocrmypdf_engine}
PARSERS: dict[str, Factory[DocumentParser]] = {"layout": layout_parser}
PAGE_RENDERERS: dict[str, Factory[PageRenderer]] = {"pdfium": lambda _: PdfiumPageRenderer()}
THUMBNAIL_WIDTH = 320
"""Pixels wide of the pages of a file a person is about to add to an edit of the pages."""
THUMBNAIL_RENDERERS: dict[str, Factory[PageRenderer]] = {
    "pdfium": lambda _: PdfiumPageRenderer(width=THUMBNAIL_WIDTH, preview_width=THUMBNAIL_WIDTH)
}
TEXT_LOCATORS: dict[str, Factory[TextLocator]] = {"pdfium": lambda _: PdfiumTextLocator()}
CODE_READERS: dict[str, Factory[CodeReader]] = {"zxing": lambda _: ZxingCodeReader()}
METADATA_READERS: dict[str, Factory[MetadataReader]] = {"pikepdf": lambda _: FileMetadataReader()}
PAGE_COMPOSERS: dict[str, Factory[PageComposer]] = {"pikepdf": lambda _: PikepdfPageComposer()}
IMAGE_NORMALISERS: dict[str, Factory[ImageNormaliser]] = {
    "pillow": lambda _: PillowImageNormaliser()
}
CLASSIFIERS: dict[str, Factory[Classifier]] = {"scikit-learn": lambda _: SklearnClassifier()}
LOGO_FETCHERS: dict[str, Factory[LogoFetcher]] = {
    "httpx2": lambda _: HttpLogoFetcher(user_agent=USER_AGENT)
}


def redirect_uri(settings: Settings) -> str:
    """Where the provider sends the browser back: the API's OIDC callback."""
    public = public_base(settings)
    assert public is not None
    return public + OIDC_CALLBACK_PATH


def oidc_provider(settings: Settings) -> OidcProvider:
    # Settings guarantee these with OIDC.
    assert settings.oidc_issuer and settings.oidc_client_id and settings.oidc_client_secret
    return AuthlibOidcProvider(
        issuer=settings.oidc_issuer,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        redirect_uri=redirect_uri(settings),
        scopes=settings.oidc_scopes.split(),
        username_claim=settings.oidc_username_claim,
    )


OIDC_PROVIDERS: dict[str, Factory[OidcProvider]] = {"authlib": oidc_provider}


def secret_cipher(settings: Settings) -> SecretCipher:
    assert settings.secret_key is not None  # Settings require it for every role.
    return AesGcmCipher(decode_key(settings.secret_key.get_secret_value()))


def ref_cipher(settings: Settings) -> RefCipher:
    assert settings.secret_key is not None  # Settings require it for every role.
    return AesSivRefCipher(decode_key(settings.secret_key.get_secret_value()))


@dataclass(frozen=True)
class Container:
    """One adapter per port. Search, language model and embeddings are optional until the
    milestones that need them (M6, M5).

    `aclose` releases what the adapters hold (database engine, S3 client); call it when the
    API or the worker stops.
    """

    unit_of_work: UnitOfWorkFactory
    event_bus: EventBus
    wakeup: Wakeup
    object_store: ObjectStore
    clock: Clock
    ocr: Ocr
    parser: DocumentParser
    pages: PageRenderer
    thumbnails: PageRenderer
    locator: TextLocator
    codes: CodeReader
    metadata: MetadataReader
    composer: PageComposer
    images: ImageNormaliser
    password_hasher: PasswordHasher
    cipher: SecretCipher
    refs: RefCipher
    webhook_sender: WebhookSender
    push_sender: PushSender | None  # with a VAPID key
    mail_server: MailServer
    mail_renderer: MailRenderer
    totp: Totp
    patterns: PatternMatcher
    templates: TemplateRenderer
    oidc: OidcProvider | None
    search_index: SearchIndex | None
    language_model: LanguageModel | None
    embeddings: Embeddings | None
    classifier: Classifier | None
    # With `LEKTO_LOGO_FETCH`: Lekto asks the websites of contacts for their logos.
    logo_fetcher: LogoFetcher | None = None
    closers: tuple[Closer, ...] = field(default=(), repr=False)

    async def aclose(self) -> None:
        """Close in reverse order of creation; every closer runs even if one fails."""
        errors: list[Exception] = []
        for close in reversed(self.closers):
            try:
                await close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("closing the container failed", errors)


def build_container(settings: Settings) -> Container:
    """Create the adapter for every port. Raises AdapterNotAvailableError for a missing one."""
    persistence = _select("persistence", settings.db_type, PERSISTENCE, settings)
    closers: list[Closer] = [persistence.close]

    def opened[T](port: str, adapter: str, factories: Mapping[str, Factory[Opened[T]]]) -> T:
        built = _select(port, adapter, factories, settings)
        if built.close is not None:
            closers.append(built.close)
        return built.adapter

    object_store = opened("object_store", settings.storage_type, OBJECT_STORES)
    search_index = (
        opened("search_index", "meilisearch", SEARCH_INDEXES)
        if settings.meilisearch_url is not None
        else None
    )
    language_model = (
        opened("llm", "openai-compatible", LANGUAGE_MODELS)
        if settings.llm_base_url is not None
        else None
    )
    embeddings = (
        opened("embeddings", "openai-compatible", EMBEDDINGS)
        if settings.embedding_base_url is not None
        else None
    )
    return Container(
        unit_of_work=persistence.unit_of_work,
        event_bus=persistence.event_bus,
        wakeup=persistence.wakeup,
        clock=SystemClock(),
        object_store=object_store,
        ocr=_select("ocr", "ocrmypdf", OCR_ENGINES, settings),
        parser=_select("parser", "layout", PARSERS, settings),
        pages=_select("pages", "pdfium", PAGE_RENDERERS, settings),
        thumbnails=_select("pages", "pdfium", THUMBNAIL_RENDERERS, settings),
        locator=_select("locator", "pdfium", TEXT_LOCATORS, settings),
        codes=_select("codes", "zxing", CODE_READERS, settings),
        metadata=_select("metadata", "pikepdf", METADATA_READERS, settings),
        composer=_select("composer", "pikepdf", PAGE_COMPOSERS, settings),
        images=_select("images", "pillow", IMAGE_NORMALISERS, settings),
        password_hasher=Argon2PasswordHasher(),
        cipher=secret_cipher(settings),
        refs=ref_cipher(settings),
        webhook_sender=HttpWebhookSender(user_agent=USER_AGENT),
        push_sender=(
            WebPushSender(
                private_key=settings.push_vapid_private_key.get_secret_value(),
                subject=settings.push_subject,
                user_agent=USER_AGENT,
            )
            if settings.push_vapid_private_key is not None and settings.push_subject is not None
            else None
        ),
        mail_server=ImapMailServer(timeout=settings.mail_timeout),
        mail_renderer=WeasyPrintMailRenderer(
            settings.template_locale,
            timeout=settings.mail_render_timeout,
            memory=int(settings.child_max_memory),
        ),
        totp=PyotpTotp(),
        patterns=RegexPatternMatcher(settings.rules_pattern_timeout.total_seconds()),
        templates=LiquidTemplateRenderer(
            locale=settings.template_locale, currency=settings.default_currency
        ),
        oidc=(
            _select("oidc", "authlib", OIDC_PROVIDERS, settings) if settings.oidc_enabled else None
        ),
        search_index=search_index,
        language_model=language_model,
        embeddings=embeddings,
        classifier=(
            None
            if settings.classifier == "none"
            else _select("classifier", settings.classifier, CLASSIFIERS, settings)
        ),
        logo_fetcher=(
            _select("logo_fetcher", "httpx2", LOGO_FETCHERS, settings)
            if settings.logo_fetch
            else None
        ),
        closers=tuple(closers),
    )


def build_memory_container(
    clock: Clock | None = None, settings: Settings | None = None
) -> Container:
    """All ports on in-memory adapters, for tests and local experiments. Nothing persists.
    `settings`: for the two adapters that take tuning; the shipped defaults without."""
    settings = settings or Settings.model_construct()
    database = MemoryDatabase()
    return Container(
        unit_of_work=MemoryUnitOfWorkFactory(database),
        event_bus=MemoryEventBus(database, retry=event_retry_of(settings)),
        wakeup=MemoryWakeup(database),
        object_store=MemoryObjectStore(),
        clock=clock or SystemClock(),
        ocr=FakeOcr(),
        parser=FakeParser(),
        pages=FakePageRenderer(),
        thumbnails=FakePageRenderer(),
        locator=FakeTextLocator(),
        codes=FakeCodeReader(),
        metadata=FakeMetadataReader(),
        composer=FakePageComposer(),
        images=FakeImageNormaliser(),
        password_hasher=FakePasswordHasher(),
        cipher=FakeCipher(),
        refs=FakeRefCipher(),
        webhook_sender=FakeWebhookSender(),
        push_sender=FakePushSender(),
        mail_server=MemoryMailServer(),
        mail_renderer=FakeMailRenderer(),
        totp=FakeTotp(),
        patterns=RegexPatternMatcher(settings.rules_pattern_timeout.total_seconds()),
        templates=LiquidTemplateRenderer(
            locale=settings.template_locale, currency=settings.default_currency
        ),
        oidc=None,
        search_index=MemorySearchIndex(locales=settings.search_locales.split("+")),
        language_model=None,
        embeddings=None,
        classifier=FakeClassifier(),
    )


@dataclass(frozen=True)
class Services:
    """The use cases, wired to the container's adapters."""

    auth: AuthService
    oidc: OidcService | None  # with a configured provider
    users: UserService
    profiles: ProfileService
    spaces: SpaceService
    master_data: MasterDataService
    open_identifiers: OpenIdentifierService
    logos: LogoService
    rules: RuleService
    rule_applications: RuleApplicationService
    bulk: BulkService
    webhooks: WebhookService
    webhook_delivery: WebhookDeliveryService
    push: PushService
    tasks: TaskService
    lenses: LensService
    mailboxes: MailboxService
    mail_intake: MailIntakeService
    mail_rules: MailRuleService
    relations: RelationService
    expected: ExpectedService
    stream: StreamService
    documents: DocumentService
    inbox: InboxService
    pipeline: PipelineService
    editing: EditingService
    maintenance: MaintenanceService
    jobs: JobsService
    automation: AutomationService
    indexing: IndexingService | None  # with a search index
    search: SearchService | None  # with a search index
    classifier: ClassifierService | None  # with a classifier


VISION_REQUEST_TIMEOUT = timedelta(minutes=5)
"""How long the vision language model may take for one page."""


MODEL_CALLS_PER_NODE = 4
"""The most requests to the language model one node makes in a row: the proposal and the facts
of `signal_llm` (#145), each once more after an unfit answer."""


def node_lease(settings: Settings) -> timedelta:
    """How long a worker holds the job of a node: longer than any node may take, except the
    OCR of a document the vision model reads (`vision_lease`)."""
    longest = max(
        settings.ocr_timeout,
        settings.mail_render_timeout,
        MODEL_CALLS_PER_NODE * settings.llm_timeout,
    )
    return longest + WORK_LEASE_MARGIN


def vision_lease(settings: Settings) -> timedelta | None:
    """How long a worker holds the OCR of a document the vision model reads; None without a
    vision model, or if the lease of every node is as long."""
    if settings.vlm_base_url is None:
        return None
    lease = settings.vlm_timeout + WORK_LEASE_MARGIN
    return lease if lease > node_lease(settings) else None


def classifier_policy_of(settings: Settings) -> ClassifierPolicy:
    return ClassifierPolicy(
        min_examples=settings.classifier_min_examples,
        retrain_after=settings.classifier_retrain_after,
        threshold=settings.classifier_threshold,
    )


def thresholds_of(settings: Settings) -> Thresholds:
    """The judge's thresholds; the classifier's is the one of its policy."""
    return Thresholds(
        accept=settings.confidence_threshold,
        suggest=settings.contact_suggest_threshold,
        classifier=classifier_policy_of(settings).threshold,
    )


def retry_policy_of(settings: Settings) -> RetryPolicy:
    """Automatic retries of a node that raised."""
    return RetryPolicy(max_attempts=settings.node_max_attempts, delay=settings.node_retry_delay)


def event_retry_of(settings: Settings) -> RetryPolicy:
    """Repeated delivery of an event whose handler failed."""
    return RetryPolicy(
        max_attempts=settings.events_max_attempts,
        delay=DELIVERY_DELAY,
        max_delay=DELIVERY_MAX_DELAY,
    )


def session_policy_of(settings: Settings) -> SessionPolicy:
    return SessionPolicy(idle=settings.session_idle_timeout, max_age=settings.session_max_age)


def policy_of(settings: Settings) -> ClassificationPolicy:
    """Thresholds and limits of classification and field extraction."""
    return ClassificationPolicy(
        accept=settings.confidence_threshold,
        suggest_contact=settings.contact_suggest_threshold,
        input_budget=settings.llm_input_budget,
        max_tags=settings.llm_max_tags,
        default_currency=settings.default_currency,
        poor_reading=settings.poor_reading_threshold,
    )


def public_base(settings: Settings) -> str | None:
    """`LEKTO_PUBLIC_URL` without a slash at its end, what every absolute link starts with;
    None when it is not set."""
    return None if settings.public_url is None else str(settings.public_url).rstrip("/")


def links_of(settings: Settings) -> Links:
    """Where the core's links lead: `LEKTO_PUBLIC_URL`, the API's and the web UI's prefixes."""
    return Links(public=public_base(settings), api_prefix=API_PREFIX, ui_prefix=UI_PREFIX)


def webhook_policy_of(settings: Settings) -> WebhookPolicy:
    return WebhookPolicy(
        per_user=settings.webhooks_per_user,
        secret_grace=settings.webhook_secret_grace,
        max_attempts=settings.webhook_max_attempts,
        retry_delay=settings.webhook_retry_delay,
        disable_after=settings.webhook_disable_after,
        timeout=settings.webhook_timeout,
        private_targets=PrivateTargets(settings.webhook_private_targets),
    )


def _prefix(value: str | None) -> str:
    return "" if not value else value + " "


def neighbours_policy_of(settings: Settings) -> NeighboursPolicy:
    """The neighbours' vector is made as the index makes the first section's."""
    return NeighboursPolicy(
        count=settings.neighbours,
        chunk_size=settings.search_chunk_size,
        document_prefix=_prefix(settings.embedding_document_prefix),
        dimensions=settings.embedding_dimensions,
    )


def indexing_policy_of(settings: Settings) -> IndexingPolicy:
    return IndexingPolicy(
        max_text=settings.search_max_text,
        chunk_size=settings.search_chunk_size,
        max_chunks=settings.search_max_chunks,
        document_prefix=_prefix(settings.embedding_document_prefix),
        dimensions=settings.embedding_dimensions,
        reconcile_interval=settings.search_reconcile_interval,
        # An indexing job may embed and write up to three times (see `IndexingService`).
        job_lease=3 * (settings.embedding_timeout + settings.meilisearch_task_timeout)
        + WORK_LEASE_MARGIN,
        rebuild_lease=settings.search_rebuild_timeout,
        durations_window=settings.retention,
    )


def search_policy_of(settings: Settings) -> SearchPolicy:
    return SearchPolicy(
        semantic_ratio=settings.search_semantic_ratio,
        embed_timeout=settings.search_embed_timeout,
        query_prefix=_prefix(settings.embedding_query_prefix),
        dimensions=settings.embedding_dimensions,
        meaning_min_score=settings.search_meaning_min_score,
    )


def classification_nodes(
    container: Container,
    settings: Settings,
    *,
    model: LanguageModel | None,
    classifier: ClassifierService | None,
    index: SearchIndex | None,
    embeddings: Embeddings | None,
    facts: FactsSignal,
    locator: TextLocator | None,
    desk: TaskDesk | None = None,
) -> dict[Node, NodeExecutor]:
    """The signals, the judge and the fields node, each taking over the metadata a document
    came in with (`ImportedSignal`, ...): for the container and, with a model per case, for
    the evaluation. `desk`: a webhook may take over the model calls (not in the evaluation)."""
    uow, clock, store = container.unit_of_work, container.clock, container.object_store
    policy = policy_of(settings)
    signals: dict[Node, NodeExecutor] = {
        Node.SIGNAL_LLM: LlmSignal(uow, store, model, clock, policy, desk=desk),
        Node.SIGNAL_FACTS: facts,
        Node.SIGNAL_CLASSIFIER: ClassifierSignal(store, classifier, uow),
        Node.SIGNAL_NEIGHBOURS: NeighboursSignal(
            uow, store, index, embeddings, neighbours_policy_of(settings)
        ),
    }
    return {node: ImportedSignal(uow, signal) for node, signal in signals.items()} | {
        Node.JUDGE: ImportedJudgeNode(
            uow,
            JudgeNode(
                uow, store, clock, policy, thresholds=thresholds_of(settings), locator=locator
            ),
        ),
        Node.FIELDS: ImportedFieldsNode(
            uow, FieldsNode(uow, store, model, clock, policy, locator=locator, desk=desk)
        ),
    }


def build_services(container: Container, settings: Settings | None = None) -> Services:
    """The use cases; tuning (retries, time limits, cleanup) from `settings`, or the defaults.

    OCR, parsing, classification and field extraction run on the container's adapters
    (without a language model, classification is uncertain), then the rules and filing.
    """
    settings = settings or Settings.model_construct()
    uow, clock, store = container.unit_of_work, container.clock, container.object_store
    classifier = (
        None
        if container.classifier is None
        else ClassifierService(
            uow,
            store,
            clock,
            container.classifier,
            classifier_policy_of(settings),
        )
    )
    index, embeddings = container.search_index, container.embeddings
    facts = FactsSignal(uow, store, container.codes)
    inbox = InboxService(uow, clock)
    links = links_of(settings)
    webhook_policy = webhook_policy_of(settings)
    desk = TaskDesk(container.cipher, container.templates, links=links)
    executors: dict[Node, NodeExecutor] = {
        Node.OCR: OcrNode(store, container.ocr, container.mail_renderer),
        Node.PAGES: PagesNode(store, container.pages, container.mail_renderer),
        Node.PARSE: ParseNode(store, container.parser),
        **classification_nodes(
            container,
            settings,
            model=container.language_model,
            classifier=classifier,
            index=index,
            embeddings=embeddings,
            facts=facts,
            locator=container.locator,
            desk=desk,
        ),
        Node.RELATE: RelateNode(),
        Node.APPLY_RULES: ApplyRulesNode(
            uow,
            store,
            container.patterns,
            container.templates,
            max_text=settings.rules_max_text,
            desk=desk,
            links=links,
        ),
        Node.FILE: FileNode(),
    }
    auth = AuthService(
        uow,
        clock,
        hasher=container.password_hasher,
        cipher=container.cipher,
        totp=container.totp,
        sessions=session_policy_of(settings),
    )
    change_rules = ChangeRules(
        store,
        container.patterns,
        container.templates,
        max_text=settings.rules_max_text,
        pipeline_version=__version__,
    )
    master_data = MasterDataService(
        uow,
        clock,
        container.templates,
        index_renames=index is not None,
        store=store,
        fetch_logos=container.logo_fetcher is not None,
    )
    documents = DocumentService(
        uow,
        clock,
        store,
        metadata=container.metadata,
        rules=change_rules,
        text_max=settings.mcp_text_max,
    )
    pipeline = PipelineService(
        uow,
        clock,
        store,
        executors,
        pipeline_version=__version__,
        suggest_contact=settings.contact_suggest_threshold,
        retry=retry_policy_of(settings),
        # Longer than any node may take, so a running node never loses its claim.
        # The model's signal asks the model up to four times (proposal and facts, each once
        # more after an invalid answer).
        # The OCR node that reads a document with the vision model extends its claim.
        lease=node_lease(settings),
        vision=container.ocr.vision,
        vision_lease=vision_lease(settings),
        poor_reading=settings.poor_reading_threshold,
        facts=facts,
    )
    search = (
        None
        if index is None
        else SearchService(
            uow, index, search_policy_of(settings), embeddings=embeddings, clock=clock, store=store
        )
    )
    return Services(
        auth=auth,
        oidc=(
            None
            if container.oidc is None
            else OidcService(
                uow,
                clock,
                auth,
                container.oidc,
                container.cipher,
                display_name=settings.oidc_display_name,
                auto_create=settings.oidc_auto_create,
            )
        ),
        users=UserService(uow, clock, container.password_hasher, rules=change_rules),
        profiles=ProfileService(uow, clock),
        spaces=SpaceService(uow, clock),
        master_data=master_data,
        open_identifiers=OpenIdentifierService(uow, store, master_data),
        logos=LogoService(uow, clock, store, container.images, container.logo_fetcher),
        rules=RuleService(
            uow,
            clock,
            container.templates,
            container.patterns,
            links=links,
            store=store,
        ),
        webhooks=WebhookService(
            uow,
            clock,
            container.cipher,
            webhook_policy,
            container.templates,
            retention=settings.retention,
        ),
        lenses=LensService(uow, clock),
        push=PushService(uow, clock, container.push_sender, inbox, links=links),
        mailboxes=MailboxService(uow, clock, container.cipher, container.mail_server),
        relations=RelationService(uow, clock),
        expected=ExpectedService(uow, clock),
        stream=StreamService(uow, clock),
        tasks=TaskService(uow, clock, container.cipher, store),
        jobs=JobsService(uow, clock, retention=settings.retention),
        automation=AutomationService(uow, clock),
        webhook_delivery=WebhookDeliveryService(
            uow,
            clock,
            container.cipher,
            container.webhook_sender,
            webhook_policy,
            container.templates,
            links=links,
            store=store,
        ),
        rule_applications=RuleApplicationService(
            uow,
            clock,
            store,
            container.patterns,
            container.templates,
            max_text=settings.rules_max_text,
            max_documents=settings.rules_apply_max_documents,
            pipeline_version=__version__,
        ),
        documents=documents,
        inbox=inbox,
        pipeline=pipeline,
        editing=EditingService(
            uow,
            clock,
            store,
            container.composer,
            container.thumbnails,
            pipeline_version=__version__,
        ),
        mail_rules=MailRuleService(uow, clock),
        mail_intake=MailIntakeService(
            uow,
            clock,
            container.cipher,
            container.mail_server,
            pipeline,
            max_attachment=int(settings.upload_max_size),
        ),
        bulk=BulkService(uow, clock, documents, pipeline, search),
        maintenance=MaintenanceService(
            uow,
            clock,
            container.event_bus,
            interval=settings.cleanup_interval,
            retention=settings.retention,
            session_idle=settings.session_idle_timeout,
            object_store=store,
        ),
        indexing=(
            None
            if index is None
            else IndexingService(
                uow, clock, store, index, indexing_policy_of(settings), embeddings=embeddings
            )
        ),
        search=search,
        classifier=classifier,
    )


def _select[T](
    port: str, adapter: str, factories: Mapping[str, Factory[T]], settings: Settings
) -> T:
    try:
        factory = factories[adapter]
    except KeyError:
        raise AdapterNotAvailableError(port, adapter) from None
    return factory(settings)
