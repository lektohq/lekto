"""What a caller may do: the rights an API token carries, and who acts with which rights (Tobi,
19.11.2026, `.knowledge/plans/token-rights.md`).

A right of an area (`documents:read`, `rules:write`, …) opens the operations of that area; the
inbound adapters check it per operation. An admin right (`admin:…`) opens part of what an admin
may beyond a user; the core checks it, and it counts only while the user is an active admin. A
session has every right of its user, and so do the worker, the evaluation and the command line.
"""

from dataclasses import dataclass
from enum import StrEnum

from lekto.core.domain.ids import UserId


class TokenRight(StrEnum):
    DOCUMENTS_COUNT = "documents:count"  # numbers of the own reach only: inbox summary, count
    DOCUMENTS_READ = "documents:read"  # documents, inbox, search, events; includes the numbers
    DOCUMENTS_WRITE = "documents:write"
    DOCUMENTS_UPLOAD = "documents:upload"
    MASTER_DATA_READ = "master_data:read"
    MASTER_DATA_WRITE = "master_data:write"
    RULES_READ = "rules:read"
    RULES_WRITE = "rules:write"
    SPACES_READ = "spaces:read"
    SPACES_WRITE = "spaces:write"
    WEBHOOKS_READ = "webhooks:read"
    WEBHOOKS_WRITE = "webhooks:write"
    LENSES_READ = "lenses:read"
    LENSES_WRITE = "lenses:write"
    PUSH_READ = "push:read"
    PUSH_WRITE = "push:write"
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    # What an admin may beyond a user, each on its own; only for an active admin.
    ADMIN_COUNT_ALL = "admin:count_all"  # count every user's documents (`all_users` of numbers)
    ADMIN_DOCUMENTS_ALL = "admin:documents_all"  # reach every space: read, and change with write
    ADMIN_MAILBOXES = "admin:mailboxes"  # list the mailboxes and fetch one now
    ADMIN_PRIVATE_WEBHOOKS = "admin:private_webhooks"  # a webhook to an address that is not public
    ADMIN_MANAGE = "admin:manage"  # users, master data, global rules, mailboxes, runs of the system

    @property
    def for_admins(self) -> bool:
        return self in ADMIN_RIGHTS


ADMIN_RIGHTS = frozenset(
    {
        TokenRight.ADMIN_COUNT_ALL,
        TokenRight.ADMIN_DOCUMENTS_ALL,
        TokenRight.ADMIN_MAILBOXES,
        TokenRight.ADMIN_PRIVATE_WEBHOOKS,
        TokenRight.ADMIN_MANAGE,
    }
)
AREA_RIGHTS = frozenset(TokenRight) - ADMIN_RIGHTS
READ_RIGHTS = frozenset(
    right
    for right in AREA_RIGHTS
    if right.value.endswith(":read") or right is TokenRight.DOCUMENTS_COUNT
)

_IMPLIED = {TokenRight.DOCUMENTS_COUNT: TokenRight.DOCUMENTS_READ}
"""A right that another one includes: who may read the documents may count them."""


def holds(rights: frozenset[TokenRight] | None, right: TokenRight) -> bool:
    """Whether `rights` (None: every right) include `right`, also through a right that includes
    it."""
    if rights is None or right in rights:
        return True
    implied_by = _IMPLIED.get(right)
    return implied_by is not None and implied_by in rights


@dataclass(frozen=True)
class Actor:
    """Who calls a service, and with which rights: those of the API token they act through;
    None for every right of their user (a session, the worker)."""

    id: UserId
    rights: frozenset[TokenRight] | None = None

    def may(self, right: TokenRight) -> bool:
        """Whether the caller's rights include `right`; an admin right counts only for an active
        admin, which the core checks with the user (`User.may`)."""
        return holds(self.rights, right)
