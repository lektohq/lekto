"""The system's resolver, as the adapters that check addresses before connecting use it."""

from lekto.adapters.outbound.http_client.resolver import system_resolver


async def test_the_system_resolver_gives_an_address_as_it_is() -> None:
    """Numeric hosts only: no name server is asked."""
    assert await system_resolver("127.0.0.1") == ["127.0.0.1"]
    assert await system_resolver("::1") == ["::1"]
