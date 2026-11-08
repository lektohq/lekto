"""`/push`: notifications on the caller's devices (web push)."""

from uuid import UUID

from fastapi import APIRouter, Response

from lekto.adapters.inbound.rest.auth import PROTECTED, CurrentUser
from lekto.adapters.inbound.rest.context import Context
from lekto.adapters.inbound.rest.problems import problem_responses
from lekto.adapters.inbound.rest.schemas.push import (
    PushDeviceIn,
    PushDeviceOut,
    PushPreferencesBody,
    PushSettingsOut,
    PushTestOut,
)
from lekto.core.domain.ids import PushDeviceId

router = APIRouter(prefix="/push", tags=["push"], dependencies=PROTECTED)

WHO = "Only its owner sees a device; other users' devices are not found (404)."
OFF = "409 `push_off`: the server sends no notifications (no VAPID key)."


@router.get(
    "",
    summary="Notifications on this server",
    description="Whether the server sends notifications, and the key browsers subscribe with.",
    response_model=PushSettingsOut,
    responses=problem_responses(401),
)
async def push_settings(context: Context) -> PushSettingsOut:
    return PushSettingsOut(enabled=context.push.enabled, public_key=context.push.public_key)


@router.get(
    "/devices",
    summary="List the caller's devices",
    description="The devices the caller receives notifications on, oldest first.",
    response_model=list[PushDeviceOut],
    responses=problem_responses(401),
)
async def list_devices(user: CurrentUser, context: Context) -> list[PushDeviceOut]:
    return [PushDeviceOut.of(device) for device in await context.push.devices(user)]


@router.post(
    "/devices",
    status_code=201,
    summary="Receive notifications on a device",
    description=(
        "A browser's subscription (`PushSubscription`): its address at the push service and its "
        "keys. The address must be one of a known push service (Apple, Google, Mozilla, "
        "Microsoft; 422 `push_endpoint_refused`), the keys valid (422 `push_keys_invalid`). The "
        "same address again replaces the device, also one another user subscribed in that "
        "browser before. 409 `push_devices_limit`: the caller has 20 devices. " + OFF
    ),
    response_model=PushDeviceOut,
    responses=problem_responses(401, 409, 422),
)
async def register_device(body: PushDeviceIn, user: CurrentUser, context: Context) -> PushDeviceOut:
    device = await context.push.register(
        user,
        endpoint=body.endpoint,
        p256dh=body.keys.p256dh,
        auth=body.keys.auth,
        name=body.name,
        locale=body.locale,
    )
    return PushDeviceOut.of(device)


@router.delete(
    "/devices/{id}",
    status_code=204,
    summary="Receive no notifications on a device",
    description=WHO,
    responses=problem_responses(401, 404, 422),
)
async def remove_device(id: UUID, user: CurrentUser, context: Context) -> Response:
    await context.push.remove(user, PushDeviceId(id))
    return Response(status_code=204)


@router.post(
    "/devices/{id}/test",
    summary="Send a device a test notification",
    description=f"{WHO} A device the push service no longer knows is forgotten (`gone`). {OFF}",
    response_model=PushTestOut,
    responses=problem_responses(401, 404, 409, 422),
)
async def test_device(id: UUID, user: CurrentUser, context: Context) -> PushTestOut:
    return PushTestOut.of(await context.push.test(user, PushDeviceId(id)))


@router.get(
    "/preferences",
    summary="What the caller is told about",
    description="Every kind is on and titles are named until the caller changes it.",
    response_model=PushPreferencesBody,
    responses=problem_responses(401),
)
async def get_preferences(user: CurrentUser, context: Context) -> PushPreferencesBody:
    return PushPreferencesBody.of(await context.push.preferences(user))


@router.put(
    "/preferences",
    summary="Choose what the caller is told about",
    description=(
        "A notification of a kind left out is not sent; documents waiting meanwhile are named "
        "in the next notification once `waiting` is on again."
    ),
    response_model=PushPreferencesBody,
    responses=problem_responses(401, 409, 422),
)
async def set_preferences(
    body: PushPreferencesBody, user: CurrentUser, context: Context
) -> PushPreferencesBody:
    preferences = await context.push.set_preferences(
        user, kinds=body.kinds_domain(), titles=body.titles
    )
    return PushPreferencesBody.of(preferences)
