"""Rules that send through webhooks (`SendWebhook`): on arrival once the document is filed,
after a change at once, applied to existing documents per document; and who may send what."""

import pytest

from lekto.core.domain.documents import Document, DocumentChanges
from lekto.core.domain.errors import NotFoundError, ValidationError
from lekto.core.domain.ids import UserId, WebhookId, new_id
from lekto.core.domain.json_value import JsonObject
from lekto.core.domain.pipeline import RULES, Lane, Node
from lekto.core.domain.reasons import ReasonCode
from lekto.core.domain.rights import Actor
from lekto.core.domain.rules import (
    Action,
    ForceReview,
    SendWebhook,
    SetSpace,
    SetTitle,
    Trigger,
)
from lekto.core.domain.spaces import SpaceRole
from lekto.core.domain.users import User
from lekto.core.domain.webhooks import RULE_SEND, Webhook
from lekto.core.services.rules.changes import ChangeRules
from lekto.core.services.rules.running import (
    CHANGES_UNFIT,
    SENDS,
    SENDS_REFUSED,
    Prepared,
    refusal,
)
from lekto.core.services.webhooks import DELIVER_JOB
from tests import builders
from tests.builders import TEMPLATES
from tests.unit.services.rules_support import (
    MAX_TEXT,
    RuleWorld,
    add_tags,
    channel_api,
    definition,
    has_tag,
    rule_world,
)
from tests.unit.services.support import World

URL = "http://ha.lan:8123/api/webhook/lekto"


async def hook(world: World, owner: User, name: str = "HA") -> Webhook:
    created = await world.webhooks.create(Actor(owner.id), name=name, url=URL, event_types=[])
    return created.webhook


def sent(world: World) -> list[JsonObject]:
    """The payloads of the queued requests rules send."""
    return [
        job.payload
        for job in world.database.jobs.values()
        if job.kind == DELIVER_JOB and job.payload.get("type") == RULE_SEND
    ]


async def notifying(r: RuleWorld, owner: User, webhook: Webhook, *more: Action) -> None:
    """A rule of the owner's personal space that sends every upload through `webhook`."""
    await r.personal_rule(
        owner, definition("Notify", channel_api(), *more, SendWebhook(webhook.id))
    )


