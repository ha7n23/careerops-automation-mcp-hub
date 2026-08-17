from dataclasses import dataclass
from uuid import UUID

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.repositories import (
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class GetApplicationQuery:
    user_id: str
    application_id: UUID


class GetApplicationService:
    def __init__(
        self,
        applications: JobApplicationRepository,
    ) -> None:
        self._applications = applications

    async def execute(
        self,
        query: GetApplicationQuery,
    ) -> JobApplication:
        application = await self._applications.get(
            user_id=query.user_id,
            application_id=query.application_id,
        )

        if application is None:
            raise ApplicationNotFoundError(query.application_id)

        return application
