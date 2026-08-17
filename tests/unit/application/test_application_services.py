from datetime import UTC, datetime
from uuid import UUID

import pytest

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.services.get_application import (
    GetApplicationQuery,
    GetApplicationService,
)
from careerops_automation_mcp_hub.application.services.update_application_status import (
    UpdateApplicationStatusCommand,
    UpdateApplicationStatusService,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    InvalidApplicationStatusTransition,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


class FakeJobApplicationRepository:
    def __init__(self) -> None:
        self.applications: dict[UUID, JobApplication] = {}
        self.saved: list[JobApplication] = []

    async def add(self, application: JobApplication) -> None:
        self.applications[application.application_id] = application

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        application = self.applications.get(application_id)

        if application is None or application.user_id != user_id:
            return None

        return application

    async def save(self, application: JobApplication) -> None:
        self.applications[application.application_id] = application
        self.saved.append(application)


class FakeApplicationEventRepository:
    def __init__(self) -> None:
        self.events: list[ApplicationEvent] = []

    async def add(self, event: ApplicationEvent) -> None:
        self.events.append(event)


def build_application(
    *,
    user_id: str = "USER-001",
) -> JobApplication:
    return JobApplication.create(
        user_id=user_id,
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )


@pytest.mark.anyio
async def test_get_application_returns_user_scoped_application() -> None:
    repository = FakeJobApplicationRepository()
    application = build_application()
    await repository.add(application)

    service = GetApplicationService(repository)

    result = await service.execute(
        GetApplicationQuery(
            user_id="USER-001",
            application_id=application.application_id,
        )
    )

    assert result is application


@pytest.mark.anyio
async def test_get_application_raises_when_application_is_not_available() -> None:
    repository = FakeJobApplicationRepository()
    application = build_application(user_id="USER-OTHER")
    await repository.add(application)

    service = GetApplicationService(repository)

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            GetApplicationQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )


@pytest.mark.anyio
async def test_update_application_status_persists_change_and_event() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()

    application = build_application()
    await applications.add(application)

    service = UpdateApplicationStatusService(applications, events)

    transitioned_at = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)

    result = await service.execute(
        UpdateApplicationStatusCommand(
            user_id="USER-001",
            application_id=application.application_id,
            target_status=ApplicationStatus.PREPARING,
            actor_id="USER-001",
            at=transitioned_at,
        )
    )

    assert result.application.status is ApplicationStatus.PREPARING
    assert result.application.updated_at == transitioned_at
    assert applications.saved == [result.application]

    assert result.event.event_type is ApplicationEventType.STATUS_CHANGED
    assert dict(result.event.attributes) == {
        "new_status": "preparing",
        "previous_status": "saved",
    }
    assert events.events == [result.event]


@pytest.mark.anyio
async def test_invalid_status_transition_is_not_persisted() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()

    application = build_application()
    await applications.add(application)

    service = UpdateApplicationStatusService(applications, events)

    with pytest.raises(InvalidApplicationStatusTransition):
        await service.execute(
            UpdateApplicationStatusCommand(
                user_id="USER-001",
                application_id=application.application_id,
                target_status=ApplicationStatus.OFFER,
                actor_id="USER-001",
            )
        )

    assert applications.saved == []
    assert events.events == []


@pytest.mark.anyio
async def test_update_cannot_access_another_users_application() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()

    application = build_application(user_id="USER-OTHER")
    await applications.add(application)

    service = UpdateApplicationStatusService(applications, events)

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            UpdateApplicationStatusCommand(
                user_id="USER-001",
                application_id=application.application_id,
                target_status=ApplicationStatus.PREPARING,
                actor_id="USER-001",
            )
        )

    assert applications.saved == []
    assert events.events == []
