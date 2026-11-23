"""Managing webhooks: who sees and changes what, the secret, the limit."""

from dataclasses import replace
from datetime import timedelta

import pytest

from lekto.core.domain.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from lekto.core.domain.identity import ViaToken
from lekto.core.domain.ids import DocumentId, EventId, WebhookId, new_id
from lekto.core.domain.reasons import ReasonCode, because
from lekto.core.domain.rights import Actor, TokenRight
from lekto.core.domain.users import Role
from lekto.core.domain.webhooks import (
    BodyFormat,
    DeliveryOutcome,
    ModelCallKind,
    ModelCallRole,
    PrivateTargets,
    WebhookDelivery,
    headers_from_bytes,
    new_secret,
)
from lekto.core.services.webhooks import WebhookService
from lekto.core.services.webhooks.management import (
    headers_context,
    secret_context,
    serving_model_call,
)
from tests import builders
from tests.unit.services.support import World

URL = "http://n8n.lan:5678/webhook/lekto"


async def test_a_user_creates_a_webhook_and_sees_the_secret_once(world: World) -> None:
    user = await world.user()
    created = await world.webhooks.create(
        Actor(user.id), name="n8n", url=URL, event_types=["document.filed"]
    )
    assert created.secret is not None and created.secret.startswith("whsec_")
    assert created.webhook.owner_id == user.id and created.webhook.active
    async with world.uow() as uow:
        stored = await uow.webhooks.get(created.webhook.id)
    # Stored encrypted, bound to the webhook: not the plain secret.
    assert stored.encrypted_secret is not None
    assert created.secret.encode() not in stored.encrypted_secret
    assert (
        world.cipher.decrypt(stored.encrypted_secret, context=secret_context(stored.id)).decode()
        == created.secret
    )
    listed = await world.webhooks.list_webhooks(Actor(user.id))
    assert [webhook.id for webhook in listed] == [created.webhook.id]


async def test_a_bad_url_or_event_type_is_refused(world: World) -> None:
    user = await world.user()
    with pytest.raises(ValidationError):
        await world.webhooks.create(Actor(user.id), name="x", url="ftp://x", event_types=["*"])
    with pytest.raises(ValidationError):
        await world.webhooks.create(Actor(user.id), name="x", url=URL, event_types=["nonsense"])
    assert await world.webhooks.list_webhooks(Actor(user.id)) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:1880/flows",
        "http://192.168.178.1/",
        "http://10.0.0.5:11434/api/pull",
        "http://[::1]/",
        "http://169.254.169.254/latest",
    ],
)
async def test_only_an_admins_webhook_names_an_address_in_the_own_network(
    world: World, url: str
) -> None:
    user, admin = await world.user(), await world.user(role=Role.ADMIN)
    with pytest.raises(ValidationError) as refused:
        await world.webhooks.create(Actor(user.id), name="x", url=url, event_types=["*"])
    assert refused.value.reason is not None
    assert refused.value.reason.code is ReasonCode.WEBHOOK_PRIVATE_ADMINS
    created = await world.webhooks.create(Actor(admin.id), name="x", url=url, event_types=["*"])
    assert created.webhook.url == url
    # A name is checked when it is resolved, before sending.
    await world.webhooks.create(Actor(user.id), name="y", url="http://n8n.lan/", event_types=["*"])


async def test_an_admin_does_not_point_a_users_webhook_into_the_own_network(
    world: World,
) -> None:
    user, admin = await world.user(), await world.user(role=Role.ADMIN)
    created = await world.webhooks.create(Actor(user.id), name="x", url=URL, event_types=["*"])
    with pytest.raises(ValidationError):
        await world.webhooks.update(Actor(admin.id), created.webhook.id, url="http://127.0.0.1/")
    # The rest of the webhook may change.
    await world.webhooks.update(Actor(user.id), created.webhook.id, name="renamed")


