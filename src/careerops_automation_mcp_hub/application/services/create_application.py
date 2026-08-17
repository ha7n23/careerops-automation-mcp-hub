from dataclasses import dataclass
from datetime import datetime

from careerops_automation_mcp_hub.application.ports.repositories import (
    ApplicationEventRepository,
    JobApplicationRepository,
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
        applications: JobApplicationRepository,
        events: ApplicationEventRepository,
    ) -> None:
        self._applications = applications
        self._events = events

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

        await self._applications.add(application)
        await self._events.add(event)

        return CreateApplicationResult(
            application=application,
            event=event,
        )
