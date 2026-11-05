"""Where a document came from: the mail that brought it."""

from datetime import datetime

from pydantic import BaseModel, Field

from lekto.core.domain.mail_intake import MailOrigin, OriginRole
from lekto.core.domain.mail_message import Address
from lekto.core.domain.mail_traits import FlagColor, Importance


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
    importance: Importance | None = Field(
        description="As the letter's header gives it; null for a document taken before."
    )
    keywords: list[str] | None = Field(
        description="The keywords the mail had on the server when fetched; null: not known."
    )
    flag: FlagColor | None = Field(
        description="The colour of its flag on the server then; null: not flagged or not known."
    )

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
            importance=origin.importance,
            keywords=None if origin.marks is None else list(origin.marks.keywords),
            flag=None if origin.marks is None else origin.marks.flag,
        )


class OriginOut(BaseModel):
    """Where a document came from; `mail` for one a mail brought, else null."""

    mail: MailOriginOut | None
