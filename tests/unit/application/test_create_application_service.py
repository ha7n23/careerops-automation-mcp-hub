from datetime import UTC, datetime

import pytest

from careerops_automation_mcp_hub.application.services.create_application import (
    CreateApplicationCommand,
    CreateApplicationService,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


class FakeJobApplicationRepository:
    def __init__(self) -> None:
        self.applications: list[JobApplication] = []

    async def add(self, application: JobApplication) -> None:
        self.applications.append(application)


class FakeApplicationEventRepository:
    def __init__(self) -> None:
        self.events: list[ApplicationEvent] = []

    async def add(self, event: ApplicationEvent) -> None:
        self.events.append(event)


@pytest.mark.anyio
async def test_create_application_persists_application_and_event() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()
    service = CreateApplicationService(applications, events)

    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    result = await service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            now=now,
        )
    )

    assert result.application.status is ApplicationStatus.SAVED
    assert result.application.company_name == "Monzo"

    assert applications.applications == [result.application]
    assert events.events == [result.event]

    assert result.event.event_type is ApplicationEventType.APPLICATION_CREATED
    assert result.event.application_id == result.application.application_id
    assert result.event.user_id == "USER-001"
    assert result.event.actor_id == "USER-001"
    assert result.event.occurred_at == now


@pytest.mark.anyio
async def test_create_application_uses_domain_normalisation() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()
    service = CreateApplicationService(applications, events)

    result = await service.execute(
        CreateApplicationCommand(
            user_id=" USER-001 ",
            company_name=" Monzo ",
            role_title=" Junior AI Engineer ",
            actor_id="USER-001",
        )
    )

    assert result.application.user_id == "USER-001"
    assert result.application.company_name == "Monzo"
    assert result.application.role_title == "Junior AI Engineer"


@pytest.mark.anyio
async def test_invalid_application_is_not_persisted() -> None:
    applications = FakeJobApplicationRepository()
    events = FakeApplicationEventRepository()
    service = CreateApplicationService(applications, events)

    with pytest.raises(ValueError):
        await service.execute(
            CreateApplicationCommand(
                user_id="USER-001",
                company_name="   ",
                role_title="Junior AI Engineer",
                actor_id="USER-001",
            )
        )

    assert applications.applications == []
    assert events.events == []
