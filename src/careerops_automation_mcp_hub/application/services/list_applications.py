from dataclasses import dataclass

from careerops_automation_mcp_hub.application.ports.repositories import (
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class ListApplicationsQuery:
    user_id: str
    status: ApplicationStatus | None = None


class ListApplicationsService:
    def __init__(
        self,
        applications: JobApplicationRepository,
    ) -> None:
        self._applications = applications

    async def execute(
        self,
        query: ListApplicationsQuery,
    ) -> tuple[JobApplication, ...]:
        return await self._applications.list_for_user(
            user_id=query.user_id,
            status=query.status,
        )
