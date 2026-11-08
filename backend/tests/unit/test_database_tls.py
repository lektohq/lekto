"""`LEKTO_DB_SSLMODE` and `LEKTO_DB_SSLROOTCERT` become asyncpg's `ssl` as libpq's modes mean."""

import datetime
import ssl
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from lekto.composition.database import tls_of


def authority(path: Path) -> Path:
    """A self-signed root certificate, as a database of one's own authority has."""
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Example Root")])
    now = datetime.datetime.now(datetime.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return path


def test_unset_leaves_the_drivers_default() -> None:
    assert tls_of(None, None) is None


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("disable", False), ("allow", "allow"), ("prefer", "prefer"), ("require", "require")],
)
def test_the_modes_that_check_no_certificate(mode: str, expected: object) -> None:
    assert tls_of(mode, None) == expected


def test_verify_full_checks_the_certificate_and_the_host() -> None:
    context = tls_of("verify-full", None)
    assert isinstance(context, ssl.SSLContext)
    assert (context.verify_mode, context.check_hostname) == (ssl.CERT_REQUIRED, True)


def test_verify_ca_checks_the_certificate_only(tmp_path: Path) -> None:
    context = tls_of("verify-ca", authority(tmp_path / "root.crt"))
    assert isinstance(context, ssl.SSLContext)
    assert (context.verify_mode, context.check_hostname) == (ssl.CERT_REQUIRED, False)
    assert [entry["subject"] for entry in context.get_ca_certs()] == [
        ((("commonName", "Example Root"),),)
    ]
