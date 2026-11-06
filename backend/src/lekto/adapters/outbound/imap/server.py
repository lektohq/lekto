"""The IMAP adapter of `MailServer`: signs in, in a thread, and leaves again: for a list of the
folders, or around a session of a fetch."""

import asyncio
import imaplib
import ssl
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager, contextmanager, suppress
from datetime import timedelta

from lekto.adapters.outbound.imap.names import listed
from lekto.adapters.outbound.imap.session import ImapMailSession, folder_keywords
from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.reasons import Reason, ReasonCode, because
from lekto.core.ports.mail_server import MailAccount, MailServerError

MAX_DETAIL = 200
INBOX = "INBOX"


class ImapMailServer:
    """`timeout` holds for connecting and for every answer. `ssl_context` checks the server's
    certificate (the system's trusted ones unless given)."""

    def __init__(
        self,
        *,
        timeout: timedelta = timedelta(seconds=30),
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._timeout = timeout.total_seconds()
        self._ssl_context = ssl_context or ssl.create_default_context()

    async def account(self, login: MailLogin) -> MailAccount:
        return await asyncio.to_thread(self._run, login, _account)

    @asynccontextmanager
    async def session(self, login: MailLogin) -> AsyncIterator[ImapMailSession]:
        imap = await asyncio.to_thread(self._connect, login)
        try:
            await asyncio.to_thread(self._sign_in, imap, login)
            yield ImapMailSession(imap, _guarded)
        finally:
            await asyncio.to_thread(_leave, imap)

    def _run[T](self, login: MailLogin, work: Callable[[imaplib.IMAP4], T]) -> T:
        with self._session(login) as imap:
            try:
                return work(imap)
            except imaplib.IMAP4.error as error:
                raise MailServerError(_server_error(error)) from error

    @contextmanager
    def _session(self, login: MailLogin) -> Iterator[imaplib.IMAP4]:
        imap = self._connect(login)
        try:
            self._sign_in(imap, login)
            yield imap
        finally:  # also after a refused login: the server ends the session
            _leave(imap)

    def _connect(self, login: MailLogin) -> imaplib.IMAP4:
        try:
            if login.security is MailSecurity.TLS:
                return imaplib.IMAP4_SSL(
                    login.host, login.port, ssl_context=self._ssl_context, timeout=self._timeout
                )
            imap = imaplib.IMAP4(login.host, login.port, timeout=self._timeout)
        except ssl.SSLError as error:
            raise MailServerError(_tls_failed(login)) from error
        except imaplib.IMAP4.error as error:
            raise MailServerError(_server_error(error)) from error
        except (OSError, EOFError) as error:
            raise MailServerError(because(ReasonCode.MAIL_UNREACHABLE, host=login.host)) from error
        if login.security is MailSecurity.STARTTLS:
            try:
                imap.starttls(self._ssl_context)
            except (ssl.SSLError, imaplib.IMAP4.error, OSError) as error:
                _close(imap)
                raise MailServerError(_tls_failed(login)) from error
        return imap

    @staticmethod
    def _sign_in(imap: imaplib.IMAP4, login: MailLogin) -> None:
        try:
            if login.username.isascii() and login.password.isascii():
                imap.login(login.username, login.password)
            elif "AUTH=PLAIN" in imap.capabilities:
                secret = f"\0{login.username}\0{login.password}".encode()
                imap.authenticate("PLAIN", lambda _: secret)
            else:
                _login_with_literal(imap, login)
        except imaplib.IMAP4.abort as error:
            raise MailServerError(_server_error(error)) from error
        except imaplib.IMAP4.error as error:
            raise MailServerError(because(ReasonCode.MAIL_LOGIN_FAILED)) from error
        except OSError as error:
            raise MailServerError(because(ReasonCode.MAIL_UNREACHABLE, host=login.host)) from error
        _learn_capabilities(imap)


def _learn_capabilities(imap: imaplib.IMAP4) -> None:
    """The server's capabilities once signed in. `imaplib` keeps those of the greeting, and many
    servers name little more there than how to sign in: iCloud names UIDPLUS only afterwards,
    so a moved mail stayed in the folder marked deleted (Tobi, 06.11.2026); Dovecot names MOVE
    only afterwards. Without an answer the greeting's stay."""
    try:
        status, answer = imap.capability()
    except (imaplib.IMAP4.error, OSError):
        return
    line = answer[-1] if status == "OK" and answer else None
    if isinstance(line, bytes) and line.strip():
        imap.capabilities = tuple(line.decode("ascii", "replace").upper().split())


def _login_with_literal(imap: imaplib.IMAP4, login: MailLogin) -> None:
    """LOGIN with the password as a literal in UTF-8, for a server without AUTH=PLAIN
    (`imaplib` sends quoted strings in ASCII only)."""
    if not login.username.isascii():
        raise imaplib.IMAP4.error("a user name beyond ASCII needs AUTH=PLAIN")
    user = '"' + login.username.replace("\\", "\\\\").replace('"', '\\"') + '"'
    imap.literal = login.password.encode()  # type: ignore[assignment]  # bytes are sent as is
    status, answer = imap.xatom("LOGIN", user)
    if status != "OK":
        raise imaplib.IMAP4.error(_text(answer))
    imap.state = "AUTH"


def _leave(imap: imaplib.IMAP4) -> None:
    with suppress(imaplib.IMAP4.error, OSError):
        imap.logout()


def _guarded[T](work: Callable[..., T], *args: object) -> T:
    """`work` in a session: what the server answers as an error is a MailServerError; a lost
    connection says the server cannot be reached."""
    try:
        return work(*args)
    except imaplib.IMAP4.abort as error:
        raise MailServerError(_server_error(error)) from error
    except imaplib.IMAP4.error as error:
        raise MailServerError(_server_error(error)) from error
    except OSError as error:
        raise MailServerError(_server_error(error)) from error


def _account(imap: imaplib.IMAP4) -> MailAccount:
    """The folders, and the keywords of the inbox, read only (EXAMINE: nothing changes)."""
    folders = _folders(imap)
    keywords: tuple[str, ...] = ()
    own = False
    status, _ = imap.select(INBOX, readonly=True)
    if status == "OK":
        keywords, own = folder_keywords(imap)
    return MailAccount(folders=folders, keywords=keywords, own_keywords=own)


def _folders(imap: imaplib.IMAP4) -> tuple[str, ...]:
    status, entries = imap.list()
    if status != "OK":
        raise imaplib.IMAP4.error(_text(entries))
    answer: list[bytes | tuple[bytes, bytes] | None] = list(entries)
    names = {name for name, flags in listed(answer) if "\\noselect" not in flags}
    names = {INBOX if name.upper() == INBOX else name for name in names}
    return tuple(sorted(names, key=lambda name: (name != INBOX, name.casefold())))


def _close(imap: imaplib.IMAP4) -> None:
    with suppress(OSError):
        imap.shutdown()


def _tls_failed(login: MailLogin) -> Reason:
    return because(ReasonCode.MAIL_TLS_FAILED, host=login.host)


def _server_error(error: Exception) -> Reason:
    return because(ReasonCode.MAIL_SERVER_ERROR, detail=_text(error.args) or type(error).__name__)


def _text(parts: object) -> str:
    """What the server said, short and as text."""
    items = parts if isinstance(parts, list | tuple) else [parts]
    words = [
        item.decode(errors="replace") if isinstance(item, bytes) else str(item)
        for item in items
        if item is not None
    ]
    return " ".join(words).strip()[:MAX_DETAIL]
