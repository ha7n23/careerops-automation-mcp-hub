from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
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
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        command: UpdateApplicationStatusCommand,
    ) -> UpdateApplicationStatusResult:
        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
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

            await unit_of_work.applications.save(application)
            await unit_of_work.events.add(event)
            await unit_of_work.commit()

        return UpdateApplicationStatusResult(
            application=application,
            event=event,
        )
