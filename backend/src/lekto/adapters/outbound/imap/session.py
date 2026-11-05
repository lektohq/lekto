"""A signed-in IMAP connection for the time of a fetch: every call in a thread, one at a time."""

import asyncio
import imaplib
import re
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta, timezone

from lekto.adapters.outbound.imap.names import listed, quoted
from lekto.core.domain.mail_traits import shown_keywords
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.mail_server import FolderMails, MailInfo, MailSearch, MailServerError

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_UID = re.compile(rb"UID (\d+)")
_SIZE = re.compile(rb"RFC822\.SIZE (\d+)")
_DATE = re.compile(
    rb'INTERNALDATE "\s?(\d{1,2})-(\w{3})-(\d{4}) (\d{2}):(\d{2}):(\d{2}) ([+-]\d{4})"'
)
_FLAGS = re.compile(rb"FLAGS \(([^)]*)\)")
_LIST = re.compile(rb"\(([^)]*)\)")
_TRASH_NAMES = ("Trash", "Papierkorb", "Deleted Messages", "Deleted Items", "INBOX.Trash")


class ImapMailSession:
    def __init__(self, imap: imaplib.IMAP4, run: Callable[..., object]) -> None:
        self._imap = imap
        self._run = run
        self._selected: str | None = None
        self._keywords: dict[str, tuple[tuple[str, ...], bool]] = {}
        self._lock = asyncio.Lock()

    async def search(self, folder: str, search: MailSearch) -> FolderMails:
        return await self._call(self._search, folder, search)

    async def info(self, folder: str, uids: Sequence[int]) -> list[MailInfo]:
        return await self._call(self._info, folder, list(uids))

    async def fetch(self, folder: str, uid: int) -> bytes | None:
        return await self._call(self._fetch, folder, uid)

    async def head(self, folder: str, uid: int) -> bytes | None:
        return await self._call(self._fetch, folder, uid, "(BODY.PEEK[HEADER])")

    async def mark(
        self, folder: str, uid: int, *, add: Sequence[str] = (), remove: Sequence[str] = ()
    ) -> None:
        if add:
            await self._call(self._store, folder, uid, "+FLAGS", f"({' '.join(add)})")
        if remove:
            await self._call(self._store, folder, uid, "-FLAGS", f"({' '.join(remove)})")

    async def move(self, folder: str, uid: int, target: str) -> None:
        await self._call(self._move, folder, uid, target)

    async def trash(self, folder: str, uid: int) -> None:
        await self._call(self._trash, folder, uid)

    async def _call[T](self, work: Callable[..., T], *args: object) -> T:
        async with self._lock:
            return await asyncio.to_thread(self._run, work, *args)  # type: ignore[arg-type]

    # --- in the thread ----------------------------------------------------------------------

    def _select(self, folder: str) -> None:
        if self._selected == folder:
            return
        status, _ = self._imap.select(quoted(folder).decode())
        if status != "OK":
            raise MailServerError(because(ReasonCode.MAIL_FOLDER_MISSING, folder=folder))
        self._selected = folder
        self._keywords[folder] = folder_keywords(self._imap)

    def _uidvalidity(self) -> int:
        _, answer = self._imap.response("UIDVALIDITY")
        value = answer[-1] if answer else None
        return int(value) if isinstance(value, bytes | str) and str(int(value)) else 0

    def _search(self, folder: str, search: MailSearch) -> FolderMails:
        self._select(folder)
        uidvalidity = self._uidvalidity()
        criteria = []
        if search.since is not None:
            criteria.append(f"SINCE {_day(search.since)}")
        if search.unseen:
            criteria.append("UNSEEN")
        status, answer = self._imap.uid("SEARCH", *(criteria or ["ALL"]))
        if status != "OK":
            raise imaplib.IMAP4.error(answer)
        found = b" ".join(part for part in answer if isinstance(part, bytes)).split()
        keywords, own = self._keywords.get(folder, ((), False))
        return FolderMails(
            uidvalidity=uidvalidity,
            uids=tuple(sorted(int(uid) for uid in found)),
            keywords=keywords,
            own_keywords=own,
        )

    def _info(self, folder: str, uids: list[int]) -> list[MailInfo]:
        if not uids:
            return []
        self._select(folder)
        status, answer = self._imap.uid(
            "FETCH", ",".join(map(str, uids)), "(UID RFC822.SIZE INTERNALDATE FLAGS)"
        )
        if status != "OK":
            raise imaplib.IMAP4.error(answer)
        found: dict[int, MailInfo] = {}
        for part in answer:
            line = part[0] if isinstance(part, tuple) else part
            if not isinstance(line, bytes):
                continue
            uid, size, moment = _UID.search(line), _SIZE.search(line), _DATE.search(line)
            flags = _FLAGS.search(line)
            if uid and size and moment:
                found[int(uid[1])] = MailInfo(
                    uid=int(uid[1]),
                    size=int(size[1]),
                    arrived_at=_moment(moment),
                    flags=frozenset(_names(flags[1])) if flags else frozenset(),
                )
        return [found[uid] for uid in uids if uid in found]

    def _fetch(self, folder: str, uid: int, what: str = "(BODY.PEEK[])") -> bytes | None:
        self._select(folder)
        status, answer = self._imap.uid("FETCH", str(uid), what)
        if status != "OK":
            raise imaplib.IMAP4.error(answer)
        for part in answer:
            if isinstance(part, tuple) and len(part) == 2 and isinstance(part[1], bytes):
                return part[1]
        return None

    def _store(self, folder: str, uid: int, command: str, flags: str) -> None:
        self._select(folder)
        status, answer = self._imap.uid("STORE", str(uid), command, flags)
        if status != "OK":
            raise imaplib.IMAP4.error(answer)

    def _move(self, folder: str, uid: int, target: str) -> None:
        self._select(folder)
        if "MOVE" in self._imap.capabilities:
            status, _ = self._imap.uid("MOVE", str(uid), quoted(target).decode())
        else:
            status, _ = self._imap.uid("COPY", str(uid), quoted(target).decode())
            if status == "OK":
                self._delete(folder, uid)
        if status != "OK":
            raise MailServerError(because(ReasonCode.MAIL_FOLDER_MISSING, folder=target))

    def _trash(self, folder: str, uid: int) -> None:
        trash = self._trash_folder()
        if trash is not None and trash != folder:
            self._move(folder, uid, trash)
            return
        self._delete(folder, uid)

    def _delete(self, folder: str, uid: int) -> None:
        """Mark the mail deleted and expunge it alone (`UID EXPUNGE`, RFC 4315). A server
        without UIDPLUS keeps it marked until a client expunges the folder: EXPUNGE would take
        every mail anyone marked (Tobi, 05.11.2026)."""
        self._store(folder, uid, "+FLAGS", "(\\Deleted)")
        if "UIDPLUS" in self._imap.capabilities:
            status, answer = self._imap.uid("EXPUNGE", str(uid))
            if status != "OK":
                raise imaplib.IMAP4.error(answer)

    def _trash_folder(self) -> str | None:
        status, entries = self._imap.list()
        if status != "OK":
            return None
        folders = listed(list(entries))
        for name, flags in folders:
            if "\\trash" in flags:
                return name
        names = {name for name, _ in folders}
        return next((name for name in _TRASH_NAMES if name in names), None)


