# Configuration

Lekto is configured with environment variables only; there is no configuration file. Every
variable starts with `LEKTO_`. This page lists them all, with their defaults, the values they
take and what they do.

- [How the variables are read](#how-the-variables-are-read)
- [The least a production setup sets](#the-least-a-production-setup-sets)
- Lekto: [Services and logs](#services-and-logs) · [Database](#database) ·
  [Object store](#object-store) · [API and web UI](#api-and-web-ui) ·
  [Sign-in and sessions](#sign-in-and-sessions) · [OpenID Connect](#openid-connect) ·
  [Webhooks](#webhooks) · [MCP](#mcp) · [Worker](#worker) · [OCR and mail](#ocr-and-mail) ·
  [Search](#search) · [Language model](#language-model) · [Embeddings](#embeddings) ·
  [Vision model](#vision-model) · [Classification](#classification) ·
  [Notifications](#notifications) · [Logos](#logos) ·
  [Rules and templates](#rules-and-templates)
- [The image](#the-image) · [The migration client](#the-migration-client)

## How the variables are read

- **Checked at start.** Invalid or contradictory values stop the start with a message that names
  every variable concerned. `lekto check` (in the image: `lekto-run lekto check`) prints the
  effective configuration, secrets masked. A `LEKTO_` variable that matches no setting is logged
  as a warning (usually a typo); a variable that was renamed is an error that names the new one.
- **Secrets** (*secret* below) can also come from a file: `LEKTO_<NAME>_FILE=/run/secrets/…`
  (Docker secrets). The file's content, without one trailing newline, is the value. Setting both
  `LEKTO_<NAME>` and `LEKTO_<NAME>_FILE` is an error. In the image the files must be readable by
  `PUID`:`PGID`.
- **Blank is unset.** Surrounding whitespace is removed, a blank value counts as not set, and
  choices ignore case (`LEKTO_DB_TYPE=Postgres` works).
- **Variables of the other variant** (`LEKTO_DB_HOST` with `LEKTO_DB_TYPE=sqlite`) are not
  required, but must still be well-formed if set.
- **From a file on the command line.** `lekto --env-file FILE …` takes the `LEKTO_` variables of
  a file of `KEY=value` lines in place of the environment's (the development instance in the
  devcontainer uses it, see [.devcontainer/README.md](../.devcontainer/README.md)).

**Role** says which service reads a variable: `API`, `Worker` or `both`. A container with
`LEKTO_ROLE=all` (the default) needs them all; separate API and worker containers need only
theirs, the connection and storage settings in both.

**Values** names what a variable takes:

| Values | Means |
| --- | --- |
| `a`, `b` | one of these words |
| `true`, `false` | a switch (`1`/`0`, `yes`/`no`, `on`/`off` work too) |
| `1–64` | a number in this range, both ends included |
| more than 0, at most 1 | a number above 0 and up to 1 |
| duration | seconds (`30`, `1.5`) or ISO 8601 (`PT1H`, `P7D`); always more than 0 |
| size | bytes (`1048576`) or with a unit (`50MB`, `100MiB`, `1GiB`) |
| URL | `http://` or `https://`, e.g. `http://ollama:11434/v1` |
| path | a path in the file system of the container |
| text | any text |
| *secret* | also as `LEKTO_<NAME>_FILE`; never shown in logs or by `lekto check` |

## The least a production setup sets

```sh
LEKTO_SECRET_KEY_FILE=/run/secrets/lekto_secret_key    # openssl rand -base64 32
LEKTO_ADMIN_USERNAME=admin
LEKTO_ADMIN_PASSWORD_FILE=/run/secrets/lekto_admin_password
LEKTO_FORWARDED_ALLOW_IPS=172.18.0.10                  # the reverse proxy in front of Lekto
LEKTO_PUBLIC_URL=https://lekto.example.org
LEKTO_MEILISEARCH_URL=http://meilisearch:7700
LEKTO_MEILISEARCH_API_KEY_FILE=/run/secrets/meili_master_key
LEKTO_LLM_BASE_URL=http://ollama:11434/v1
LEKTO_LLM_MODEL=qwen3:8b
LEKTO_EMBEDDING_BASE_URL=http://ollama:11434/v1
LEKTO_EMBEDDING_MODEL=snowflake-arctic-embed2
LEKTO_EMBEDDING_DIMENSIONS=1024
```

Without Meilisearch there is no search; without a language model documents wait yellow for a
person; without embeddings the search finds words only. The Compose examples in
[docker/](../docker/) show complete setups; [deploy/README.md](../deploy/README.md) covers the
image, the reverse proxy and backups.

## Services and logs

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_ROLE` | both | `all` | `all`, `api`, `worker` | Which services run in this container (the image's s6 scripts read it); see [deploy/README.md](../deploy/README.md#roles) |
| `LEKTO_LOG_FORMAT` | both | `json` | `json`, `console` | `console` for people, `json` for log collectors |
| `LEKTO_LOG_LEVEL` | both | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | The least important messages logged |

## Database

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_DB_TYPE` | both | `sqlite` | `sqlite`, `postgres` | SQLite for one container, Postgres for several or for size |
| `LEKTO_DB_SQLITE_PATH` | both | `data/lekto.db`; image: `/data/lekto.db` | path | SQLite only; on a local volume (WAL), never a network share |
| `LEKTO_DB_HOST` | both | – | text | Postgres only, required |
| `LEKTO_DB_PORT` | both | `5432` | 1–65,535 | Postgres only |
| `LEKTO_DB_NAME` | both | – | text | Postgres only, required |
| `LEKTO_DB_USER` | both | – | text | Postgres only, required |
| `LEKTO_DB_PASSWORD` | both | – | text, *secret* | Postgres only, required |

## Object store

Originals, archive PDFs, page images and the classifier's models.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_STORAGE_TYPE` | both | `filesystem` | `filesystem`, `s3` | A directory or an S3 bucket |
| `LEKTO_STORAGE_PATH` | both | `data/objects`; image: `/data/objects` | path | File system only |
| `LEKTO_S3_ENDPOINT_URL` | both | – | URL | S3 only, required, e.g. `http://garage:3900` |
| `LEKTO_S3_REGION` | both | `us-east-1` | text | S3 only |
| `LEKTO_S3_BUCKET` | both | – | text | S3 only, required |
| `LEKTO_S3_ACCESS_KEY_ID` | both | – | text, *secret* | S3 only, required |
| `LEKTO_S3_SECRET_ACCESS_KEY` | both | – | text, *secret* | S3 only, required |
| `LEKTO_S3_PATH_STYLE` | both | `true` | `true`, `false` | Path-style addressing (Garage needs it) |

## API and web UI

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_API_HOST` | API | `0.0.0.0` | text | Where the API listens |
| `LEKTO_API_PORT` | API | `8000` | 0–65,535 | `0`: the operating system picks a free port, which the log line `api started` names (for tests; the image's health check needs a fixed port) |
| `LEKTO_UPLOAD_MAX_SIZE` | API | `100MiB` | size | Largest upload; a reverse proxy's body limit must allow it |
| `LEKTO_REQUEST_MAX_SIZE` | API | `1MiB` | size | Largest body of every other request (JSON); larger ones get `413` |
| `LEKTO_UI_DIR` | API | –; image: `/opt/lekto/ui` | path | The built web UI (`web/build`), served below `/ui`; `/` leads there. Must contain `index.html`; unset serves the API only |
| `LEKTO_FORWARDED_ALLOW_IPS` | API | –; required with `LEKTO_COOKIE_SECURE=true` | text | Reverse proxies whose `X-Forwarded-For` is trusted, comma-separated. Secure cookies mean a TLS-terminating proxy in front of Lekto: name its address, or the per-source throttle of sign-ins sees only the proxy. `*` only if the proxy sets the header itself, replacing what clients send |

## Sign-in and sessions

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_SECRET_KEY` | both | required | text, *secret* | 32 bytes, base64 (`openssl rand -base64 32`). Encrypts TOTP secrets, webhook secrets and header values and the passwords of mailboxes; the worker decrypts what it needs to send and fetch. Keep it: without it they cannot be read. The development key from the repository is refused with secure cookies |
| `LEKTO_ADMIN_USERNAME` | API | – | text | The first admin, created at API start while there is no active admin; set together with the password |
| `LEKTO_ADMIN_PASSWORD` | API | – | text, *secret* | See `LEKTO_ADMIN_USERNAME` |
| `LEKTO_SESSION_IDLE_TIMEOUT` | API | `P1D` | duration | A session ends when unused this long |
| `LEKTO_SESSION_MAX_AGE` | API | `P30D` | duration | A session ends this long after sign-in; not shorter than the idle timeout |
| `LEKTO_COOKIE_SECURE` | API | `true` | `true`, `false` | `false` only for development over plain HTTP: the session cookie loses `Secure` |
| `LEKTO_PUBLIC_URL` | API | – | URL | Where browsers reach Lekto (`https://lekto.example.org`); required with OpenID Connect |

## OpenID Connect

One provider, Authorization Code Flow with PKCE. Set issuer, client id and client secret together
or none, and register `<LEKTO_PUBLIC_URL>/api/v1/auth/oidc/callback` as redirect URI.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_OIDC_ISSUER` | API | – | text | An `https` URL without query, compared exactly |
| `LEKTO_OIDC_CLIENT_ID` | API | – | text | The client at the provider |
| `LEKTO_OIDC_CLIENT_SECRET` | API | – | text, *secret* | Its secret |
| `LEKTO_OIDC_SCOPES` | API | `openid profile email` | text | Scopes, separated by spaces; must contain `openid` |
| `LEKTO_OIDC_DISPLAY_NAME` | API | `Single sign-on` | text | The provider's name on the sign-in page |
| `LEKTO_OIDC_AUTO_CREATE` | API | `false` | `true`, `false` | Create a user at the first sign-in of an unknown provider account |
| `LEKTO_OIDC_USERNAME_CLAIM` | API | `preferred_username` | text | The ID token claim that names such a user |

## Webhooks

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_WEBHOOKS_PER_USER` | API | `20` | 1–1,000 | Webhooks a user may have |
| `LEKTO_WEBHOOK_SECRET_GRACE` | API | `P1D` | duration | How long the old secret still signs after renewing; the cleanup drops it afterwards |
| `LEKTO_WEBHOOK_TIMEOUT` | Worker | `10` | duration, 1–120 s | Time per delivery attempt |
| `LEKTO_WEBHOOK_MAX_ATTEMPTS` | Worker | `10` | 1–50 | Attempts per delivery |
| `LEKTO_WEBHOOK_RETRY_DELAY` | Worker | `30` | duration | Before the second attempt, doubling after, at most an hour |
| `LEKTO_WEBHOOK_DISABLE_AFTER` | Worker | `20` | 1–10,000 | Deliveries given up in a row until a webhook is switched off |
| `LEKTO_WEBHOOK_CONCURRENCY` | Worker | `4` | 1–64 | Deliveries at the same time |

## MCP

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_MCP_ENABLED` | API | `true` | `true`, `false` | Serve the MCP server at `/api/v1/mcp` (tools for AI clients, API tokens as bearer) |
| `LEKTO_MCP_TEXT_MAX` | API | `20000` | 1,000–1,000,000 | Characters one `documents_text` call and one piece of `GET /documents/{id}/text` return at most |

## Worker

Background jobs, the delivery of events and the cleanup.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_WORKER_CONCURRENCY` | Worker | `2` | 1–64 | Jobs at the same time; OCR shares the CPU cores among them |
| `LEKTO_WORKER_POLL_INTERVAL` | Worker | `1` | duration | How often the worker looks for due jobs while no signal reaches it |
| `LEKTO_WORKER_SHUTDOWN_TIMEOUT` | Worker | `30` | duration | Time running jobs get to finish on SIGTERM; raise the image's grace times with it ([deploy/README.md](../deploy/README.md#stopping)) |
| `LEKTO_NODE_MAX_ATTEMPTS` | Worker | `3` | 1–20 | Attempts of a processing step that fails |
| `LEKTO_NODE_RETRY_DELAY` | Worker | `30` | duration | Before its second attempt, doubling after |
| `LEKTO_EVENTS_POLL_INTERVAL` | Worker | `1` | duration | How often the outbox is dispatched while no signal comes |
| `LEKTO_EVENTS_MAX_ATTEMPTS` | Worker | `10` | 1–100 | Delivery attempts of an event per subscriber |
| `LEKTO_CLEANUP_INTERVAL` | Worker | `3600` | duration | Time between cleanups |
| `LEKTO_RETENTION` | Worker | `P7D` | duration | Age from which finished jobs, delivered events and webhook log rows are removed |

## OCR and mail

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_OCR_LANGUAGES` | Worker | `deu+eng` | text | Tesseract languages, joined by `+`; the image has German and English |
| `LEKTO_OCR_TIMEOUT` | Worker | `600` | duration | Time per document for OCR (OCRmyPDF) |
| `LEKTO_MAIL_RENDER_TIMEOUT` | Worker | `120` | duration | Time per mail for setting it as a PDF (WeasyPrint, in a child process) |
| `LEKTO_MAIL_TIMEOUT` | both | `30` | duration | Time for connecting to a mail server (IMAP) and for each of its answers; the API tests connections, the worker fetches |

## Search

Meilisearch holds the index of words and vectors. Without `LEKTO_MEILISEARCH_URL` there is no
search; the API searches, the worker indexes.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_MEILISEARCH_URL` | both | – | URL | Meilisearch, e.g. `http://meilisearch:7700` |
| `LEKTO_MEILISEARCH_API_KEY` | both | – | text, *secret* | The master key or a key with access to the index |
| `LEKTO_MEILISEARCH_INDEX` | both | `lekto-documents` | text | The active index (letters, digits, `-`, `_`); a rebuild fills `<name>-rebuild` and swaps it in |
| `LEKTO_MEILISEARCH_TIMEOUT` | both | `30` | duration | Time per request |
| `LEKTO_MEILISEARCH_TASK_TIMEOUT` | Worker | `120` | duration | How long a write waits for its task |
| `LEKTO_SEARCH_LOCALES` | both | `deu+eng` | text | Languages of the documents, ISO 639-3 codes joined by `+` (for splitting words) |
| `LEKTO_SEARCH_SEMANTIC_RATIO` | API | `0.5` | 0–1 | Weight of the meaning against the words (0: words only, 1: meaning only) when a request does not say |
| `LEKTO_SEARCH_EMBED_TIMEOUT` | API | `5` | duration | How long a search waits for the embedding of its query, then it finds words only |
| `LEKTO_SEARCH_MEANING_MIN_SCORE` | API | – | 0–1 | A document found by the meaning alone, not by a word, is left out below this score. It depends on the model; `lekto evaluate-search` measures it |
| `LEKTO_SEARCH_MAX_TEXT` | Worker | `200000` | 1,000–10,000,000 | Characters of text per document in the index |
| `LEKTO_SEARCH_CHUNK_SIZE` | Worker | `1500` | 100–100,000 | Characters per section with a vector |
| `LEKTO_SEARCH_MAX_CHUNKS` | Worker | `8` | 1–100 | Sections with a vector per document |
| `LEKTO_SEARCH_RECONCILE_INTERVAL` | Worker | `21600` | duration | Time between comparisons of index and database |
| `LEKTO_SEARCH_REBUILD_TIMEOUT` | Worker | `21600` | duration | Time a rebuild of the index may take |

## Language model

An OpenAI-compatible endpoint (Ollama, LiteLLM, a cloud provider) that proposes contact, type,
tags, date, title and fields. Set base URL and model together or neither; without them documents
wait yellow for a person.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_LLM_BASE_URL` | Worker | – | URL | With the version path: `http://ollama:11434/v1` |
| `LEKTO_LLM_MODEL` | Worker | – | text | The model's name at the endpoint |
| `LEKTO_LLM_API_KEY` | Worker | – | text, *secret* | Sent as bearer token, if set |
| `LEKTO_LLM_TEMPERATURE` | Worker | `0` | 0–2 or `none` | 0 for repeatable answers; `none` sends none (for models that reject one, such as Claude Sonnet 5.5) |
| `LEKTO_LLM_SEED` | Worker | – | integer | Passed to the endpoint, if set |
| `LEKTO_LLM_TIMEOUT` | Worker | `300` | duration | Time per request (`600` on a CPU) |
| `LEKTO_LLM_RESPONSE_FORMAT` | Worker | `json_schema` | `json_schema`, `json_object` | `json_object` for providers without JSON Schema support; the schema then goes as a message after the task. The answer is checked either way |
| `LEKTO_LLM_INPUT_BUDGET` | Worker | `12000` | 1,000–1,000,000 | Characters of document text per request (a run of spaces counts once); longer documents are shortened |
| `LEKTO_LLM_MAX_TAGS` | Worker | `200` | 1–10,000 | Tags listed per request; with more, those named in the text come first |

## Embeddings

An OpenAI-compatible endpoint that turns sections of documents and search queries into vectors,
for search by meaning and for similar documents. Set base URL and model together or neither.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_EMBEDDING_BASE_URL` | both | – | URL | The worker embeds sections, the API embeds queries |
| `LEKTO_EMBEDDING_MODEL` | both | – | text | The model's name at the endpoint |
| `LEKTO_EMBEDDING_API_KEY` | both | – | text, *secret* | Sent as bearer token, if set |
| `LEKTO_EMBEDDING_TIMEOUT` | both | `60` | duration | Time per request |
| `LEKTO_EMBEDDING_DIMENSIONS` | both | – | 1–65,535 | Length of the vectors (Qwen3-Embedding 4B: 2560; `snowflake-arctic-embed2`, `bge-m3`: 1024); required with Meilisearch and an embedding endpoint. Another model needs a rebuild of the index |
| `LEKTO_EMBEDDING_QUERY_PREFIX` | API | – | text | Put before queries, for models that ask for it (`query:`; Qwen3-Embedding an instruction and `Query:`); `\n` stands for a line break |
| `LEKTO_EMBEDDING_DOCUMENT_PREFIX` | Worker | – | text | Put before document sections, for models that ask for it; `\n` stands for a line break |

## Vision model

An OpenAI-compatible endpoint whose model takes images and reads a document's pages when a person
asks for it (`POST /documents/{id}/vision`); the page images go there. Set base URL and model
together or neither; off without them.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_VLM_BASE_URL` | both | – | URL | The API names model and endpoint in `GET /pipeline` |
| `LEKTO_VLM_MODEL` | both | – | text | A model that gives each line's box in pixels (measured with Claude Sonnet 5.5) |
| `LEKTO_VLM_API_KEY` | Worker | – | text, *secret* | Sent as bearer token, if set |
| `LEKTO_VLM_TIMEOUT` | Worker | `1800` | duration | Time for reading a whole document (one page at most 300 s); that job's lease grows with it |

## Classification

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_CONFIDENCE_THRESHOLD` | Worker | `0.9` | more than 0, at most 1 | A value passes (green) from this confidence on |
| `LEKTO_CONTACT_SUGGEST_THRESHOLD` | Worker | `0.75` | more than 0, at most 1 | An existing contact is suggested from this similarity on; not above `LEKTO_CONFIDENCE_THRESHOLD` |
| `LEKTO_POOR_READING_THRESHOLD` | Worker | `0.08` | more than 0, at most 1 | Share of unsure words around a value from which its place counts as poorly read, and the value is only suggested. The default lies between good scans (up to 7 %) and broken ones (from 9 %) |
| `LEKTO_DEFAULT_CURRENCY` | both | `EUR` | text | ISO 4217 code: the currency of an amount in a document that shows none, and of the `currency` filter in templates |
| `LEKTO_CLASSIFIER` | both | `scikit-learn` | `scikit-learn`, `none` | The classifier trained from confirmed documents; `none` turns it off |
| `LEKTO_CLASSIFIER_MIN_EXAMPLES` | both | `20` | 2–1,000,000 | Confirmed documents before the first model is trained |
| `LEKTO_CLASSIFIER_RETRAIN_AFTER` | both | `25` | 1–1,000,000 | Documents confirmed since the last model before it is trained again |
| `LEKTO_CLASSIFIER_THRESHOLD` | Worker | `0.8` | more than 0, at most 1 | A prediction this sure names its contact, type or tag |
| `LEKTO_NEIGHBOURS` | Worker | `5` | 0–20 | Similar confirmed documents that vote on a new one (needs the search index with embeddings); `0` turns them off |

## Notifications

Web push: notifications on the devices of people who switched them on (the installed app on
iPhone and iPad, browsers elsewhere). Lekto encrypts each message for the device and sends it to
the device's push service (Apple, Google, Mozilla, Microsoft): an outgoing connection, as for
logos. Set both variables or neither; without them Lekto sends no notification.

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_PUSH_VAPID_PRIVATE_KEY` | both | – | text, *secret* | Lekto's key for the push services, 32 bytes base64url: `lekto vapid-key` prints a new one. Keep it: with another key, every device has to switch notifications on again |
| `LEKTO_PUSH_SUBJECT` | both | – | text | How a push service reaches the operator: `mailto:admin@example.org` or an `https://` address |

## Logos

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_LOGO_FETCH` | both | `false` | `true`, `false` | Fetch the logos of contacts from their own websites (the worker fetches, the API offers the button): HTTPS to public addresses only. Off, Lekto never asks the web on its own; uploads work either way |

## Rules and templates

| Variable | Role | Default | Values | Meaning |
| --- | --- | --- | --- | --- |
| `LEKTO_RULES_PATTERN_TIMEOUT` | both | `0.2` | duration | Time a regular expression of a rule may run per text or value (worker: rules; API: previews) |
| `LEKTO_RULES_MAX_TEXT` | both | `200000` | 1,000–10,000,000 | Characters of document text that rules look at |
| `LEKTO_RULES_APPLY_MAX_DOCUMENTS` | both | `1000` | 1–100,000 | Documents per retroactive application of a rule |
| `LEKTO_TEMPLATE_LOCALE` | both | `de` | text | Locale in which templates write dates and amounts (Babel's names: `de`, `en_US`); the head of a mail set as a PDF speaks its language too (German, else English). See [templates.md](templates.md) |

## The image

Variables of the image `ghcr.io/tb1337/lekto` that are not settings of Lekto itself.

| Variable | Default | Meaning |
| --- | --- | --- |
| `PUID`, `PGID` | `1000` | User and group of the Lekto processes; `0` is refused. The volume and the secret files must be readable by them, the volume writable |
| `LEKTO_VERSION` | the release's | Set by the release build from its tag; Lekto reports it. Not to be set |
| `S6_SERVICES_GRACETIME` | `40000` | Milliseconds s6 waits for the services on `docker stop`; at least `LEKTO_WORKER_SHUTDOWN_TIMEOUT` plus 10 s ([deploy/README.md](../deploy/README.md#stopping)) |
| `S6_KILL_GRACETIME`, `S6_BEHAVIOUR_IF_STAGE2_FAILS` | `1000`, `2` | Further settings of s6-overlay; keep them |

## The migration client

`lekto-migration` (image `ghcr.io/tb1337/lekto-migration`) reads its own variables, all with the
prefix `LEKTO_MIGRATION_`; Lekto ignores them. See [migration/README.md](../migration/README.md).

| Variable | Default | Meaning |
| --- | --- | --- |
| `LEKTO_MIGRATION_PAPERLESS_URL` | – | The source system's address; required (or `--paperless-url`) |
| `LEKTO_MIGRATION_PAPERLESS_TOKEN` | – | *secret*; its API token, required |
| `LEKTO_MIGRATION_LEKTO_URL` | – | Lekto's address (or `--lekto-url`) |
| `LEKTO_MIGRATION_LEKTO_TOKEN` | – | *secret*; an admin's API token with scope `read_write` |
