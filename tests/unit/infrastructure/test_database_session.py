from sqlalchemy.ext.asyncio import AsyncSession

from careerops_automation_mcp_hub.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)


def test_create_database_engine_uses_async_driver() -> None:
    engine = create_database_engine(
        "postgresql+asyncpg://user:password@localhost:5432/careerops"
    )

    try:
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        # No connection is opened by constructing the engine.
        pass


def test_create_session_factory_produces_async_sessions() -> None:
    engine = create_database_engine(
        "postgresql+asyncpg://user:password@localhost:5432/careerops"
    )
    session_factory = create_session_factory(engine)

    session = session_factory()

    try:
        assert isinstance(session, AsyncSession)
    finally:
        # The session has not opened a DB connection in this test.
        pass
