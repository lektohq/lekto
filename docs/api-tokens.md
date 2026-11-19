# API tokens

An API token lets a script, a tool or a service such as Home Assistant use Lekto's REST API and
its MCP server without signing in. It belongs to one user and carries **rights**: what it may do,
area by area. It never may more than its user.

Create and revoke tokens in **Settings › API-Tokens**. A token is shown only once, when it is
created. Every request sends it as `Authorization: Bearer lekto_…`.

## Presets

| Preset | Rights |
| --- | --- |
| **Lesen** (`read`) | reading in every area, and the numbers; for an admin also every admin right |
| **Lesen und Schreiben** (`read_write`) | reading and changing in every area, uploading; for an admin also every admin right |
| **Nur hochladen** (`upload`) | only `POST /api/v1/documents`; it reads nothing, not even who it is ([shortcut](shortcut.md)) |

Choose **Eigene Rechte** to pick the rights one by one.

## Rights of the areas

Each area has a right to read and one to change (`…:read`, `…:write`).

| Area | What it covers |
| --- | --- |
| `documents` | documents with their files, text, facts and relations; the inbox, search, expected documents, events (`GET /events`). Besides `documents:read` and `documents:write`: `documents:count`, the numbers alone (`GET /inbox/summary`, `GET /documents/count`), which reading includes; `documents:upload`, uploading |
| `master_data` | contacts, document types, tags, fields, identifiers |
| `rules` | rules, their applications, the preview of templates |
| `spaces` | spaces and their members, the list of users to share with |
| `webhooks` | your own webhooks and their deliveries |
| `lenses` | your saved views |
| `push` | the devices and settings of notifications |
| `system` | jobs, the search index, the classifier, processing; runs of them; mailboxes and mail rules; users (most of it for admins only) |

Each operation of the REST API names the right it needs as `x-right` in the OpenAPI document
(`/api/v1/openapi.json`): a right, `any` (every token, such as `GET /auth/me`) or `session`
(signing in, the own profile, passwords, two-factor, tokens: never a token). A token without
the right gets `403` with the reason `token_lacks_right` and the right it lacks; a token of a
preset gets the reasons it always got (`read_only_token`, `upload_only_token`). The MCP server
shows a token the tools its rights open.

## Admin rights

What an admin may beyond a user is split into rights of its own, for an admin's token only. They
count only while the user is an active admin. An admin's token without them acts as a user with
the same spaces.

| Right | What it allows |
| --- | --- |
| `admin:count_all` | the numbers of every user's documents: `all_users` at `GET /inbox/summary`, `GET /documents/count`, the facets and the counts of master data |
| `admin:documents_all` | reaching every space: reading every document (changing it, with `documents:write`), `all_users` at lists and search, events of every document |
| `admin:mailboxes` | listing the mailboxes and fetching one now (`GET /mailboxes`, `POST /mailboxes/{id}/fetch`, with `system:read` and `system:write`) |
| `admin:private_webhooks` | saving a webhook at an address that is not public (`LEKTO_WEBHOOK_PRIVATE_TARGETS`) |
| `admin:manage` | everything else of an admin: users, master data, global rules, mailboxes and mail rules, runs, the facts and profiles of persons |

A token for Home Assistant that counts the whole household, reads its user's documents, uploads,
fetches the mailboxes and keeps its own webhook at Home Assistant's address takes:
`documents:read`, `documents:upload`, `webhooks:read`, `webhooks:write`, `system:read`,
`system:write`, `admin:count_all`, `admin:mailboxes`, `admin:private_webhooks`.

## Revoking

Revoking a token in **Settings › API-Tokens** ends it at once, and deletes the webhooks created
through it. Changing the password may revoke every token as well. A deactivated user's tokens
are refused.

## Over the API

`POST /api/v1/auth/tokens` (with a session) takes a `name`, either a `scope` (a preset) or
`rights` (a list), and optionally `expires_at`. The answer holds the token once, with its
`rights` and the preset they match (`scope`, `null` for rights chosen one by one).
`GET /api/v1/auth/me` with a token tells its `rights`.
