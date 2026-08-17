from datetime import UTC, datetime

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
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    InvalidApplicationStatusTransition,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.unit_of_work import (
    InMemoryApplicationUnitOfWorkFactory,
)


def build_application(
    *,
    user_id: str = "USER-001",
) -> JobApplication:
    return JobApplication.create(
        user_id=user_id,
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )


def build_update_service() -> tuple[
    UpdateApplicationStatusService,
    InMemoryJobApplicationRepository,
    InMemoryApplicationEventRepository,
    InMemoryApplicationUnitOfWorkFactory,
]:
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    service = UpdateApplicationStatusService(unit_of_work_factory)

    return service, applications, events, unit_of_work_factory


@pytest.mark.anyio
async def test_get_application_returns_user_scoped_application() -> None:
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    application = build_application()
    await applications.add(application)

    service = GetApplicationService(unit_of_work_factory)

    result = await service.execute(
        GetApplicationQuery(
            user_id="USER-001",
            application_id=application.application_id,
        )
    )

    assert result is application


@pytest.mark.anyio
async def test_get_application_raises_when_application_is_not_available() -> None:
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    application = build_application(user_id="USER-OTHER")
    await applications.add(application)

    service = GetApplicationService(unit_of_work_factory)

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            GetApplicationQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )


@pytest.mark.anyio
async def test_update_application_status_persists_change_and_event() -> None:
    service, applications, events, unit_of_work_factory = build_update_service()

    application = build_application()
    await applications.add(application)

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

    stored = await applications.get(
        user_id="USER-001",
        application_id=application.application_id,
    )

    assert stored is result.application

    assert result.event.event_type is ApplicationEventType.STATUS_CHANGED
    assert dict(result.event.attributes) == {
        "new_status": "preparing",
        "previous_status": "saved",
    }
    assert events.all() == (result.event,)

    assert unit_of_work_factory.created[-1].committed is True
    assert unit_of_work_factory.created[-1].rolled_back is False


@pytest.mark.anyio
async def test_invalid_status_transition_is_not_persisted() -> None:
    service, applications, events, unit_of_work_factory = build_update_service()

    application = build_application()
    await applications.add(application)

    with pytest.raises(InvalidApplicationStatusTransition):
        await service.execute(
            UpdateApplicationStatusCommand(
                user_id="USER-001",
                application_id=application.application_id,
                target_status=ApplicationStatus.OFFER,
                actor_id="USER-001",
            )
        )

    stored = await applications.get(
        user_id="USER-001",
        application_id=application.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationStatus.SAVED
    assert events.all() == ()

    assert unit_of_work_factory.created[-1].committed is False
    assert unit_of_work_factory.created[-1].rolled_back is True


@pytest.mark.anyio
async def test_update_cannot_access_another_users_application() -> None:
    service, applications, events, unit_of_work_factory = build_update_service()

    application = build_application(user_id="USER-OTHER")
    await applications.add(application)

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            UpdateApplicationStatusCommand(
                user_id="USER-001",
                application_id=application.application_id,
                target_status=ApplicationStatus.PREPARING,
                actor_id="USER-001",
            )
        )

    assert application.status is ApplicationStatus.SAVED
    assert events.all() == ()

    assert unit_of_work_factory.created[-1].committed is False
    assert unit_of_work_factory.created[-1].rolled_back is True
