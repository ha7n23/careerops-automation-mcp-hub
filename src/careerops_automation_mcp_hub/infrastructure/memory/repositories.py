from datetime import datetime
from uuid import UUID

from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)


class InMemoryJobApplicationRepository:
    def __init__(self) -> None:
        self._applications: dict[UUID, JobApplication] = {}

    async def add(self, application: JobApplication) -> None:
        self._applications[application.application_id] = application

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        application = self._applications.get(application_id)

        if application is None or application.user_id != user_id:
            return None

        return application

    async def save(self, application: JobApplication) -> None:
        self._applications[application.application_id] = application

    def all(self) -> tuple[JobApplication, ...]:
        return tuple(self._applications.values())

    async def list_for_user(
        self,
        *,
        user_id: str,
        status: ApplicationStatus | None = None,
    ) -> tuple[JobApplication, ...]:
        applications = [
            application
            for application in self._applications.values()
            if application.user_id == user_id
            and (status is None or application.status is status)
        ]

        return tuple(
            sorted(
                applications,
                key=lambda application: (
                    application.created_at,
                    application.application_id.hex,
                ),
            )
        )


class InMemoryApplicationEventRepository:
    def __init__(self) -> None:
        self._events: list[ApplicationEvent] = []

    async def add(self, event: ApplicationEvent) -> None:
        self._events.append(event)

    def all(self) -> tuple[ApplicationEvent, ...]:
        return tuple(self._events)


class InMemoryActionItemRepository:
    def __init__(self) -> None:
        self._actions: dict[UUID, ActionItem] = {}

    async def add(self, action: ActionItem) -> None:
        self._actions[action.action_id] = action

    async def list_pending(
        self,
        *,
        user_id: str,
        due_before: datetime | None = None,
    ) -> tuple[ActionItem, ...]:
        actions = [
            action
            for action in self._actions.values()
            if action.user_id == user_id
            and action.status is ActionItemStatus.PENDING
            and (
                due_before is None
                or (action.due_at is not None and action.due_at <= due_before)
            )
        ]

        return tuple(
            sorted(
                actions,
                key=lambda action: (
                    action.due_at is None,
                    action.due_at or action.created_at,
                    action.action_id.hex,
                ),
            )
        )

    def all(self) -> tuple[ActionItem, ...]:
        return tuple(self._actions.values())
