"""The foreign keys of the SQL schema as the in-memory rows hold them (PM-03): which rows of
which table a row refers to, and what removing one of those does. The unit of work refuses to
remove a row a `RESTRICT` reference still points to, removes what a `CASCADE` one points from at
the commit, and refuses a commit that leaves a reference pointing to no row; a `SET_NULL` one
the repository's `remove` empties (`MemoryUserRepository.remove`).

What a row embeds refers as the row (a space's members, a contact's identifiers, a document's
tags and fields). The stores outside the tables check theirs where they are written (the inbox's
marks, the processing facts) or at the commit (the processing log)."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from lekto.adapters.outbound.memory.database import (
    API_TOKENS,
    BULK_OPERATIONS,
    CONTACTS,
    CREDENTIALS,
    DOCUMENT_FACTS,
    DOCUMENT_RELATIONS,
    DOCUMENT_TYPES,
    DOCUMENT_VERSIONS,
    DOCUMENTS,
    EXTERNAL_IDENTITIES,
    FIELDS,
    KNOWN_DEVICES,
    LENSES,
    MAIL_ORIGINS,
    MAIL_RECORDS,
    MAIL_RULES,
    MAILBOXES,
    PROFILES,
    PUSH_DEVICES,
    PUSH_PREFERENCES,
    RULE_APPLICATIONS,
    RULE_VERSIONS,
    RULES,
    SESSIONS,
    SPACES,
    TAGS,
    USERS,
    WEBHOOK_DELIVERIES,
    WEBHOOKS,
    Table,
)


class OnDelete(Enum):
    """What removing the row a reference points to does (the foreign key's ON DELETE)."""

    RESTRICT = "restrict"  # refused while the reference points to it
    CASCADE = "cascade"  # the referring row goes with it
    SET_NULL = "set null"  # the reference is emptied


@dataclass(frozen=True)
class Reference:
    """Rows of `table` refer to rows of `target` by the ids `ids` gives (None: none)."""

    table: Table[Any]
    target: Table[Any]
    ids: Callable[[Any], Iterable[UUID | None]]
    on_delete: OnDelete = OnDelete.RESTRICT


def _one(read: Callable[[Any], UUID | None]) -> Callable[[Any], Iterable[UUID | None]]:
    return lambda row: (read(row),)


_RESTRICT, _CASCADE, _SET_NULL = OnDelete.RESTRICT, OnDelete.CASCADE, OnDelete.SET_NULL

REFERENCES: tuple[Reference, ...] = (
    # The users'.
    Reference(PROFILES, USERS, _one(lambda profile: profile.id), _CASCADE),
    Reference(SPACES, USERS, _one(lambda space: space.personal_of)),
    Reference(SPACES, USERS, lambda space: space.members),
    Reference(CREDENTIALS, USERS, _one(lambda credential: credential.user_id), _CASCADE),
    Reference(SESSIONS, USERS, _one(lambda session: session.user_id), _CASCADE),
    Reference(API_TOKENS, USERS, _one(lambda token: token.user_id), _CASCADE),
    Reference(KNOWN_DEVICES, USERS, _one(lambda device: device.user_id), _CASCADE),
    Reference(PUSH_DEVICES, USERS, _one(lambda device: device.user_id), _CASCADE),
    Reference(PUSH_PREFERENCES, USERS, _one(lambda preferences: preferences.id), _CASCADE),
    Reference(EXTERNAL_IDENTITIES, USERS, _one(lambda identity: identity.user_id), _CASCADE),
    Reference(WEBHOOKS, USERS, _one(lambda webhook: webhook.owner_id), _CASCADE),
    Reference(LENSES, USERS, _one(lambda lens: lens.owner_id), _CASCADE),
    Reference(BULK_OPERATIONS, USERS, _one(lambda operation: operation.user_id), _CASCADE),
    Reference(RULE_APPLICATIONS, USERS, _one(lambda application: application.user_id), _CASCADE),
    Reference(MAILBOXES, USERS, _one(lambda mailbox: mailbox.fallback_user_id)),
    Reference(
        CONTACTS,
        USERS,
        lambda contact: (item.user_id for item in contact.identifiers),
        _SET_NULL,  # the identifier goes, the contact stays (`MemoryUserRepository.remove`)
    ),
    Reference(DOCUMENTS, USERS, _one(lambda document: document.uploaded_by), _SET_NULL),
    Reference(DOCUMENT_RELATIONS, USERS, _one(lambda row: row.relation.decided_by), _SET_NULL),
    Reference(DOCUMENT_VERSIONS, USERS, _one(lambda row: row.version.created_by), _SET_NULL),
    # The master data's.
    Reference(TAGS, TAGS, _one(lambda tag: tag.parent_id)),
    Reference(CONTACTS, TAGS, lambda contact: contact.group_ids),
    Reference(CONTACTS, TAGS, lambda contact: contact.topic_ids),
    Reference(CONTACTS, TAGS, lambda contact: (item.topic_id for item in contact.identifiers)),
    Reference(DOCUMENT_TYPES, TAGS, lambda kind: kind.group_ids),
    Reference(FIELDS, DOCUMENT_TYPES, lambda field: field.document_type_ids or ()),
    Reference(MAILBOXES, DOCUMENT_TYPES, _one(lambda mailbox: mailbox.body_type_id)),
    # `title_pattern_rules` keeps a type's rule; its cascade empties the rule's `managed_by`.
    Reference(RULES, DOCUMENT_TYPES, _one(lambda rule: rule.managed_by), _SET_NULL),
    # The documents'.
    Reference(DOCUMENTS, SPACES, _one(lambda document: document.space_id)),
    Reference(DOCUMENTS, CONTACTS, _one(lambda document: document.contact_id)),
    Reference(DOCUMENTS, DOCUMENT_TYPES, _one(lambda document: document.document_type_id)),
    Reference(DOCUMENTS, TAGS, _one(lambda document: document.topic_id)),
    Reference(DOCUMENTS, TAGS, lambda document: document.tag_ids),
    Reference(DOCUMENTS, FIELDS, lambda document: document.fields),
    Reference(DOCUMENT_FACTS, DOCUMENTS, _one(lambda row: row.id), _CASCADE),
    Reference(DOCUMENT_RELATIONS, DOCUMENTS, _one(lambda row: row.relation.newer), _CASCADE),
    Reference(DOCUMENT_RELATIONS, DOCUMENTS, _one(lambda row: row.relation.older), _CASCADE),
    Reference(DOCUMENT_VERSIONS, DOCUMENTS, _one(lambda row: row.version.document_id), _CASCADE),
    Reference(MAIL_ORIGINS, DOCUMENTS, _one(lambda origin: origin.document_id), _CASCADE),
    # The rules', mailboxes' and webhooks'.
    Reference(RULES, SPACES, _one(lambda rule: rule.space_id), _CASCADE),
    Reference(RULE_VERSIONS, RULES, _one(lambda row: row.item.rule_id), _CASCADE),
    Reference(RULE_APPLICATIONS, RULES, _one(lambda application: application.rule_id), _CASCADE),
    Reference(MAIL_RECORDS, MAILBOXES, _one(lambda record: record.mailbox_id), _CASCADE),
    Reference(MAIL_RULES, MAILBOXES, _one(lambda rule: rule.mailbox_id), _CASCADE),
    Reference(WEBHOOK_DELIVERIES, WEBHOOKS, _one(lambda row: row.item.webhook_id), _CASCADE),
)
"""Every foreign key of the SQL schema between rows the memory keeps as tables (`tables.py`)."""
