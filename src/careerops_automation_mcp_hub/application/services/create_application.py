from dataclasses import dataclass
from datetime import datetime

from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class CreateApplicationCommand:
    user_id: str
    company_name: str
    role_title: str
    actor_id: str
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class CreateApplicationResult:
    application: JobApplication
    event: ApplicationEvent


class CreateApplicationService:
    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        command: CreateApplicationCommand,
    ) -> CreateApplicationResult:
        application = JobApplication.create(
            user_id=command.user_id,
            company_name=command.company_name,
            role_title=command.role_title,
            now=command.now,
        )

        event = ApplicationEvent.create(
            application_id=application.application_id,
            user_id=application.user_id,
            event_type=ApplicationEventType.APPLICATION_CREATED,
            actor_id=command.actor_id,
            occurred_at=command.now,
        )

        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.applications.add(application)
            await unit_of_work.events.add(event)
            await unit_of_work.commit()

        return CreateApplicationResult(
            application=application,
            event=event,
        )
