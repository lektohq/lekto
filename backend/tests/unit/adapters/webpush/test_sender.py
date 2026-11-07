"""The web push sender: RFC 8291's example, the VAPID signature, what the push service answers."""

import base64
import json

import httpx2
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from lekto.adapters.outbound.webpush.sender import (
    WebPushSender,
    b64url,
    encrypt,
    new_private_key,
    unb64url,
    vapid_header,
)
from lekto.core.domain.ids import UserId, new_id
from lekto.core.domain.push import PushKind, PushMessage
from lekto.core.ports.push import PushOutcome, PushSender
from tests.contracts.push import PushSenderContract, a_device

SUBJECT = "mailto:admin@example.org"


def answering(status: int, seen: list[httpx2.Request] | None = None) -> httpx2.MockTransport:
    def handle(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        return httpx2.Response(status)

    return httpx2.MockTransport(handle)


class TestWebPushSender(PushSenderContract):
    @pytest.fixture
    def sender(self) -> PushSender:
        return WebPushSender(
            private_key=new_private_key(), subject=SUBJECT, transport=answering(201)
        )


def test_the_encryption_is_rfc_8291s_example() -> None:
    """RFC 8291, appendix A: the same keys, salt and text give the same body."""
    sender = ec.derive_private_key(
        int.from_bytes(unb64url("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"),
        ec.SECP256R1(),
    )
    body = encrypt(
        b"When I grow up, I want to be a watermelon",
        unb64url(
            "BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"
        ),
        unb64url("BTBZMqHH6r4Tts7J_aSIgg"),
        salt=unb64url("DGv6ra1nlYgDCS1FRnbzlw"),
        sender=sender,
    )
    assert b64url(body) == (
        "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS"
        "6TlzAC8wEqKK6PBru3jl7A_yl95bQpu6cVPTpK4Mqgkf1CXztLVBSt2Ks3oZwbuwXPXLWyouBWLVWGNWQexSgSxsj_Q"
        "ulcy4a-fN"
    )


def test_the_vapid_token_is_signed_for_the_push_services_origin() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    header = vapid_header("https://web.push.apple.com/QGx1?x=1", key, SUBJECT, now=1_800_000_000)
    token, public = header.removeprefix("vapid t=").split(", k=")
    head, body, signature = token.split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    assert claims == {"aud": "https://web.push.apple.com", "exp": 1_800_043_200, "sub": SUBJECT}
    raw = unb64url(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    verifier = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), unb64url(public))
    verifier.verify(der, f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))
    with pytest.raises(InvalidSignature):
        verifier.verify(der, f"{head}.{body}x".encode(), ec.ECDSA(hashes.SHA256()))


async def test_it_posts_an_encrypted_body_with_its_headers() -> None:
    seen: list[httpx2.Request] = []
    sender = WebPushSender(
        private_key=new_private_key(), subject=SUBJECT, transport=answering(201, seen)
    )
    message = PushMessage(
        kind=PushKind.WAITING, params={"count": 3}, topic="waiting", ttl_seconds=60
    )
    result = await sender.send(a_device(UserId(new_id())), message)
    assert result.outcome is PushOutcome.DELIVERED
    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == "https://web.push.apple.com/QGx1"
    assert request.headers["content-encoding"] == "aes128gcm"
    assert (request.headers["ttl"], request.headers["topic"]) == ("60", "waiting")
    assert request.headers["authorization"].startswith("vapid t=")
    assert b'"count"' not in request.content  # encrypted: nothing of it to read on the way


@pytest.mark.parametrize(
    ("status", "outcome"),
    [
        (201, PushOutcome.DELIVERED),
        (404, PushOutcome.GONE),
        (410, PushOutcome.GONE),
        (413, PushOutcome.FAILED),
        (429, PushOutcome.FAILED),
        (503, PushOutcome.FAILED),
    ],
)
async def test_the_answer_decides_the_outcome(status: int, outcome: PushOutcome) -> None:
    sender = WebPushSender(
        private_key=new_private_key(), subject=SUBJECT, transport=answering(status)
    )
    result = await sender.send(a_device(UserId(new_id())), PushMessage(kind=PushKind.TEST))
    assert (result.outcome, result.status_code) == (outcome, status)


async def test_a_failure_on_the_way_does_not_name_the_address() -> None:
    def broken(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    sender = WebPushSender(
        private_key=new_private_key(), subject=SUBJECT, transport=httpx2.MockTransport(broken)
    )
    result = await sender.send(a_device(UserId(new_id())), PushMessage(kind=PushKind.TEST))
    assert result.outcome is PushOutcome.FAILED and result.status_code is None
    assert result.error and "QGx1" not in result.error and "apple" not in result.error


def test_a_key_must_be_32_bytes() -> None:
    with pytest.raises(ValueError):
        WebPushSender(private_key="c2hvcnQ", subject=SUBJECT)
