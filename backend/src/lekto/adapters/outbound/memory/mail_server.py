"""A mail server in memory: accounts with their folders, for tests and the memory container."""

from dataclasses import dataclass, field

from lekto.core.domain.mail import MailLogin, MailSecurity
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.ports.mail_server import MailServerError


@dataclass
class MemoryMailAccount:
    password: str
    security: MailSecurity
    folders: list[str] = field(default_factory=lambda: ["INBOX"])


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

    async def folders(self, login: MailLogin) -> tuple[str, ...]:
        account = self._account(login)
        return tuple(sorted(account.folders, key=lambda name: (name != "INBOX", name)))

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
