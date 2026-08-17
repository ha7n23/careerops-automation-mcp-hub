from dataclasses import dataclass
from uuid import UUID

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class GetApplicationQuery:
    user_id: str
    application_id: UUID


class GetApplicationService:
    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        query: GetApplicationQuery,
    ) -> JobApplication:
        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=query.user_id,
                application_id=query.application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(query.application_id)

            return application
