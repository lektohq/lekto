from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self

from lekto.core.ports.event_bus import Outbox
from lekto.core.ports.identity import (
    ApiTokenRepository,
    CredentialRepository,
    ExternalIdentityRepository,
    KnownDeviceRepository,
    LoginFailureRepository,
    SessionRepository,
)
from lekto.core.ports.instance import InstanceRepository
from lekto.core.ports.job_queue import JobQueue
from lekto.core.ports.push import PushDeviceRepository, PushPreferencesRepository
from lekto.core.ports.repository import (
    BulkOperationRepository,
    ClassifierModelRepository,
    ContactRepository,
    DocumentFactRepository,
    DocumentRelationRepository,
    DocumentRepository,
    DocumentTypeRepository,
    DocumentVersionRepository,
    FieldDefinitionRepository,
    InboxRepository,
    LensRepository,
    MailboxRepository,
    MailOriginRepository,
    MailRecordRepository,
    MailRuleRepository,
    ProcessingFacts,
    ProcessingLog,
    ProfileRepository,
    RuleApplicationRepository,
    RuleRepository,
    SpaceRepository,
    TagRepository,
    TaskRepository,
    UserRepository,
    WebhookRepository,
)


class UnitOfWork(Protocol):
    """One transaction over repositories (rules, webhooks, tasks and the inbox included),
    processing log, outbox, job queue and identity.

    State change, events and jobs are committed together or not at all:

        async with uow_factory() as uow:
            document = await uow.documents.get(document_id)
            ...
            await uow.documents.update(document)
            await uow.outbox.add(document.pull_events())
            await uow.commit()

    Leaving the block without `commit` (or with an exception) rolls back. Changes are visible
    to other units of work only after commit; within the unit, reads see its own changes.
    After commit or rollback the unit is closed and cannot be used again.
    """

    users: UserRepository
    profiles: ProfileRepository
    spaces: SpaceRepository
    contacts: ContactRepository
    document_types: DocumentTypeRepository
    tags: TagRepository
    fields: FieldDefinitionRepository
    documents: DocumentRepository
    processing_log: ProcessingLog
    processing_facts: ProcessingFacts
    document_facts: DocumentFactRepository

    document_relations: DocumentRelationRepository
    document_versions: DocumentVersionRepository
    inbox: InboxRepository
    rules: RuleRepository
    rule_applications: RuleApplicationRepository
    bulk_operations: BulkOperationRepository
    classifier_models: ClassifierModelRepository
    webhooks: WebhookRepository
    tasks: TaskRepository
    lenses: LensRepository
    mailboxes: MailboxRepository
    mail_records: MailRecordRepository
    mail_origins: MailOriginRepository
    mail_rules: MailRuleRepository
    outbox: Outbox
    jobs: JobQueue
    credentials: CredentialRepository
    sessions: SessionRepository
    api_tokens: ApiTokenRepository
    external_identities: ExternalIdentityRepository
    known_devices: KnownDeviceRepository
    push_devices: PushDeviceRepository
    push_preferences: PushPreferencesRepository
    instance: InstanceRepository
    login_failures: LoginFailureRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    async def lock(self, name: str) -> None:
        """Hold an exclusive lock on `name` until this unit ends (commit or rollback). Other
        units that lock the same name wait meanwhile. For work outside the database that must
        not interleave, e.g. storing and deleting the same original. Lock at most one name per
        unit, before its other writes."""
        ...

    async def commit(self) -> None:
        """Make all changes durable and visible. ConflictError or ConcurrencyError if a
        uniqueness rule or a version check fails; then nothing is stored."""
        ...

    async def rollback(self) -> None: ...


type UnitOfWorkFactory = Callable[[], UnitOfWork]
