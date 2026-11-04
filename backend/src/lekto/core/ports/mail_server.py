"""A mail server Lekto fetches from (IMAP).

First adapter: `imaplib` of the standard library, in a thread. The port signs in for every call
and leaves again; nothing stays open between fetches (no IDLE: Lekto fetches every few minutes).
What goes wrong comes back as a `MailServerError` with a reason an admin can act on: the server
cannot be reached, no secure connection, user name or password refused, a folder missing, or the
server's own error.
"""

from typing import Protocol

from lekto.core.domain.errors import DomainError
from lekto.core.domain.mail import MailLogin
from lekto.core.domain.reasons import Reason


class MailServerError(DomainError):
    """The mail server could not do what was asked; `reason` says why (`MAIL_...`)."""

    def __init__(self, reason: Reason) -> None:
        super().__init__(reason)


class MailServer(Protocol):
    async def folders(self, login: MailLogin) -> tuple[str, ...]:
        """The folders of the account, by their full names as the server separates them
        (`INBOX`, `INBOX/Rechnungen`, ...), sorted, `INBOX` first. Raises MailServerError."""
        ...
