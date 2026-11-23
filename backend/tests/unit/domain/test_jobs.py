"""Jobs: how a failed attempt is repeated (`RetryPolicy`)."""

from datetime import timedelta

from lekto.core.domain.jobs import RetryPolicy
from tests.builders import NOW


def test_retry_policy() -> None:
    policy = RetryPolicy(max_attempts=3, delay=timedelta(seconds=10))
    assert policy.next_run(1, NOW) == NOW + timedelta(seconds=10)
    assert policy.next_run(2, NOW) == NOW + timedelta(seconds=20)
    assert policy.next_run(3, NOW) is None
    capped = RetryPolicy(
        max_attempts=10, delay=timedelta(seconds=10), max_delay=timedelta(seconds=30)
    )
    assert [capped.next_run(n, NOW) for n in (2, 3, 4)] == [
        NOW + timedelta(seconds=20),
        NOW + timedelta(seconds=30),
        NOW + timedelta(seconds=30),
    ]