def folder_keywords(imap: imaplib.IMAP4) -> tuple[tuple[str, ...], bool]:
    """The keywords the selected folder knows (FLAGS, PERMANENTFLAGS), as a person may choose
    them, and whether the server stores keywords of its own there (`\\*`). Takes the answers
    of the SELECT or EXAMINE just made."""
    names: set[str] = set()
    own = False
    for key in ("FLAGS", "PERMANENTFLAGS"):
        _, answer = imap.response(key)
        for item in answer or ():
            if not isinstance(item, bytes):
                continue
            listed_ = _LIST.search(item)
            found = _names(listed_[1] if listed_ else item)
            own = own or (key == "PERMANENTFLAGS" and "\\*" in found)
            names.update(found)
    return shown_keywords(names), own


def _names(data: bytes) -> list[str]:
    return [name for name in data.decode("ascii", "replace").split() if name]


def _day(day: date) -> str:
    return f"{day.day}-{_MONTHS[day.month - 1]}-{day.year}"


def _moment(match: re.Match[bytes]) -> datetime:
    day, month, year, hour, minute, second, zone = (part.decode() for part in match.groups())
    offset = int(zone[1:3]) * 60 + int(zone[3:5])
    tz = timezone(timedelta(minutes=offset if zone[0] == "+" else -offset))
    moment = datetime(
        int(year),
        _MONTHS.index(month) + 1,
        int(day),
        int(hour),
        int(minute),
        int(second),
        tzinfo=tz,
    )
    return moment.astimezone(UTC)
