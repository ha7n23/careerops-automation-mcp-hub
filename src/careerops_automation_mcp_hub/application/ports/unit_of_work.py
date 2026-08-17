from types import TracebackType
from typing import Protocol, Self

from careerops_automation_mcp_hub.application.ports.repositories import (
    ActionItemRepository,
    ApplicationEventRepository,
    JobApplicationRepository,
)


class ApplicationUnitOfWork(Protocol):
    applications: JobApplicationRepository
    events: ApplicationEventRepository
    actions: ActionItemRepository

    async def __aenter__(self) -> Self:
        """Enter the transaction boundary."""
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Rollback automatically when the operation fails."""
        ...

    async def commit(self) -> None:
        """Commit all changes in the unit of work."""
        ...

    async def rollback(self) -> None:
        """Discard all uncommitted changes."""
        ...


class ApplicationUnitOfWorkFactory(Protocol):
    def __call__(self) -> ApplicationUnitOfWork:
        """Create a fresh unit of work."""
        ...
