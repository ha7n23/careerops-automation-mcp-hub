import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
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
    "approval_requests, application_events, action_items, job_applications "
    "RESTART IDENTITY CASCADE"
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def postgres_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Provide a clean PostgreSQL session factory for one integration test."""
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        DEFAULT_TEST_DATABASE_URL,
    )

    if database_url.endswith("/careerops"):
        raise RuntimeError(
            "Integration tests must not run against the development database."
        )

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.execute(_TRUNCATE_SQL)

    try:
        yield session_factory
    finally:
        async with engine.begin() as connection:
            await connection.execute(_TRUNCATE_SQL)

        await engine.dispose()
