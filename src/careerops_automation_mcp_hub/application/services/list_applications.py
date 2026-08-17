from dataclasses import dataclass

from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
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
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        query: ListApplicationsQuery,
    ) -> tuple[JobApplication, ...]:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.applications.list_for_user(
                user_id=query.user_id,
                status=query.status,
            )