async def test_with_none_no_webhook_names_an_address_in_the_own_network(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    service = replace_policy(world, PrivateTargets.NONE)
    with pytest.raises(ValidationError) as refused:
        await service.create(Actor(admin.id), name="x", url="http://127.0.0.1/", event_types=["*"])
    assert refused.value.reason is not None
    assert refused.value.reason.code is ReasonCode.WEBHOOK_PRIVATE_NONE
    everyone = replace_policy(world, PrivateTargets.ALL)
    user = await world.user()
    await everyone.create(Actor(user.id), name="x", url="http://127.0.0.1/", event_types=["*"])


def replace_policy(world: World, targets: PrivateTargets) -> WebhookService:
    return WebhookService(
        world.uow,
        world.clock,
        world.cipher,
        replace(builders.WEBHOOKS, private_targets=targets),
        builders.TEMPLATES,
        retention=builders.RETENTION,
    )


async def test_the_number_of_webhooks_per_user_is_limited(world: World) -> None:
    user, other = await world.user(), await world.user()
    service = WebhookService(
        world.uow,
        world.clock,
        world.cipher,
        replace(builders.WEBHOOKS, per_user=2),
        builders.TEMPLATES,
        retention=builders.RETENTION,
    )
    for _ in range(2):
        await service.create(Actor(user.id), name="x", url=URL, event_types=["*"])
    with pytest.raises(ConflictError):
        await service.create(Actor(user.id), name="x", url=URL, event_types=["*"])
    await service.create(Actor(other.id), name="x", url=URL, event_types=["*"])


async def test_others_do_not_find_a_webhook_but_admins_read_it(world: World) -> None:
    owner, other = await world.user(), await world.user()
    admin = await world.user(role=Role.ADMIN)
    service = world.webhooks
    hook = (await service.create(Actor(owner.id), name="x", url=URL, event_types=["*"])).webhook
    with pytest.raises(NotFoundError):
        await service.get(Actor(other.id), hook.id)
    with pytest.raises(NotFoundError):
        await service.deliveries(Actor(other.id), hook.id)
    with pytest.raises(NotFoundError):
        await service.update(Actor(other.id), hook.id, name="mine")
    assert await service.list_webhooks(Actor(other.id)) == []
    assert (await service.get(Actor(admin.id), hook.id)).id == hook.id
    assert (await service.deliveries(Actor(admin.id), hook.id)).deliveries == ()
    assert [webhook.id for webhook in await service.list_webhooks(Actor(admin.id))] == [hook.id]
    owned = await service.list_webhooks(Actor(admin.id), owner=owner.id)
    assert [webhook.id for webhook in owned] == [hook.id]
    assert await service.list_webhooks(Actor(admin.id), owner=other.id) == []
    assert await service.list_webhooks(Actor(other.id), owner=owner.id) == []


async def test_admins_change_renew_and_delete_other_users_webhooks(world: World) -> None:
    owner, admin = await world.user(), await world.user(role=Role.ADMIN)
    service = world.webhooks
    hook = (await service.create(Actor(owner.id), name="x", url=URL, event_types=["*"])).webhook
    assert (await service.update(Actor(admin.id), hook.id, name="by admin")).name == "by admin"
    renewed = await service.renew_secret(Actor(admin.id), hook.id)
    assert renewed.secret is not None and renewed.secret.startswith("whsec_")
    assert (await service.get(Actor(owner.id), hook.id)).owner_id == owner.id
    await service.delete(Actor(admin.id), hook.id)
    with pytest.raises(NotFoundError):
        await service.get(Actor(owner.id), hook.id)


async def test_the_owner_changes_and_switches_off_and_on(world: World) -> None:
    user = await world.user()
    service = world.webhooks
    hook = (await service.create(Actor(user.id), name="x", url=URL, event_types=["*"])).webhook
    changed = await service.update(
        Actor(user.id),
        hook.id,
        name="HA",
        url="https://ha.example.org/h",
        event_types=["document.filed"],
    )
    assert (changed.name, changed.url, changed.event_types) == (
        "HA",
        "https://ha.example.org/h",
        frozenset({"document.filed"}),
    )
    assert not (await service.update(Actor(user.id), hook.id, active=False)).active
    with pytest.raises(ValidationError):
        await service.update(Actor(user.id), hook.id, url="javascript:x")
    async with world.uow() as uow:
        webhook = await uow.webhooks.get(hook.id)
        webhook.active, webhook.disabled_reason, webhook.failed_streak = (
            False,
            because(ReasonCode.WEBHOOK_FAILING),
            20,
        )
        await uow.webhooks.update(webhook)
        await uow.commit()
    again = await service.update(Actor(user.id), hook.id, active=True)
    assert (again.active, again.disabled_reason, again.failed_streak) == (True, None, 0)


async def test_renewing_the_secret_keeps_the_old_one_for_the_grace_period(world: World) -> None:
    user = await world.user()
    service = world.webhooks
    created = await service.create(Actor(user.id), name="x", url=URL, event_types=["*"])
    renewed = await service.renew_secret(Actor(user.id), created.webhook.id)
    assert renewed.secret != created.secret
    webhook = await service.get(Actor(user.id), created.webhook.id)
    assert webhook.previous_valid_until == world.clock.now() + timedelta(hours=24)
    secrets = [
        world.cipher.decrypt(item, context=secret_context(webhook.id)).decode()
        for item in webhook.encrypted_secrets(world.clock.now())
    ]
    assert secrets == [renewed.secret, created.secret]


async def test_delete_removes_the_webhook_and_a_deleted_user_loses_theirs(world: World) -> None:
    admin, user = await world.user(role=Role.ADMIN), await world.user()
    service = world.webhooks
    first = (await service.create(Actor(user.id), name="x", url=URL, event_types=["*"])).webhook
    await service.create(Actor(user.id), name="y", url=URL, event_types=["*"])
    await service.delete(Actor(user.id), first.id)
    with pytest.raises(NotFoundError):
        await service.get(Actor(user.id), first.id)
    with pytest.raises(NotFoundError):
        await service.delete(Actor(user.id), WebhookId(new_id()))
    await world.users.delete_user(Actor(admin.id), user.id)
    async with world.uow() as uow:
        assert await uow.webhooks.list_all() == []


async def test_a_deactivated_user_cannot_use_webhooks(world: World) -> None:
    admin, user = await world.user(role=Role.ADMIN), await world.user()
    await world.webhooks.create(Actor(user.id), name="x", url=URL, event_types=["*"])
    await world.users.update(Actor(admin.id), user.id, active=False)
    with pytest.raises(AuthenticationError):
        await world.webhooks.list_webhooks(Actor(user.id))
    with pytest.raises(AuthenticationError):
        await world.webhooks.create(Actor(user.id), name="y", url=URL, event_types=["*"])


async def test_a_webhook_may_go_unsigned_and_sign_again_later(world: World) -> None:
    user = await world.user()
    service = world.webhooks
    created = await service.create(
        Actor(user.id), name="HA", url=URL, event_types=["*"], signed=False
    )
    assert created.secret is None and not created.webhook.signed
    renewed = await service.renew_secret(Actor(user.id), created.webhook.id)
    assert renewed.secret is not None and renewed.webhook.signed
    # Nothing signed before: no old secret with a grace period.
    assert renewed.webhook.previous_valid_until is None
    removed = await service.remove_secret(Actor(user.id), created.webhook.id)
    assert not removed.signed and removed.previous_secret is None
    assert not (await service.get(Actor(user.id), created.webhook.id)).signed


def stored_headers(world: World, webhook_id: WebhookId, encrypted: bytes | None) -> dict[str, str]:
    assert encrypted is not None
    return headers_from_bytes(world.cipher.decrypt(encrypted, context=headers_context(webhook_id)))


async def test_the_header_values_go_to_another_address_only_when_given_anew(
    world: World,
) -> None:
    """The values of the headers are never shown again: when an admin moves another user's
    webhook to another address, they must give them anew; the owner moves theirs freely."""
    owner, admin = await world.user(), await world.user(role=Role.ADMIN)
    service = world.webhooks
    created = await service.create(
        Actor(owner.id),
        name="n8n",
        url=URL,
        event_types=["*"],
        headers=[("Authorization", "Bearer x")],
    )
    hook = created.webhook
    other = "http://n8n.example.net/webhook/lekto"

    with pytest.raises(ValidationError) as kept:
        await service.update(Actor(admin.id), hook.id, url=other)
    assert kept.value.reason.code is ReasonCode.WEBHOOK_HEADERS_AGAIN
    with pytest.raises(ValidationError):
        await service.update(Actor(admin.id), hook.id, url=other, headers=[("Authorization", None)])
    await service.update(Actor(admin.id), hook.id, name="renamed")  # the address stays: fine
    moved = await service.update(
        Actor(admin.id), hook.id, url=other, headers=[("Authorization", "Bearer y")]
    )
    assert moved.url == other
    assert stored_headers(world, hook.id, moved.encrypted_headers) == {"Authorization": "Bearer y"}
    back = await service.update(Actor(owner.id), hook.id, url=URL)
    assert back.url == URL


async def test_header_values_are_stored_encrypted_and_kept_by_name(world: World) -> None:
    user = await world.user()
    service = world.webhooks
    created = await service.create(
        Actor(user.id),
        name="HA",
        url=URL,
        event_types=["*"],
        headers=[("Authorization", "Bearer t0ken"), ("X-Tenant", "home")],
    )
    hook = created.webhook
    assert hook.header_names == ("Authorization", "X-Tenant")
    assert hook.encrypted_headers is not None and b"t0ken" not in hook.encrypted_headers
    assert stored_headers(world, hook.id, hook.encrypted_headers) == {
        "Authorization": "Bearer t0ken",
        "X-Tenant": "home",
    }
    # A value left out keeps the stored one (by name, ignoring case); the order follows.
    changed = await service.update(
        Actor(user.id), hook.id, headers=[("X-Tenant", "work"), ("authorization", None)]
    )
    assert changed.header_names == ("X-Tenant", "authorization")
    assert stored_headers(world, hook.id, changed.encrypted_headers) == {
        "X-Tenant": "work",
        "authorization": "Bearer t0ken",
    }
    with pytest.raises(ValidationError, match="new header 'X-New'"):
        await service.update(Actor(user.id), hook.id, headers=[("X-New", None)])
    cleared = await service.update(Actor(user.id), hook.id, headers=[])
    assert cleared.header_names == () and cleared.encrypted_headers is None


async def test_reserved_or_broken_headers_are_refused(world: World) -> None:
    user = await world.user()
    for headers in (
        [("Webhook-Signature", "x")],
        [("Lekto-Task-Token", "x")],
        [("X", "a\nb")],
        [("X-Token", "a"), ("x-token", "b")],  # twice, ignoring case
    ):
        with pytest.raises(ValidationError):
            await world.webhooks.create(
                Actor(user.id), name="x", url=URL, event_types=["*"], headers=headers
            )
    assert await world.webhooks.list_webhooks(Actor(user.id)) == []


async def test_header_values_that_cannot_be_decrypted_must_be_given_anew(world: World) -> None:
    user = await world.user()
    hook = (
        await world.webhooks.create(
            Actor(user.id), name="x", url=URL, event_types=["*"], headers=[("X-Token", "a")]
        )
    ).webhook
    async with world.uow() as uow:
        webhook = await uow.webhooks.get(hook.id)
        webhook.encrypted_headers = b"garbage"
        await uow.webhooks.update(webhook)
        await uow.commit()
    with pytest.raises(ValidationError, match="new header 'X-Token'"):
        await world.webhooks.update(Actor(user.id), hook.id, headers=[("X-Token", None)])
    changed = await world.webhooks.update(Actor(user.id), hook.id, headers=[("X-Token", "b")])
    assert stored_headers(world, hook.id, changed.encrypted_headers) == {"X-Token": "b"}


async def test_a_template_body_is_checked_when_saved(world: World) -> None:
    user = await world.user()
    service = world.webhooks
    good = (
        '{"title": {{ title | json }}, "event": {{ event.type | json }}, "lane": {{ lane | json }}}'
    )
    hook = (
        await service.create(
            Actor(user.id),
            name="HA",
            url=URL,
            event_types=["*"],
            body=BodyFormat.TEMPLATE,
            body_template=good,
        )
    ).webhook
    assert (hook.body, hook.body_template) == (BodyFormat.TEMPLATE, good)
    for template, error in (
        ('{"x": {{ nonsense }}}', "unknown value nonsense"),
        ('{"x": {{ field.betrag }}}', "unknown value field.betrag"),
        ('{"x": {{ title | nofilter }}}', "unknown filter"),
        ('{"x": {% if %}}', "invalid template"),
    ):
        with pytest.raises(ValidationError, match=error) as refused:
            await service.update(
                Actor(user.id), hook.id, body=BodyFormat.TEMPLATE, body_template=template
            )
        # Lekto's own message has a code and says where; the engine's is text.
        if error.startswith("unknown value"):
            assert refused.value.reason.code is ReasonCode.TEMPLATE_UNKNOWN_VALUE_AT
            assert refused.value.reason.params["at"] == "body_template"
        else:
            assert refused.value.reason.code is ReasonCode.ERROR
    with pytest.raises(ValidationError):
        await service.update(Actor(user.id), hook.id, body_template=good)  # without the body
    full = await service.update(Actor(user.id), hook.id, body=BodyFormat.FULL)
    assert (full.body, full.body_template) == (BodyFormat.FULL, None)


def test_new_secrets_do_not_repeat() -> None:
    assert new_secret() != new_secret()


async def test_an_admin_makes_an_admins_webhook_serve_as_a_model_call(world: World) -> None:
    admin, user = await world.user(role=Role.ADMIN), await world.user()
    service = world.webhooks
    role = ModelCallRole(ModelCallKind.PROPOSE, timedelta(minutes=10))
    created = await service.create(
        Actor(admin.id), name="agent", url=URL, event_types=[], model_call=role
    )
    assert created.webhook.model_call == role
    async with world.uow() as uow:
        assert await serving_model_call(uow, ModelCallKind.PROPOSE) == created.webhook
        assert await serving_model_call(uow, ModelCallKind.EXTRACT) is None
    # Not on a user's webhook, not by a user, not even an admin on a user's.
    own = (await service.create(Actor(user.id), name="x", url=URL, event_types=[])).webhook
    extract = ModelCallRole(ModelCallKind.EXTRACT)
    with pytest.raises(PermissionDeniedError):
        await service.create(Actor(user.id), name="x", url=URL, event_types=[], model_call=extract)
    with pytest.raises(PermissionDeniedError):
        await service.update(Actor(user.id), own.id, model_call=extract)
    with pytest.raises(PermissionDeniedError):
        await service.update(Actor(admin.id), own.id, model_call=extract)
    # A change that leaves it alone keeps it; None ends it.
    assert (await service.update(Actor(admin.id), created.webhook.id, name="a")).model_call == role
    assert (
        await service.update(Actor(admin.id), created.webhook.id, model_call=None)
    ).model_call is None


async def test_one_active_webhook_serves_each_model_call(world: World) -> None:
    admin, other = await world.user(role=Role.ADMIN), await world.user(role=Role.ADMIN)
    service = world.webhooks
    propose = ModelCallRole(ModelCallKind.PROPOSE)
    first = (
        await service.create(
            Actor(admin.id), name="first", url=URL, event_types=[], model_call=propose
        )
    ).webhook
    with pytest.raises(ConflictError, match="'first' serves as the model call 'propose'"):
        await service.create(
            Actor(other.id), name="second", url=URL, event_types=[], model_call=propose
        )
    # Switched off, it serves no more: another may, and switching it on again conflicts.
    off = await service.create(
        Actor(other.id), name="off", url=URL, event_types=[], active=False, model_call=propose
    )
    await service.update(Actor(admin.id), first.id, active=False)
    second = (
        await service.create(
            Actor(other.id), name="second", url=URL, event_types=[], model_call=propose
        )
    ).webhook
    with pytest.raises(ConflictError):
        await service.update(Actor(admin.id), first.id, active=True)
    with pytest.raises(ConflictError):
        await service.update(Actor(other.id), off.webhook.id, active=True)
    async with world.uow() as uow:
        assert await serving_model_call(uow, ModelCallKind.PROPOSE) == second
    # The other kind is free.
    extract = ModelCallRole(ModelCallKind.EXTRACT)
    assert (
        await service.update(Actor(admin.id), first.id, model_call=extract)
    ).model_call == extract


async def test_a_model_call_of_an_admin_no_more_serves_no_more(world: World) -> None:
    admin = await world.user(role=Role.ADMIN)
    created = await world.webhooks.create(
        Actor(admin.id),
        name="agent",
        url=URL,
        event_types=[],
        model_call=ModelCallRole(ModelCallKind.EXTRACT),
    )
    async with world.uow() as uow:
        user = await uow.users.get(admin.id)
        user.role = Role.USER
        await uow.users.update(user)
        await uow.commit()
    async with world.uow() as uow:
        assert await serving_model_call(uow, ModelCallKind.EXTRACT) is None
    # Its owner may still take the role away.
    webhook = await world.webhooks.update(Actor(admin.id), created.webhook.id, model_call=None)
    assert webhook.model_call is None


async def test_the_log_names_documents_as_far_as_the_viewer_may_read_them(world: World) -> None:
    owner, stranger = await world.user("owner"), await world.user("stranger")
    admin = await world.user(role=Role.ADMIN)
    mine = await world.pipeline().receive(
        Actor(owner.id), builders.incoming(b"%PDF-1"), filename="a.pdf"
    )
    theirs = await world.pipeline().receive(
        Actor(stranger.id), builders.incoming(b"%PDF-2"), filename="b.pdf"
    )
    hook = (
        await world.webhooks.create(Actor(owner.id), name="x", url=URL, event_types=["*"])
    ).webhook

    def entry(
        document: DocumentId | None, outcome: DeliveryOutcome, event: str = "document.filed"
    ) -> WebhookDelivery:
        return WebhookDelivery.record(
            webhook_id=hook.id,
            event_id=EventId(new_id()),
            event_type=event,
            document_id=document,
            attempt=1,
            started_at=world.clock.now(),
            duration_ms=5,
            outcome=outcome,
            status_code=200 if outcome is DeliveryOutcome.DELIVERED else 503,
        )

    gone = DocumentId(new_id())
    async with world.uow() as uow:
        for delivery in (
            entry(mine.id, DeliveryOutcome.DELIVERED),
            entry(theirs.id, DeliveryOutcome.GAVE_UP),
            entry(gone, DeliveryOutcome.RETRYING, "document.deleted"),
            entry(None, DeliveryOutcome.DELIVERED, "webhook.test"),
        ):
            await uow.webhooks.add_delivery(delivery)
        await uow.commit()

    seen = {
        view.delivery.event_type + str(view.delivery.document_id): view
        for view in (await world.webhooks.deliveries(Actor(owner.id), hook.id)).deliveries
    }
    readable = seen[f"document.filed{mine.id}"]
    assert readable.document is not None and readable.document.title == mine.title
    assert not readable.document_hidden
    other = seen[f"document.filed{theirs.id}"]
    assert (other.document, other.document_hidden) == (None, True)
    assert (
        seen[f"document.deleted{gone}"].document_hidden,
        seen["webhook.testNone"].document_hidden,
    ) == (
        True,
        False,
    )
    as_admin = (
        await world.webhooks.deliveries(Actor(admin.id), hook.id, event_type="document.filed")
    ).deliveries
    assert {view.document.title for view in as_admin if view.document} == {mine.title, theirs.title}

    problems = await world.webhooks.deliveries(
        Actor(owner.id), hook.id, outcomes={DeliveryOutcome.GAVE_UP, DeliveryOutcome.RETRYING}
    )
    assert {view.delivery.event_type for view in problems.deliveries} == {
        "document.filed",
        "document.deleted",
    }
    assert problems.total == 2
    rest = await world.webhooks.deliveries(Actor(owner.id), hook.id, offset=3)
    assert (len(rest.deliveries), rest.total) == (1, 4)

    summary = await world.webhooks.delivery_summary(Actor(owner.id), hook.id)
    assert summary.counts == {
        DeliveryOutcome.DELIVERED: 2,
        DeliveryOutcome.GAVE_UP: 1,
        DeliveryOutcome.RETRYING: 1,
    }
    assert summary.event_types == ("document.deleted", "document.filed", "webhook.test")
    assert summary.kept_since == world.clock.now() - builders.RETENTION
    filed = await world.webhooks.delivery_summary(
        Actor(owner.id), hook.id, event_type="document.filed"
    )
    assert filed.counts == {DeliveryOutcome.DELIVERED: 1, DeliveryOutcome.GAVE_UP: 1}
    with pytest.raises(NotFoundError):
        await world.webhooks.delivery_summary(Actor(stranger.id), hook.id)


async def test_a_webhook_created_through_a_token_goes_with_the_token(world: World) -> None:
    """Revoking the token deletes the webhooks created through it, the others stay
    (`.knowledge/plans/token-rights.md`)."""
    admin = await world.user(role=Role.ADMIN)
    rights = frozenset({TokenRight.WEBHOOKS_WRITE, TokenRight.ADMIN_PRIVATE_WEBHOOKS})
    token, _ = await world.auth.create_api_token(Actor(admin.id), "Home Assistant", rights)
    created = await world.webhooks.create(
        Actor(admin.id, rights),
        name="Home Assistant",
        url="http://127.0.0.1:8123/api/webhook/lekto",
        event_types=["*"],
        via=ViaToken.of(token),
    )
    kept = await world.webhooks.create(Actor(admin.id), name="kept", url=URL, event_types=["*"])
    assert created.webhook.api_token_id == token.id
    assert kept.webhook.api_token_id is None

    await world.auth.revoke_api_token(Actor(admin.id), token.id)
    with pytest.raises(NotFoundError):
        await world.webhooks.get(Actor(admin.id), created.webhook.id)
    assert (await world.webhooks.get(Actor(admin.id), kept.webhook.id)).name == "kept"


async def test_a_token_needs_its_right_for_an_address_in_the_own_network(world: World) -> None:
    """An admin's token reaches an address that is not public only with
    `admin:private_webhooks`, on creating and on changing the address."""
    admin = await world.user(role=Role.ADMIN)
    url = "http://127.0.0.1:8123/api/webhook/lekto"
    writes = frozenset({TokenRight.WEBHOOKS_WRITE})
    without = Actor(admin.id, writes)
    with pytest.raises(ValidationError):
        await world.webhooks.create(without, name="x", url=url, event_types=["*"])
    public = await world.webhooks.create(without, name="x", url=URL, event_types=["*"])
    with pytest.raises(ValidationError):
        await world.webhooks.update(without, public.webhook.id, url=url)
    allowed = Actor(admin.id, writes | {TokenRight.ADMIN_PRIVATE_WEBHOOKS})
    await world.webhooks.update(allowed, public.webhook.id, url=url)
