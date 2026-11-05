"""A mail server Lekto fetches from (IMAP).

First adapter: `imaplib` of the standard library, in a thread. `folders` signs in for itself;
a fetch opens a `session` and does its work in it, then leaves (no IDLE: Lekto fetches every
few minutes). Mails are read with `BODY.PEEK`: reading marks nothing; only an action does.
What goes wrong comes back as a `MailServerError` with a reason an admin can act on: the
server cannot be reached, no secure connection, user name or password refused, a folder
missing, or the server's own error.
"""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from lekto.core.domain.errors import DomainError
from lekto.core.domain.mail import MailLogin
from lekto.core.domain.reasons import Reason


class MailServerError(DomainError):
    """The mail server could not do what was asked; `reason` says why (`MAIL_...`)."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)


@dataclass(frozen=True)
class MailSearch:
    """Which mails of a folder: arrived on `since` or later (by the server's date of arrival,
    to the day), unread ones only (`unseen`), or all."""

    since: date | None = None
    unseen: bool = False


@dataclass(frozen=True)
class FolderMails:
    """The UIDs a search found, ascending, and the folder's UIDVALIDITY: UIDs count only
    together with it. `keywords`: those the folder knows (its FLAGS and PERMANENTFLAGS, as
    `mail_traits.shown_keywords` offers them); `own_keywords`: whether the server stores
    keywords of Lekto's own there (PERMANENTFLAGS hold `\\*`)."""

    uidvalidity: int
    uids: tuple[int, ...]
    keywords: tuple[str, ...] = ()
    own_keywords: bool = False


@dataclass(frozen=True)
class MailInfo:
    uid: int
    size: int  # bytes
    arrived_at: datetime  # the server's date of arrival (INTERNALDATE), UTC
    flags: frozenset[str] = frozenset()  # its IMAP flags and keywords, as the server has them


@dataclass(frozen=True)
class MailAccount:
    """What a test of a connection finds: the folders (`MailServer.account`), the keywords the
    inbox knows and whether the server stores keywords of its own."""

    folders: tuple[str, ...]
    keywords: tuple[str, ...] = ()
    own_keywords: bool = False


class MailSession(Protocol):
    async def search(self, folder: str, search: MailSearch) -> FolderMails:
        """MailServerError (`MAIL_FOLDER_MISSING`) if there is no such folder."""
        ...

    async def info(self, folder: str, uids: Sequence[int]) -> list[MailInfo]:
        """Size, date of arrival and flags of the mails `uids` still there, in the order of
        `uids`."""
        ...

    async def fetch(self, folder: str, uid: int) -> bytes | None:
        """The whole mail, unmarked; None if it is gone."""
        ...

    async def head(self, folder: str, uid: int) -> bytes | None:
        """The mail's header lines only, unmarked; None if it is gone."""
        ...

    async def mark(
        self, folder: str, uid: int, *, add: Sequence[str] = (), remove: Sequence[str] = ()
    ) -> None:
        """Add and remove IMAP flags and keywords (`\\Seen`, `\\Flagged`, `Lekto`).
        MailServerError where the server refuses, such as a keyword of its own where it stores
        none."""
        ...

    async def move(self, folder: str, uid: int, target: str) -> None:
        """MailServerError (`MAIL_FOLDER_MISSING`) if there is no folder `target`."""
        ...

    async def trash(self, folder: str, uid: int) -> None:
        """Into the account's trash folder; deleted where it has none."""
        ...


class MailServer(Protocol):
    async def account(self, login: MailLogin) -> MailAccount:
        """The folders of the account, by their full names as the server separates them
        (`INBOX`, `INBOX/Rechnungen`, ...), sorted, `INBOX` first, and the keywords of its inbox.
        Raises MailServerError."""
        ...

    def session(self, login: MailLogin) -> AbstractAsyncContextManager[MailSession]:
        """Signed in for the time of the `async with`. Raises MailServerError on entering
        and from its calls."""
        ...
