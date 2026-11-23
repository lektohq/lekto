"""The fixtures of the SQL adapter's tests that both databases share, given a `database`
fixture (`tests/unit/adapters/sql`: SQLite; `tests/integration/adapters/sql`: Postgres);
each conftest imports them."""

import pytest

from lekto.adapters.outbound.sql import Database, SqlEventBus, SqlUnitOfWorkFactory, SqlWakeup
from lekto.core.domain.jobs import RetryPolicy
from lekto.core.ports.clock import Clock
from lekto.core.ports.event_bus import EventBus
from lekto.core.ports.unit_of_work import UnitOfWorkFactory
from tests import builders
from tests.contracts.event_bus import EventBusFactory
from tests.contracts.wakeup import WakeupFactory


@pytest.fixture
def uow_factory(database: Database) -> UnitOfWorkFactory:
    return SqlUnitOfWorkFactory(database)


@pytest.fixture
def event_bus_factory(database: Database) -> EventBusFactory:
    def create(
        *, clock: Clock | None = None, retry: RetryPolicy = builders.EVENT_RETRY
    ) -> EventBus:
        return SqlEventBus(database, clock=clock, retry=retry)

    return create


@pytest.fixture
def wakeup_factory(database: Database) -> WakeupFactory:
    return lambda: SqlWakeup(database)
