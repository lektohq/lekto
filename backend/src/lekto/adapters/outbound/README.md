# Outbound adapters

The adapters the core calls through its ports, the protocols in [`core/ports`](../../core/ports).
A folder holds one technology, a library or a service. One technology can serve several ports
(`sql`, `pdfium`, `pikepdf`) and one port can have several adapters (`ObjectStore`: S3, the file
system, memory), so the folders do not show the ports. The classes do: every adapter names its
port among its bases (`class S3ObjectStore(ObjectStore)`), so "Go to Implementations" on a port
lists its adapters and mypy checks an adapter where it is defined. Only `composition` decides
which adapter runs.

`memory` holds the in-memory adapters for the tests and the memory container; the pattern matcher
(`regex`) and the template renderer (`liquid`) have none and serve that container too.
`http_client`, `imaging.py` and `system/process.py` implement no port: they are helpers of the
adapters.

## Ports and their adapters

`tests/unit/test_outbound_adapters.py` builds this table from the classes and fails when it
differs; its message holds the table to paste. `Repository` and `NamedRepository` are missing
on purpose: they are the bases of the repository ports below.

<!-- ports:start -->
| Port | Adapters |
| --- | --- |
| [`Classifier`](../../core/ports/classifier.py) | [`FakeClassifier`](memory/classifier.py), [`SklearnClassifier`](sklearn/classifier.py) |
| [`Clock`](../../core/ports/clock.py) | [`ManualClock`](memory/clock.py), [`SystemClock`](system/clock.py) |
| [`CodeReader`](../../core/ports/codes.py) | [`FakeCodeReader`](memory/processing.py), [`ZxingCodeReader`](zxing/reader.py) |
| [`PageComposer`](../../core/ports/composer.py) | [`FakePageComposer`](memory/processing.py), [`PikepdfPageComposer`](pikepdf/composer.py) |
| [`Embeddings`](../../core/ports/embeddings.py) | [`BagOfWordsEmbeddings`](memory/language_model.py), [`FakeEmbeddings`](memory/language_model.py), [`OpenAiCompatEmbeddings`](openai_compat/client.py) |
| [`Outbox`](../../core/ports/event_bus.py) | [`MemoryOutbox`](memory/unit_of_work.py), [`SqlOutbox`](sql/unit_of_work.py) |
| [`EventBus`](../../core/ports/event_bus.py) | [`MemoryEventBus`](memory/event_bus.py), [`SqlEventBus`](sql/event_bus.py) |
| [`CredentialRepository`](../../core/ports/identity.py) | [`MemoryCredentialRepository`](memory/identity.py), [`SqlCredentialRepository`](sql/identity.py) |
| [`SessionRepository`](../../core/ports/identity.py) | [`MemorySessionRepository`](memory/identity.py), [`SqlSessionRepository`](sql/identity.py) |
| [`ApiTokenRepository`](../../core/ports/identity.py) | [`MemoryApiTokenRepository`](memory/identity.py), [`SqlApiTokenRepository`](sql/identity.py) |
| [`KnownDeviceRepository`](../../core/ports/identity.py) | [`MemoryKnownDeviceRepository`](memory/identity.py), [`SqlKnownDeviceRepository`](sql/identity.py) |
| [`ExternalIdentityRepository`](../../core/ports/identity.py) | [`MemoryExternalIdentityRepository`](memory/identity.py), [`SqlExternalIdentityRepository`](sql/identity.py) |
| [`LoginFailureRepository`](../../core/ports/identity.py) | [`MemoryLoginFailureRepository`](memory/identity.py), [`SqlLoginFailureRepository`](sql/identity.py) |
| [`PasswordHasher`](../../core/ports/identity.py) | [`Argon2PasswordHasher`](crypto/argon2.py), [`FakePasswordHasher`](memory/crypto.py) |
| [`SecretCipher`](../../core/ports/identity.py) | [`AesGcmCipher`](crypto/cipher.py), [`FakeCipher`](memory/crypto.py) |
| [`RefCipher`](../../core/ports/identity.py) | [`AesSivRefCipher`](crypto/refs.py), [`FakeRefCipher`](memory/crypto.py) |
| [`Totp`](../../core/ports/identity.py) | [`PyotpTotp`](crypto/totp.py), [`FakeTotp`](memory/crypto.py) |
| [`OidcProvider`](../../core/ports/identity.py) | [`FakeOidcProvider`](memory/oidc.py), [`AuthlibOidcProvider`](oidc/provider.py) |
| [`ImageNormaliser`](../../core/ports/images.py) | [`FakeImageNormaliser`](memory/images.py), [`PillowImageNormaliser`](pillow/images.py) |
| [`InstanceRepository`](../../core/ports/instance.py) | [`MemoryInstanceRepository`](memory/instance.py), [`SqlInstanceRepository`](sql/instance.py) |
| [`JobQueue`](../../core/ports/job_queue.py) | [`MemoryJobQueue`](memory/unit_of_work.py), [`SqlJobQueue`](sql/job_queue.py) |
| [`LanguageModel`](../../core/ports/llm.py) | [`FakeLanguageModel`](memory/language_model.py), [`OpenAiCompatLanguageModel`](openai_compat/client.py) |
| [`TextLocator`](../../core/ports/locator.py) | [`FakeTextLocator`](memory/processing.py), [`PdfiumTextLocator`](pdfium/locator.py) |
| [`LogoFetcher`](../../core/ports/logos.py) | [`HttpLogoFetcher`](logos/fetcher.py), [`FakeLogoFetcher`](memory/logos.py) |
| [`MailRenderer`](../../core/ports/mail_renderer.py) | [`FakeMailRenderer`](memory/processing.py), [`WeasyPrintMailRenderer`](weasyprint/renderer.py) |
| [`MailSession`](../../core/ports/mail_server.py) | [`ImapMailSession`](imap/session.py), [`MemoryMailSession`](memory/mail_server.py) |
| [`MailServer`](../../core/ports/mail_server.py) | [`ImapMailServer`](imap/server.py), [`MemoryMailServer`](memory/mail_server.py) |
| [`MetadataReader`](../../core/ports/metadata.py) | [`FakeMetadataReader`](memory/processing.py), [`FileMetadataReader`](pikepdf/metadata.py) |
| [`ObjectStore`](../../core/ports/object_store.py) | [`FilesystemObjectStore`](filesystem/object_store.py), [`MemoryObjectStore`](memory/object_store.py), [`S3ObjectStore`](s3/object_store.py) |
| [`Ocr`](../../core/ports/ocr.py) | [`FakeOcr`](memory/processing.py), [`OcrmypdfEngine`](ocrmypdf/engine.py) |
| [`PageRenderer`](../../core/ports/pages.py) | [`FakePageRenderer`](memory/processing.py), [`PdfiumPageRenderer`](pdfium/pages.py) |
| [`DocumentParser`](../../core/ports/parser.py) | [`FakeParser`](memory/processing.py), [`LayoutParser`](pdfium/layout.py) |
| [`PatternMatcher`](../../core/ports/patterns.py) | [`RegexPatternMatcher`](regex/matcher.py) |
| [`PushDeviceRepository`](../../core/ports/push.py) | [`MemoryPushDeviceRepository`](memory/push.py), [`SqlPushDeviceRepository`](sql/push.py) |
| [`PushPreferencesRepository`](../../core/ports/push.py) | [`MemoryPushPreferencesRepository`](memory/push.py), [`SqlPushPreferencesRepository`](sql/push.py) |
| [`PushSender`](../../core/ports/push.py) | [`FakePushSender`](memory/push.py), [`WebPushSender`](webpush/sender.py) |
| [`ReleaseFeed`](../../core/ports/releases.py) | [`GitHubReleaseFeed`](github/releases.py), [`FakeReleaseFeed`](memory/releases.py) |
| [`UserRepository`](../../core/ports/repository.py) | [`MemoryUserRepository`](memory/unit_of_work.py), [`SqlUserRepository`](sql/users.py) |
| [`ProfileRepository`](../../core/ports/repository.py) | [`MemoryProfileRepository`](memory/unit_of_work.py), [`SqlProfileRepository`](sql/users.py) |
| [`SpaceRepository`](../../core/ports/repository.py) | [`MemorySpaceRepository`](memory/unit_of_work.py), [`SqlSpaceRepository`](sql/spaces.py) |
| [`ContactRepository`](../../core/ports/repository.py) | [`MemoryContactRepository`](memory/unit_of_work.py), [`SqlContactRepository`](sql/master_data.py) |
| [`DocumentTypeRepository`](../../core/ports/repository.py) | [`MemoryDocumentTypeRepository`](memory/unit_of_work.py), [`SqlDocumentTypeRepository`](sql/master_data.py) |
| [`TagRepository`](../../core/ports/repository.py) | [`MemoryTagRepository`](memory/unit_of_work.py), [`SqlTagRepository`](sql/master_data.py) |
| [`FieldDefinitionRepository`](../../core/ports/repository.py) | [`MemoryFieldDefinitionRepository`](memory/unit_of_work.py), [`SqlFieldRepository`](sql/master_data.py) |
| [`DocumentRepository`](../../core/ports/repository.py) | [`MemoryDocumentRepository`](memory/unit_of_work.py), [`SqlDocumentRepository`](sql/documents.py) |
| [`DocumentVersionRepository`](../../core/ports/repository.py) | [`MemoryDocumentVersionRepository`](memory/unit_of_work.py), [`SqlDocumentVersionRepository`](sql/versions.py) |
| [`DocumentRelationRepository`](../../core/ports/repository.py) | [`MemoryDocumentRelationRepository`](memory/unit_of_work.py), [`SqlDocumentRelationRepository`](sql/relations.py) |
| [`DocumentFactRepository`](../../core/ports/repository.py) | [`MemoryDocumentFactRepository`](memory/unit_of_work.py), [`SqlDocumentFactRepository`](sql/facts.py) |
| [`InboxRepository`](../../core/ports/repository.py) | [`MemoryInboxRepository`](memory/inbox.py), [`SqlInboxRepository`](sql/inbox.py) |
| [`ProcessingLog`](../../core/ports/repository.py) | [`MemoryProcessingLog`](memory/unit_of_work.py), [`SqlProcessingLog`](sql/documents.py) |
| [`ProcessingFacts`](../../core/ports/repository.py) | [`MemoryProcessingFacts`](memory/processing_facts.py), [`SqlProcessingFacts`](sql/processing_facts.py) |
| [`RuleRepository`](../../core/ports/repository.py) | [`MemoryRuleRepository`](memory/rules.py), [`SqlRuleRepository`](sql/rules.py) |
| [`RuleApplicationRepository`](../../core/ports/repository.py) | [`MemoryRuleApplicationRepository`](memory/rules.py), [`SqlRuleApplicationRepository`](sql/rules.py) |
| [`BulkOperationRepository`](../../core/ports/repository.py) | [`MemoryBulkOperationRepository`](memory/rules.py), [`SqlBulkOperationRepository`](sql/bulk.py) |
| [`ClassifierModelRepository`](../../core/ports/repository.py) | [`MemoryClassifierModelRepository`](memory/classifier_models.py), [`SqlClassifierModelRepository`](sql/classifier_models.py) |
| [`LensRepository`](../../core/ports/repository.py) | [`MemoryLensRepository`](memory/lenses.py), [`SqlLensRepository`](sql/lenses.py) |
| [`MailboxRepository`](../../core/ports/repository.py) | [`MemoryMailboxRepository`](memory/mailboxes.py), [`SqlMailboxRepository`](sql/mailboxes.py) |
| [`MailRecordRepository`](../../core/ports/repository.py) | [`MemoryMailRecordRepository`](memory/mail_records.py), [`SqlMailRecordRepository`](sql/mail_records.py) |
| [`MailRuleRepository`](../../core/ports/repository.py) | [`MemoryMailRuleRepository`](memory/mail_rules.py), [`SqlMailRuleRepository`](sql/mail_rules.py) |
| [`MailOriginRepository`](../../core/ports/repository.py) | [`MemoryMailOriginRepository`](memory/mail_records.py), [`SqlMailOriginRepository`](sql/mail_records.py) |
| [`WebhookRepository`](../../core/ports/repository.py) | [`MemoryWebhookRepository`](memory/webhooks.py), [`SqlWebhookRepository`](sql/webhooks.py) |
| [`TaskRepository`](../../core/ports/repository.py) | [`MemoryTaskRepository`](memory/tasks.py), [`SqlTaskRepository`](sql/tasks.py) |
| [`IndexBuild`](../../core/ports/search_index.py) | [`_MeilisearchBuild`](meilisearch/index.py), [`_MemoryBuild`](memory/search_index.py) |
| [`SearchIndex`](../../core/ports/search_index.py) | [`MeilisearchIndex`](meilisearch/index.py), [`MemorySearchIndex`](memory/search_index.py) |
| [`TemplateRenderer`](../../core/ports/templates.py) | [`LiquidTemplateRenderer`](liquid/renderer.py) |
| [`UnitOfWork`](../../core/ports/unit_of_work.py) | [`MemoryUnitOfWork`](memory/unit_of_work.py), [`SqlUnitOfWork`](sql/unit_of_work.py) |
| [`Signal`](../../core/ports/wakeup.py) | [`InProcessSignal`](signals.py) |
| [`Wakeup`](../../core/ports/wakeup.py) | [`MemoryWakeup`](memory/wakeup.py), [`SqlWakeup`](sql/wakeup.py) |
| [`WebhookSender`](../../core/ports/webhook_sender.py) | [`FakeWebhookSender`](memory/webhook_sender.py), [`HttpWebhookSender`](webhooks/sender.py) |
<!-- ports:end -->
