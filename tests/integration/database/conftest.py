import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)

DEFAULT_TEST_DATABASE_URL = (
    "postgresql+asyncpg://careerops:careerops@localhost:5433/careerops_test"
)

_TRUNCATE_SQL = text(
    "TRUNCATE TABLE "
    "idempotency_records, approval_requests, application_events, "
    "action_items, job_applications "
    "RESTART IDENTITY CASCADE"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def postgres_database_url() -> str:
    """Return the explicitly isolated PostgreSQL integration-test URL."""
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        DEFAULT_TEST_DATABASE_URL,
    )

    database_name = make_url(database_url).database

    if database_name != "careerops_test":
        raise RuntimeError(
            "Integration tests may run only against the 'careerops_test' database."
        )

    return database_url


@pytest.fixture
async def postgres_session_factory(
    postgres_database_url: str,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Provide a clean PostgreSQL session factory for one integration test."""
    engine = create_database_engine(postgres_database_url)
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.execute(_TRUNCATE_SQL)

    try:
        yield session_factory
    finally:
        async with engine.begin() as connection:
            await connection.execute(_TRUNCATE_SQL)

        await engine.dispose()
