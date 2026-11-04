"""Where a document came from: the mail that brought it."""

from datetime import datetime

from pydantic import BaseModel, Field

from lekto.core.domain.mail_intake import MailOrigin, OriginRole
from lekto.core.domain.mail_message import Address


class AddressOut(BaseModel):
    name: str = Field(description="The display name; empty where the mail gives none.")
    address: str

    @classmethod
    def of(cls, address: Address) -> "AddressOut":
        return cls(name=address.name, address=address.address)


class MailOriginOut(BaseModel):
    """The mail a document came with, as it was then (a mailbox renamed or deleted since keeps
    its name here)."""

    mailbox: str = Field(description="The mailbox's name.")
    rule: str | None = Field(description="The mail rule that took it; null: the fallback.")
    role: OriginRole = Field(
        description="`cover`: the mail's text; `attachment`: one of its files."
    )
    filename: str | None
    subject: str
    sender: list[AddressOut]
    to: list[AddressOut]
    cc: list[AddressOut]
    sent_at: datetime | None = Field(description="The mail's own date.")
    arrived_at: datetime = Field(description="When it arrived at the mailbox.")
    forwarded_by: list[AddressOut] = Field(
        description="Who forwarded the mail that held it, outermost first."
    )
    message_id: str | None

    @classmethod
    def of(cls, origin: MailOrigin) -> "MailOriginOut":
        return cls(
            mailbox=origin.mailbox,
            rule=origin.rule,
            role=origin.role,
            filename=origin.filename,
            subject=origin.subject,
            sender=[AddressOut.of(item) for item in origin.sender],
            to=[AddressOut.of(item) for item in origin.to],
            cc=[AddressOut.of(item) for item in origin.cc],
            sent_at=origin.sent_at,
            arrived_at=origin.arrived_at,
            forwarded_by=[AddressOut.of(item) for item in origin.forwarded_by],
            message_id=origin.message_id,
        )


class OriginOut(BaseModel):
    """Where a document came from; `mail` for one a mail brought, else null."""

    mail: MailOriginOut | None
