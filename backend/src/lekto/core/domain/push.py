"""Notifications on a person's devices through web push (RFC 8030; web/DESIGN.md, "App").

A browser subscribes at its push service (Apple's, Google's, Mozilla's, Microsoft's) and hands
Lekto the address there (`endpoint`) and two keys (`p256dh`, `auth`). Lekto encrypts each message
for the browser (RFC 8291) and signs its request for the push service (VAPID, RFC 8292); the push
service sees neither the content nor whom it is for. The address must be one of a known push
service's: Lekto sends nothing to an address a caller made up.
"""

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit

from lekto.core.domain.errors import ValidationError
from lekto.core.domain.ids import DocumentId, PushDeviceId, UserId
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.validation import require_name, require_utc

# The hosts of the push services browsers use, each with its subdomains: Safari (Apple), Chrome
# and Edge on Android and elsewhere (Google), Firefox (Mozilla), Edge on Windows (Microsoft).
PUSH_SERVICES = (
    "push.apple.com",
    "fcm.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
)

MAX_DEVICES = 20
"""The devices one person receives notifications on."""

LOCALES = ("de", "en")
"""The languages of the web UI, and so of its notifications."""

MAX_ENDPOINT = 2000
MAX_DEVICE_NAME = 100

GIVE_UP_AFTER = 20
"""Failed deliveries in a row after which a device is forgotten (the browser dropped it without
the push service saying so)."""


def push_service_of(endpoint: str) -> str | None:
    """The known push service an address belongs to (its host suffix), None for any other."""
    try:
        parts = urlsplit(endpoint)
    except ValueError:
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or not host or parts.username or parts.password:
        return None
    return next((s for s in PUSH_SERVICES if host == s or host.endswith(f".{s}")), None)


def _key(value: str, length: int) -> bytes | None:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (binascii.Error, ValueError):
        return None
    return raw if len(raw) == length else None


@dataclass(kw_only=True)
class PushDevice:
    """A browser that receives a person's notifications. `name` says which ("iPhone",
    "Mac · Safari"); `locale` the language its notifications speak (the web UI's when it
    subscribed: the service worker words them); `last_success_at` when a message last reached its
    push service; `failures` the failed deliveries since."""

    id: PushDeviceId
    user_id: UserId
    endpoint: str
    p256dh: str
    auth: str
    name: str
    created_at: datetime
    locale: str = "en"
    last_success_at: datetime | None = None
    failures: int = 0
    version: int = 1

    def __post_init__(self) -> None:
        self.name = require_name(self.name, "device name", max_length=MAX_DEVICE_NAME)
        self.created_at = require_utc(self.created_at, "created_at")
        if self.locale not in LOCALES:
            self.locale = "en"
        if len(self.endpoint) > MAX_ENDPOINT or push_service_of(self.endpoint) is None:
            raise ValidationError(because(ReasonCode.PUSH_ENDPOINT_REFUSED))
        public = _key(self.p256dh, 65)
        if public is None or public[0] != 4 or _key(self.auth, 16) is None:
            raise ValidationError(because(ReasonCode.PUSH_KEYS_INVALID))

    @property
    def public_key(self) -> bytes:
        """The browser's public key (P-256, uncompressed)."""
        key = _key(self.p256dh, 65)
        assert key is not None
        return key

    @property
    def auth_secret(self) -> bytes:
        key = _key(self.auth, 16)
        assert key is not None
        return key


class PushKind(StrEnum):
    """What a notification is about; the service worker words it in the device's language."""

    TEST = "test"
    WAITING = "waiting"
    MAILBOX_FAILED = "mailbox_failed"
    WEBHOOK_DISABLED = "webhook_disabled"
    JOB_FAILED = "job_failed"


@dataclass(frozen=True, kw_only=True)
class PushMessage:
    """A notification as data: its `kind` and `params` (the service worker words it), `url` to
    open on a tap (a path of the web UI), `badge` the number on the app's icon (None: leave it),
    `tag` replaces an earlier notification with the same tag on the device, `topic` a message the
    push service still holds (at most 32 characters of `[A-Za-z0-9_-]`)."""

    kind: PushKind
    url: str
    params: Mapping[str, object] = field(default_factory=dict)
    badge: int | None = None
    tag: str | None = None
    topic: str | None = None
    urgency: str = "normal"
    ttl_seconds: int = 24 * 60 * 60

    def payload(self, locale: str) -> dict[str, object]:
        """What the service worker gets, as JSON."""
        return {
            "kind": self.kind.value,
            "params": dict(self.params),
            "url": self.url,
            "badge": self.badge,
            "tag": self.tag,
            "locale": locale,
        }


PENDING_LIMIT = 50
"""Documents that came to wait since the last notification, kept for the next one at most."""

ADMIN_KINDS = frozenset({PushKind.MAILBOX_FAILED, PushKind.JOB_FAILED})
"""What only admins are told about (mailboxes and jobs are theirs to look after)."""

DEFAULT_KINDS = frozenset(
    {PushKind.WAITING, PushKind.MAILBOX_FAILED, PushKind.WEBHOOK_DISABLED, PushKind.JOB_FAILED}
)


@dataclass(kw_only=True)
class PushPreferences:
    """What a person wants to be told about (`kinds`; a test always comes), whether the titles
    of documents stand in a notification (`titles`: it may show on a locked screen), and the
    documents that came to wait in their inbox since the last notification (`pending`).
    Its id is the user's."""

    id: UserId
    kinds: frozenset[PushKind] = DEFAULT_KINDS
    titles: bool = True
    pending: tuple[DocumentId, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        self.kinds = frozenset(kind for kind in self.kinds if kind is not PushKind.TEST)
        self.pending = tuple(dict.fromkeys(self.pending))[-PENDING_LIMIT:]

    def wants(self, kind: PushKind) -> bool:
        return kind is PushKind.TEST or kind in self.kinds

    def note_waiting(self, document: DocumentId) -> None:
        self.pending = tuple(
            dict.fromkeys((*(d for d in self.pending if d != document), document))
        )[-PENDING_LIMIT:]
