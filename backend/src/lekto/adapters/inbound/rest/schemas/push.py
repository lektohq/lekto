"""Bodies and answers of `/push`."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lekto.core.domain.push import (
    MAX_DEVICE_NAME,
    MAX_ENDPOINT,
    PushDevice,
    PushKind,
    PushPreferences,
)
from lekto.core.ports.push import PushOutcome, PushResult


class PushSettingsOut(BaseModel):
    enabled: bool = Field(description="Whether the server sends notifications (a VAPID key).")
    public_key: str | None = Field(
        description=(
            "The key a browser subscribes with (`applicationServerKey`: P-256, uncompressed, "
            "base64url); null without notifications."
        )
    )


class PushKeysIn(BaseModel):
    p256dh: str = Field(max_length=200, description="The browser's public key (base64url).")
    auth: str = Field(max_length=100, description="The browser's auth secret (base64url).")


class PushDeviceIn(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "endpoint": "https://web.push.apple.com/QGuQyavXutnMH9Byyn6xHn",
                    "keys": {
                        "p256dh": (
                            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7"
                            "Vd8pZGH6SRpkNtoIAiw4"
                        ),
                        "auth": "BTBZMqHH6r4Tts7J_aSIgg",
                    },
                    "name": "iPhone",
                    "locale": "de",
                }
            ]
        },
    )

    endpoint: str = Field(
        max_length=MAX_ENDPOINT,
        description="The subscription's address at the push service (`PushSubscription.endpoint`).",
    )
    keys: PushKeysIn
    name: str = Field(min_length=1, max_length=MAX_DEVICE_NAME, description="Which device it is.")
    locale: Literal["de", "en"] = Field(
        description="The language the device's notifications speak."
    )


class PushDeviceOut(BaseModel):
    id: UUID
    name: str
    locale: str
    endpoint: str = Field(
        description="The address at the push service: a browser finds its own device by it."
    )
    created_at: datetime
    last_success_at: datetime | None = Field(
        description="When a message last reached the push service."
    )

    @classmethod
    def of(cls, device: PushDevice) -> "PushDeviceOut":
        return cls(
            id=device.id,
            name=device.name,
            locale=device.locale,
            endpoint=device.endpoint,
            created_at=device.created_at,
            last_success_at=device.last_success_at,
        )


class PushTestOut(BaseModel):
    outcome: PushOutcome = Field(
        description=(
            "`delivered`: the push service took it; `gone`: it no longer knows the device, which "
            "is forgotten; `failed`: no answer or a refusal."
        )
    )

    @classmethod
    def of(cls, result: PushResult) -> "PushTestOut":
        return cls(outcome=result.outcome)


NoticeKind = Literal["waiting", "mailbox_failed", "webhook_disabled", "job_failed"]


class PushPreferencesBody(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"kinds": ["waiting", "webhook_disabled"], "titles": True}]
        },
    )

    kinds: list[NoticeKind] = Field(
        description=(
            "What the caller is told about: `waiting` (documents wait in their inbox), "
            "`webhook_disabled` (one of their webhooks was switched off), and for admins "
            "`mailbox_failed` (a mailbox fails to fetch) and `job_failed` (a job was given up)."
        )
    )
    titles: bool = Field(
        description=(
            "Whether a notification names the documents' titles (it may show on a locked screen)."
        )
    )

    @classmethod
    def of(cls, preferences: PushPreferences) -> "PushPreferencesBody":
        return cls(
            kinds=sorted(kind.value for kind in preferences.kinds),  # type: ignore[misc]
            titles=preferences.titles,
        )

    def kinds_domain(self) -> frozenset[PushKind]:
        return frozenset(PushKind(kind) for kind in self.kinds)
