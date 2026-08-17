from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from careerops_automation_mcp_hub.application.ports.repositories import (
    ActionItemRepository,
    ApplicationEventRepository,
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.database.repositories import (
    SqlAlchemyActionItemRepository,
    SqlAlchemyApplicationEventRepository,
    SqlAlchemyJobApplicationRepository,
)


class SqlAlchemyApplicationUnitOfWork:
    """Transactional application Unit of Work backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

        self.applications: JobApplicationRepository = (
            SqlAlchemyJobApplicationRepository(session)
        )
        self.events: ApplicationEventRepository = SqlAlchemyApplicationEventRepository(
            session
        )
        self.actions: ActionItemRepository = SqlAlchemyActionItemRepository(session)

        self._committed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None or not self._committed:
                await self.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        await self._session.rollback()


class SqlAlchemyApplicationUnitOfWorkFactory:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyApplicationUnitOfWork:
        return SqlAlchemyApplicationUnitOfWork(self._session_factory())
