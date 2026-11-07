"""Sends web push messages (RFC 8030) over httpx2.

- **Encryption** (RFC 8291, `aes128gcm` of RFC 8188): a new P-256 key pair and salt per message;
  ECDH with the browser's key, HKDF with its auth secret, one record. Only the browser can read
  the message; its push service cannot.
- **VAPID** (RFC 8292): a JWT (ES256) for the push service's origin, valid 12 hours, signed with
  Lekto's private key, with the subject (`mailto:` or `https:`) the push service may contact.
- One POST, no redirects, no proxy settings from the environment, certificates verified. The
  device's address stays out of errors and the log: whoever has it may send to the device's push
  service (it still needs Lekto's key to be accepted).
"""

import asyncio
import base64
import json
import logging
import os
import time
from urllib.parse import urlsplit

import httpx2
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from lekto.adapters.outbound.http_client import CONNECT_TIMEOUT, describe_failure
from lekto.core.domain.push import PushDevice, PushMessage
from lekto.core.ports.push import PushOutcome, PushResult

log = logging.getLogger(__name__)

RECORD_SIZE = 4096
JWT_LIFETIME = 12 * 60 * 60
TIMEOUT = 10.0


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def private_key_of(text: str) -> ec.EllipticCurvePrivateKey:
    """Lekto's VAPID key from its 32 bytes, base64url (`lekto vapid-key` writes one). Raises
    ValueError for anything else."""
    raw = unb64url(text.strip())
    if len(raw) != 32:
        raise ValueError("a VAPID private key is 32 bytes, base64url")
    return ec.derive_private_key(int.from_bytes(raw, "big"), ec.SECP256R1())


def new_private_key() -> str:
    """A new VAPID private key, base64url."""
    key = ec.generate_private_key(ec.SECP256R1())
    return b64url(key.private_numbers().private_value.to_bytes(32, "big"))


def public_bytes(key: ec.EllipticCurvePrivateKey | ec.EllipticCurvePublicKey) -> bytes:
    public = key.public_key() if isinstance(key, ec.EllipticCurvePrivateKey) else key
    return public.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )


def _hkdf(salt: bytes, ikm: bytes, info: bytes, length: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


def encrypt(
    plaintext: bytes,
    receiver_public: bytes,
    auth_secret: bytes,
    *,
    salt: bytes | None = None,
    sender: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """The body of a push message for a browser (RFC 8291, one `aes128gcm` record). `salt` and
    `sender` (the one-time key) come new each time unless a test names them."""
    salt = os.urandom(16) if salt is None else salt
    sender = ec.generate_private_key(ec.SECP256R1()) if sender is None else sender
    sender_public = public_bytes(sender)
    receiver = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receiver_public)
    shared = sender.exchange(ec.ECDH(), receiver)
    ikm = _hkdf(auth_secret, shared, b"WebPush: info\x00" + receiver_public + sender_public, 32)
    key = _hkdf(salt, ikm, b"Content-Encoding: aes128gcm\x00", 16)
    nonce = _hkdf(salt, ikm, b"Content-Encoding: nonce\x00", 12)
    # One record, the last: the delimiter 0x02 after the content, no padding.
    record = AESGCM(key).encrypt(nonce, plaintext + b"\x02", None)
    header = salt + RECORD_SIZE.to_bytes(4, "big") + bytes([len(sender_public)]) + sender_public
    return header + record


def vapid_header(endpoint: str, key: ec.EllipticCurvePrivateKey, subject: str, now: float) -> str:
    """`Authorization: vapid t=<JWT>, k=<public key>` for the push service of `endpoint`."""
    parts = urlsplit(endpoint)
    claims = {
        "aud": f"{parts.scheme}://{parts.netloc}",
        "exp": int(now) + JWT_LIFETIME,
        "sub": subject,
    }
    head = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    body = b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{head}.{body}".encode("ascii")
    r, s = decode_dss_signature(key.sign(signing_input, ec.ECDSA(hashes.SHA256())))
    signature = b64url(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
    return f"vapid t={head}.{body}.{signature}, k={b64url(public_bytes(key))}"


class WebPushSender:
    def __init__(
        self,
        *,
        private_key: str,
        subject: str,
        timeout: float = TIMEOUT,
        user_agent: str = "Lekto",
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        """`transport` replaces the network in tests."""
        self._key = private_key_of(private_key)
        self._subject = subject
        self._timeout = timeout
        self._user_agent = user_agent
        self._transport = transport

    @property
    def public_key(self) -> str:
        return b64url(public_bytes(self._key))

    async def send(self, device: PushDevice, message: PushMessage) -> PushResult:
        payload = json.dumps(message.payload(device.locale), separators=(",", ":")).encode()
        headers = {
            "User-Agent": self._user_agent,
            "Authorization": vapid_header(device.endpoint, self._key, self._subject, time.time()),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "TTL": str(message.ttl_seconds),
            "Urgency": message.urgency,
        }
        if message.topic:
            headers["Topic"] = message.topic
        status: int | None = None
        error: str | None = None
        try:
            body = encrypt(payload, device.public_key, device.auth_secret)
            async with asyncio.timeout(self._timeout):
                async with httpx2.AsyncClient(
                    transport=self._transport,
                    follow_redirects=False,
                    trust_env=False,
                    timeout=httpx2.Timeout(
                        self._timeout, connect=min(CONNECT_TIMEOUT, self._timeout)
                    ),
                ) as client:
                    response = await client.post(device.endpoint, content=body, headers=headers)
                    status = response.status_code
        except (TimeoutError, httpx2.TimeoutException):
            error = f"no answer within {self._timeout:g} seconds"
        except httpx2.HTTPError as failure:
            error = describe_failure(failure)
        except (httpx2.InvalidURL, ValueError, OSError) as failure:
            error = f"cannot send: {type(failure).__name__}"
        if status is not None and 200 <= status < 300:
            return PushResult(outcome=PushOutcome.DELIVERED, status_code=status)
        if status in (404, 410):
            return PushResult(outcome=PushOutcome.GONE, status_code=status)
        error = error or f"the push service answered {status}"
        log.info("push message not delivered", extra={"error": error, "status": status})
        return PushResult(outcome=PushOutcome.FAILED, status_code=status, error=error)
