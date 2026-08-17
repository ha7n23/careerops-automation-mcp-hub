from types import TracebackType
from typing import Self

from careerops_automation_mcp_hub.application.ports.repositories import (
    ActionItemRepository,
    ApplicationEventRepository,
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)


class InMemoryApplicationUnitOfWork:
    """Development/test unit of work over shared in-memory repositories.

    This adapter provides the same orchestration boundary as the production
    unit of work. True database transaction rollback is provided by the
    PostgreSQL implementation.
    """

    def __init__(
        self,
        applications: InMemoryJobApplicationRepository,
        events: InMemoryApplicationEventRepository,
        actions: InMemoryActionItemRepository,
    ) -> None:
        self.applications: JobApplicationRepository = applications
        self.events: ApplicationEventRepository = events
        self.actions: ActionItemRepository = actions

        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class InMemoryApplicationUnitOfWorkFactory:
    def __init__(
        self,
        applications: InMemoryJobApplicationRepository,
        events: InMemoryApplicationEventRepository,
        actions: InMemoryActionItemRepository,
    ) -> None:
        self._applications = applications
        self._events = events
        self._actions = actions
        self.created: list[InMemoryApplicationUnitOfWork] = []

    def __call__(self) -> InMemoryApplicationUnitOfWork:
        unit_of_work = InMemoryApplicationUnitOfWork(
            applications=self._applications,
            events=self._events,
            actions=self._actions,
        )
        self.created.append(unit_of_work)
        return unit_of_work