async def test_a_green_document_sends_when_it_is_filed(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    await notifying(r, owner, webhook)
    document = await r.arrive(owner)
    assert document.lane is Lane.GREEN
    (payload,) = sent(world)
    assert payload["webhook_id"] == str(webhook.id)
    assert payload["document_id"] == str(document.id)
    rule = payload["rule"]
    assert isinstance(rule, dict) and rule["name"] == "Notify"
    (entry,) = [item for item in await r.log(document) if item.node is Node.FILE]
    assert entry.result.output[SENDS] != []


async def test_a_yellow_document_sends_once_confirmed_and_only_once(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    await notifying(r, owner, webhook, ForceReview("look first"))
    document = await r.arrive(owner)
    assert document.lane is Lane.YELLOW
    assert sent(world) == []  # waiting in the inbox: nothing goes yet
    pipeline = r.pipeline()
    await pipeline.confirm(Actor(owner.id), document.id, DocumentChanges(), accept_suggestions=True)
    await world.drain(pipeline)
    assert (await r.stored(document)).lane is Lane.GREEN
    assert [payload["document_id"] for payload in sent(world)] == [str(document.id)]


async def test_a_webhook_whose_owner_cannot_read_the_document_turns_it_yellow(
    world: World,
) -> None:
    """A global rule of an admin, whose webhook reports only what the admin reaches as a user:
    another user's upload waits for a person, and after their click it is only reported."""
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, r.admin)
    await r.global_rule(definition("Everything", channel_api(), SendWebhook(webhook.id)))
    document = await r.arrive(owner)
    assert document.lane is Lane.YELLOW
    (entry,) = await r.rule_entries(document, RULES)
    assert [reason.code for reason in entry.result.reasons] == [ReasonCode.RULE_WEBHOOK_UNREADABLE]
    pipeline = r.pipeline()
    await pipeline.confirm(Actor(owner.id), document.id, DocumentChanges(), accept_suggestions=True)
    await world.drain(pipeline)
    assert (await r.stored(document)).lane is Lane.GREEN
    assert sent(world) == []
    latest = (await r.rule_entries(document, RULES))[-1]
    assert latest.result.output[SENDS_REFUSED] != []


async def test_a_rule_sends_only_through_webhooks_of_whoever_saves_it(world: World) -> None:
    r = await rule_world(world)
    owner, other = await world.user(), await world.user()
    theirs = await hook(world, other)
    with pytest.raises(NotFoundError):
        await notifying(r, owner, theirs)
    mine = await hook(world, owner)
    with pytest.raises(ValidationError, match="twice"):
        await r.personal_rule(
            owner,
            definition("Twice", channel_api(), SendWebhook(mine.id), SendWebhook(mine.id)),
        )


async def test_deleting_the_webhook_disables_its_rules(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    await notifying(r, owner, webhook)
    await world.webhooks.delete(Actor(owner.id), webhook.id)
    (rule,) = await r.rules.list_rules(Actor(owner.id))
    assert not rule.enabled
    assert rule.disabled_reason is not None
    assert rule.disabled_reason.code is ReasonCode.RULE_DISABLED_DELETED


async def test_a_change_rule_sends_once_the_change_is_stored(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    tag = await r.tag("pay")
    await r.personal_rule(
        owner,
        definition("Pay", has_tag(tag.id), SendWebhook(webhook.id), triggers=(Trigger.CHANGE,)),
    )
    document = await r.arrive(owner)
    assert sent(world) == []
    preview = await r.documents.change_metadata(
        Actor(owner.id), document.id, DocumentChanges(tag_ids=frozenset({tag.id})), dry_run=True
    )
    assert preview.rules is not None and [send.webhook_id for send in preview.rules.sends] == [
        webhook.id
    ]
    assert sent(world) == []  # a preview sends nothing
    await r.documents.change_metadata(
        Actor(owner.id), document.id, DocumentChanges(tag_ids=frozenset({tag.id}))
    )
    assert [payload["document_id"] for payload in sent(world)] == [str(document.id)]


async def test_applying_to_existing_documents_sends_per_document(world: World) -> None:
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    tag = await r.tag("old")
    first, second = await r.arrive(owner), await r.arrive(owner)
    rule = await r.personal_rule(
        owner, definition("Backfill", channel_api(), add_tags(tag.id), SendWebhook(webhook.id))
    )
    world.database.jobs.clear()
    preview = await r.applications.preview(Actor(owner.id), rule.id)
    assert {
        item.document.id: [send.webhook_id for send in item.sends] for item in preview.items
    } == {
        first.id: [webhook.id],
        second.id: [webhook.id],
    }
    assert sent(world) == []
    await r.applications.start(
        Actor(owner.id), rule.id, version=1, documents=[first.id, second.id], accept_conflicts=[]
    )
    await builders.drain(r.applications)
    assert sorted(str(payload["document_id"]) for payload in sent(world)) == sorted(
        [str(first.id), str(second.id)]
    )


async def test_an_admin_s_global_rule_sends_for_documents_the_admin_reaches(world: World) -> None:
    r = await rule_world(world)
    webhook = await hook(world, r.admin)
    await r.global_rule(definition("Mine", channel_api(), SendWebhook(webhook.id)))
    document = await r.arrive(r.admin)
    assert document.lane is Lane.GREEN
    assert [payload["document_id"] for payload in sent(world)] == [str(document.id)]


async def test_a_move_whose_rules_change_does_not_fit_sends_nothing(world: World) -> None:
    """As after a change: what is not applied does not send either (SC-02)."""
    r = await rule_world(world)
    owner, other = await world.user(), await world.user()
    shared = await world.spaces.create(Actor(owner.id), "Haushalt")
    await world.spaces.set_member(Actor(owner.id), shared.id, other.id, SpaceRole.EDIT)
    webhook = await hook(world, other)
    too_long = SetTitle("{% for i in (1..501) %}x{% endfor %}")
    await r.space_rule(
        other,
        shared.id,
        definition(
            "Long", channel_api(), too_long, SendWebhook(webhook.id), triggers=(Trigger.INGEST,)
        ),
    )
    document = await r.arrive(owner)
    await r.documents.move(Actor(owner.id), document.id, shared.id)
    assert (await r.stored(document)).title == document.title
    assert sent(world) == []


async def test_rules_that_move_it_back_send_nothing(world: World) -> None:
    """The chain stops where rules would move it back; that space's requests stay (SC-02)."""
    r = await rule_world(world)
    owner, other = await world.user(), await world.user()
    shared = await world.spaces.create(Actor(owner.id), "Haushalt")
    await world.spaces.set_member(Actor(owner.id), shared.id, other.id, SpaceRole.EDIT)
    theirs = await world.personal_space(other)
    webhook = await hook(world, other)
    ingest = (Trigger.INGEST,)
    await r.space_rule(
        other, shared.id, definition("To them", channel_api(), SetSpace(theirs.id), triggers=ingest)
    )
    await r.space_rule(
        other,
        theirs.id,
        definition(
            "Back", channel_api(), SetSpace(shared.id), SendWebhook(webhook.id), triggers=ingest
        ),
    )
    document = await r.arrive(owner)
    change = ChangeRules(
        world.object_store, r.matcher, TEMPLATES, max_text=MAX_TEXT, pipeline_version="test"
    )
    async with world.uow() as uow:
        stored = await uow.documents.get(document.id)
        assert stored is not None
        stored.move_to(shared.id, builders.NOW)  # as a rule applied to it would
        await change.after_arrival(
            uow,
            document=stored,
            source=await world.personal_space(owner),
            prepared=Prepared(),
            definitions={},
            now=builders.NOW,
            by_person=False,
        )
        await uow.documents.update(stored)
        await uow.commit()
    assert (await r.stored(document)).space_id == theirs.id
    assert sent(world) == []


async def test_one_check_tells_whether_a_rule_may_send_or_ask(world: World) -> None:
    """The webhook is there, its owner wrote the rule and reaches the document (SC-07)."""
    r = await rule_world(world)
    owner, other = await world.user(), await world.user()
    webhook = await hook(world, owner)
    mine, theirs = await r.arrive(owner), await r.arrive(other)

    async def check(webhook_id: WebhookId, author: UserId, document: Document) -> object:
        async with world.uow() as uow:
            reason = await refusal(uow, webhook_id, author, "Notify", document)
        return None if reason is None else reason.code

    assert await check(webhook.id, owner.id, mine) is None
    assert await check(WebhookId(new_id()), owner.id, mine) is ReasonCode.RULE_WEBHOOK_GONE
    assert await check(webhook.id, other.id, mine) is ReasonCode.RULE_WEBHOOK_GONE
    assert await check(webhook.id, owner.id, theirs) is ReasonCode.RULE_WEBHOOK_UNREADABLE


async def test_a_rule_whose_change_does_not_fit_waits_once_and_sends_nothing(
    world: World,
) -> None:
    """Confirmed, the rules run again and their change does not fit again: only reported then,
    the document leaves the inbox (SC-11); nothing of the change applied, nothing is sent."""
    r = await rule_world(world)
    owner = await world.user()
    webhook = await hook(world, owner)
    too_long = SetTitle("{% for i in (1..501) %}x{% endfor %}")
    await notifying(r, owner, webhook, too_long)
    document = await r.arrive(owner)
    assert document.lane is Lane.YELLOW
    (entry,) = await r.rule_entries(document, RULES)
    assert [reason.code for reason in entry.result.reasons] == [ReasonCode.RULES_CHANGE_UNFIT]
    pipeline = r.pipeline()
    await pipeline.confirm(Actor(owner.id), document.id, DocumentChanges(), accept_suggestions=True)
    await world.drain(pipeline)
    assert (await r.stored(document)).lane is Lane.GREEN
    latest = (await r.rule_entries(document, RULES))[-1]
    assert latest.result.output[CHANGES_UNFIT] != []
    assert sent(world) == []
