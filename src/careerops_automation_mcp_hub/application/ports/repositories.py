from typing import Protocol
from uuid import UUID

from careerops_automation_mcp_hub.domain.application_event import ApplicationEvent
from careerops_automation_mcp_hub.domain.job_application import JobApplication


class JobApplicationRepository(Protocol):
    async def add(self, application: JobApplication) -> None:
        """Persist a new job application."""

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        """Return a user-scoped application if it exists."""

    async def save(self, application: JobApplication) -> None:
        """Persist changes to an existing application."""


class ApplicationEventRepository(Protocol):
    async def add(self, event: ApplicationEvent) -> None:
        """Persist an application event."""
