<picture>
  <source media="(prefers-color-scheme: dark)" srcset=".github/release/banner-dark.svg">
  <img alt="Lekto" src=".github/release/banner-light.svg" width="100%">
</picture>

[![version](https://img.shields.io/github/v/release/tb1337/lekto-dms?label=version&color=0d6b6b)](https://github.com/tb1337/lekto-dms/releases)
[![ghcr.io](https://img.shields.io/badge/ghcr.io-tb1337%2Flekto-0d6b6b)](https://github.com/tb1337/lekto-dms/pkgs/container/lekto)
[![license](https://img.shields.io/badge/license-GPL--3.0-0d6b6b)](LICENSE)
[![python](https://img.shields.io/badge/python-3.13-0d6b6b)](backend/README.md)

# Lekto DMS

> [!WARNING]
> Lekto is in beta. Breaking changes can come with any release: in the REST API, the
> configuration, the database and the stored data. Read the release notes before you update, and
> keep a backup ([deploy/README.md](deploy/README.md)). Use it in non-production environments
> only, not yet for documents you cannot afford to lose.

**Lekto DMS** is a self-hosted, headless document management system. It reads every document,
files it and finds it again, and it shows why it decided what it did. The name comes from
*lector*, the reader; the owl in the logo reads with one eye and searches with the magnifier in
the other.

## What it does

- **Explainable intake.** Upload, mail or API → OCR (OCRmyPDF, PDF/A) → a language model, a
  classifier, similar documents and the facts of the text propose → a judge decides → one of
  three lanes: green (done), yellow (confirm), red (intervene). A value counts only if it stands
  in the text; every step is logged and can be repeated. A vision model rereads poorly read
  pages on request.
- **Facts and identifiers.** IBANs, customer, contract and tax numbers tie a document to its
  contact; documents relate to each other, and recurring ones form series with the next one
  expected.
- **Mail.** IMAP mailboxes with rules per mailbox: attachments become documents, the mail's text
  a PDF of its own beside them. A saved `.eml` can be uploaded too.
- **Rules.** Global and per space, built in the UI from conditions and actions, versioned, with
  a dry run and retroactive application; titles from Liquid templates.
- **Search.** Words and meaning in one query (Meilisearch, hybrid), always within the caller's
  rights; saved views as lenses.
- **People and spaces.** Native logins with TOTP, OpenID Connect. Rights belong to spaces, never
  to single documents.
- **Integration.** Signed webhooks, server-sent events and an MCP server at `/api/v1/mcp` for
  Claude and other AI clients.

## Quick start

```sh
cd docker
cp .env.example .env               # fill in the secrets
docker compose up -d
```

Open <http://localhost:8000/> and sign in as `admin` with `LEKTO_ADMIN_PASSWORD`. Point
`LEKTO_LLM_BASE_URL` and `LEKTO_EMBEDDING_BASE_URL` at Ollama or another OpenAI-compatible
endpoint (or add `compose.ollama.yml`); without one, documents wait yellow for a person and the
search works with words only. More setups (Postgres, S3, more workers, Caddy, Traefik, nginx):
[docker/](docker/), operation and backup: [deploy/README.md](deploy/README.md).

Development in the devcontainer: [.devcontainer/README.md](.devcontainer/README.md) and
[CLAUDE.md](CLAUDE.md).

## How it is built

- **Headless.** The REST API (OpenAPI) is the only way in; the web UI (SvelteKit), the MCP server
  and the migration client are its clients.
- **Hexagonal.** A plain Python core with ports; FastAPI, SQLAlchemy and every service behind
  adapters with contract tests.
- **Asynchronous.** The API answers at once, a worker processes; events reach the UI, webhooks
  and the search index through a transactional outbox.
- **Storage.** SQLite or Postgres, file system or S3, Meilisearch. Originals never change and are
  addressed by their SHA-256.
- **Models.** Any OpenAI-compatible endpoint, local (Ollama) or in the cloud: a language model,
  embeddings and optionally a vision model.
- **Configuration.** Environment variables with the prefix `LEKTO_`, secrets also as files.

## Documentation

| Document | Content |
| --- | --- |
| [docs/configuration.md](docs/configuration.md) | Every `LEKTO_` variable: default, values, meaning |
| [docs/templates.md](docs/templates.md) | Templates for titles, rules and webhook bodies |
| [docs/shortcut.md](docs/shortcut.md) | The shortcut that sends shared files from iPhone, iPad and Mac |
| [backend/README.md](backend/README.md) | Architecture, the REST API, processing, rules, search, webhooks, mail, MCP |
| [deploy/README.md](deploy/README.md) | The image: roles, volumes, health, reverse proxy, backup, updating |
| [docker/](docker/) | Compose examples with the published images |
| [web/README.md](web/README.md) | The web UI; its design system in [web/DESIGN.md](web/DESIGN.md) |
| [examples/](examples/) | Synthetic example documents, an MCP evaluation, a model-call consumer |
| [.devcontainer/README.md](.devcontainer/README.md) | Development and a personal instance in the devcontainer |

## License

[GPL-3.0](LICENSE)
