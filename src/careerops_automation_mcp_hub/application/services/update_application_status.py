from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.repositories import (
    ApplicationEventRepository,
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class UpdateApplicationStatusCommand:
    user_id: str
    application_id: UUID
    target_status: ApplicationStatus
    actor_id: str
    at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UpdateApplicationStatusResult:
    application: JobApplication
    event: ApplicationEvent


class UpdateApplicationStatusService:
    def __init__(
        self,
        applications: JobApplicationRepository,
        events: ApplicationEventRepository,
    ) -> None:
        self._applications = applications
        self._events = events

    async def execute(
        self,
        command: UpdateApplicationStatusCommand,
    ) -> UpdateApplicationStatusResult:
        application = await self._applications.get(
            user_id=command.user_id,
            application_id=command.application_id,
        )

        if application is None:
            raise ApplicationNotFoundError(command.application_id)

        previous_status = application.status

        application.transition_to(
            command.target_status,
            at=command.at,
        )

        event = ApplicationEvent.create(
            application_id=application.application_id,
            user_id=application.user_id,
            event_type=ApplicationEventType.STATUS_CHANGED,
            actor_id=command.actor_id,
            occurred_at=command.at,
            attributes={
                "previous_status": previous_status.value,
                "new_status": application.status.value,
            },
        )

        await self._applications.save(application)
        await self._events.add(event)

        return UpdateApplicationStatusResult(
            application=application,
            event=event,
        )
