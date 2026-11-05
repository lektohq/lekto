"""A mail server in memory: accounts with their folders and mails, for tests and the memory
container."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.mail_traits import SEEN, shown_keywords
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.mail_server import (
    TRASH_NAMES,
    FolderMails,
    MailAccount,
    MailInfo,
    MailSearch,
    MailServerError,
)


@dataclass
class MemoryMail:
    uid: int
    data: bytes
    arrived_at: datetime
    seen: bool = False
    flags: set[str] = field(default_factory=set)  # keywords and flags besides \Seen

    @property
    def all_flags(self) -> frozenset[str]:
        return frozenset(self.flags | ({SEEN} if self.seen else set()))


@dataclass
class MemoryFolder:
    uidvalidity: int
    mails: list[MemoryMail] = field(default_factory=list)
    next_uid: int = 1


@dataclass
class MemoryMailAccount:
    password: str
    security: MailSecurity
    boxes: dict[str, MemoryFolder] = field(default_factory=lambda: {"INBOX": MemoryFolder(1)})
    own_keywords: bool = True  # whether it stores keywords of Lekto's own
    known: set[str] = field(default_factory=set)  # every keyword its mails had, as FLAGS keeps

    def add_folders(self, *names: str) -> None:
        for name in names:
            self.boxes.setdefault(name, MemoryFolder(len(self.boxes) + 1))

    def deliver(
        self,
        folder: str,
        data: bytes,
        *,
        arrived_at: datetime,
        seen: bool = False,
        flags: set[str] | frozenset[str] = frozenset(),
    ) -> int:
        """Put a mail into `folder` (made if missing), with its keywords and flags; returns its
        UID."""
        box = self.boxes.setdefault(folder, MemoryFolder(len(self.boxes) + 1))
        uid = box.next_uid
        box.next_uid += 1
        box.mails.append(MemoryMail(uid, data, arrived_at.astimezone(UTC), seen, set(flags)))
        self.known.update(flags)
        return uid

    def keywords(self, folder: str) -> tuple[str, ...]:
        """The keywords the account's mails had, as a server's FLAGS would list them."""
        return shown_keywords(self.known) if folder in self.boxes else ()


class MemoryMailServer:
    """Servers by host and port; each holds accounts by user name. A host it does not know cannot
    be reached; a login whose security is not the server's gets no secure connection."""

    def __init__(self) -> None:
        self.servers: dict[tuple[str, int], dict[str, MemoryMailAccount]] = {}
        self.securities: dict[tuple[str, int], MailSecurity] = {}

    def add_account(self, login: MailLogin) -> MemoryMailAccount:
        """An account as `login` names it, on a server with the login's security."""
        where = (login.host, login.port)
        self.securities.setdefault(where, login.security)
        account = MemoryMailAccount(password=login.password, security=login.security)
        self.servers.setdefault(where, {})[login.username] = account
        return account

    async def account(self, login: MailLogin) -> MailAccount:
        account = self._account(login)
        return MailAccount(
            folders=tuple(
                sorted(account.boxes, key=lambda name: (name != "INBOX", name.casefold()))
            ),
            keywords=account.keywords("INBOX"),
            own_keywords=account.own_keywords,
        )

    @asynccontextmanager
    async def session(self, login: MailLogin) -> AsyncIterator["MemoryMailSession"]:
        yield MemoryMailSession(self._account(login))

    def _account(self, login: MailLogin) -> MemoryMailAccount:
        where = (login.host, login.port)
        if where not in self.servers:
            raise MailServerError(because(ReasonCode.MAIL_UNREACHABLE, host=login.host))
        if self.securities[where] != login.security:
            raise MailServerError(because(ReasonCode.MAIL_TLS_FAILED, host=login.host))
        account = self.servers[where].get(login.username)
        if account is None or account.password != login.password:
            raise MailServerError(because(ReasonCode.MAIL_LOGIN_FAILED))
        return account


class MemoryMailSession:
    def __init__(self, account: MemoryMailAccount) -> None:
        self._account = account

    async def search(self, folder: str, search: MailSearch) -> FolderMails:
        box = self._box(folder)
        uids = tuple(
            mail.uid
            for mail in box.mails
            if (search.since is None or mail.arrived_at.date() >= search.since)
            and not (search.unseen and mail.seen)
        )
        return FolderMails(
            uidvalidity=box.uidvalidity,
            uids=uids,
            keywords=self._account.keywords(folder),
            own_keywords=self._account.own_keywords,
        )

    async def info(self, folder: str, uids: Sequence[int]) -> list[MailInfo]:
        mails = {mail.uid: mail for mail in self._box(folder).mails}
        return [
            MailInfo(
                uid=uid,
                size=len(mails[uid].data),
                arrived_at=mails[uid].arrived_at,
                flags=mails[uid].all_flags,
            )
            for uid in uids
            if uid in mails
        ]

    async def fetch(self, folder: str, uid: int) -> bytes | None:
        mail = self._mail(folder, uid)
        return None if mail is None else mail.data

    async def head(self, folder: str, uid: int) -> bytes | None:
        mail = self._mail(folder, uid)
        if mail is None:
            return None
        end = mail.data.replace(b"\r\n", b"\n").find(b"\n\n")
        return mail.data if end < 0 else mail.data.replace(b"\r\n", b"\n")[: end + 1]

    async def mark(
        self, folder: str, uid: int, *, add: Sequence[str] = (), remove: Sequence[str] = ()
    ) -> None:
        mail = self._mail(folder, uid)
        if mail is None:
            return
        own = [name for name in add if not name.startswith("\\")]
        if own and not self._account.own_keywords:
            raise MailServerError(
                because(ReasonCode.MAIL_SERVER_ERROR, detail="keywords are not stored")
            )
        for name in add:
            if name.casefold() == SEEN.casefold():
                mail.seen = True
            else:
                mail.flags.add(name)
                self._account.known.add(name)
        for name in remove:
            if name.casefold() == SEEN.casefold():
                mail.seen = False
            else:
                mail.flags = {flag for flag in mail.flags if flag.casefold() != name.casefold()}

    async def move(self, folder: str, uid: int, target: str) -> None:
        self._box(target)
        mail = self._mail(folder, uid)
        if mail is not None:
            self._box(folder).mails.remove(mail)
            self._account.deliver(
                target, mail.data, arrived_at=mail.arrived_at, seen=mail.seen, flags=mail.flags
            )

    async def trash(self, folder: str, uid: int) -> None:
        """Into the folder named as a trash (`TRASH_NAMES`); deleted where there is none, as
        the port says."""
        trash = next((name for name in TRASH_NAMES if name in self._account.boxes), None)
        if trash is not None and trash != folder:
            await self.move(folder, uid, trash)
            return
        mail = self._mail(folder, uid)
        if mail is not None:
            self._box(folder).mails.remove(mail)

    def _box(self, folder: str) -> "MemoryFolder":
        box = self._account.boxes.get(folder)
        if box is None:
            raise MailServerError(because(ReasonCode.MAIL_FOLDER_MISSING, folder=folder))
        return box

    def _mail(self, folder: str, uid: int) -> MemoryMail | None:
        return next((mail for mail in self._box(folder).mails if mail.uid == uid), None)
