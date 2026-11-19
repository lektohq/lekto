"""The S3 adapter's limits, without a store (the store itself in the integration tests)."""

from datetime import timedelta

from lekto.adapters.outbound.http_client import CONNECT_TIMEOUT
from lekto.adapters.outbound.s3.object_store import ATTEMPTS, READ_TIMEOUT, S3ObjectStore
from lekto.core.domain.jobs import WORK_LEASE_MARGIN


def test_a_store_that_does_not_answer_ends_within_the_margin_of_a_lease() -> None:
    """Its own limits, not botocore's 60 s each, three times over (AD-10)."""
    store = S3ObjectStore(
        endpoint_url="http://127.128.129.23:3900",
        region="garage",
        bucket="lekto",
        access_key_id="id",
        secret_access_key="secret",
        path_style=True,
    )
    config = store._config
    assert (config.connect_timeout, config.read_timeout) == (CONNECT_TIMEOUT, READ_TIMEOUT)
    assert timedelta(seconds=ATTEMPTS * (CONNECT_TIMEOUT + READ_TIMEOUT)) < WORK_LEASE_MARGIN
