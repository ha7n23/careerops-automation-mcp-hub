from datetime import UTC, datetime

import pytest

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyConflictError,
)
from careerops_automation_mcp_hub.application.services.create_application import (
    CreateApplicationCommand,
    CreateApplicationService,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.unit_of_work import (
    InMemoryApplicationUnitOfWorkFactory,
)


def build_service() -> tuple[
    CreateApplicationService,
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

    service = CreateApplicationService(unit_of_work_factory)

    return service, applications, events, unit_of_work_factory


@pytest.mark.anyio
async def test_create_application_persists_application_and_event() -> None:
    service, applications, events, unit_of_work_factory = build_service()

    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    result = await service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="create-persist-1",
            now=now,
        )
    )

    assert result.application.status is ApplicationStatus.SAVED
    assert result.application.company_name == "Monzo"

    assert applications.all() == (result.application,)
    assert events.all() == (result.event,)

    assert result.event.event_type is ApplicationEventType.APPLICATION_CREATED
    assert result.event.application_id == result.application.application_id
    assert result.event.user_id == "USER-001"
    assert result.event.actor_id == "USER-001"
    assert result.event.occurred_at == now

    assert unit_of_work_factory.created[-1].committed is True
    assert unit_of_work_factory.created[-1].rolled_back is False


@pytest.mark.anyio
async def test_create_application_uses_domain_normalisation() -> None:
    service, _, _, unit_of_work_factory = build_service()

    result = await service.execute(
        CreateApplicationCommand(
            user_id=" USER-001 ",
            company_name=" Monzo ",
            role_title=" Junior AI Engineer ",
            actor_id="USER-001",
            idempotency_key="create-normalisation-1",
        )
    )

    assert result.application.user_id == "USER-001"
    assert result.application.company_name == "Monzo"
    assert result.application.role_title == "Junior AI Engineer"

    assert unit_of_work_factory.created[-1].committed is True


@pytest.mark.anyio
async def test_invalid_application_is_not_persisted() -> None:
    service, applications, events, unit_of_work_factory = build_service()

    with pytest.raises(ValueError):
        await service.execute(
            CreateApplicationCommand(
                user_id="USER-001",
                company_name="   ",
                role_title="Junior AI Engineer",
                actor_id="USER-001",
                idempotency_key="create-invalid-1",
            )
        )

    assert applications.all() == ()
    assert events.all() == ()

    # Domain validation fails before a transaction is opened.
    assert unit_of_work_factory.created == []


@pytest.mark.anyio
async def test_create_application_replays_same_idempotency_key() -> None:
    service, applications, events, _ = build_service()

    command = CreateApplicationCommand(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
        actor_id="USER-001",
        idempotency_key="workflow-123",
    )

    first = await service.execute(command)
    replay = await service.execute(command)

    assert replay.application.application_id == (first.application.application_id)
    assert replay.event.event_id == first.event.event_id

    assert applications.all() == (first.application,)
    assert events.all() == (first.event,)


@pytest.mark.anyio
async def test_create_application_rejects_key_reuse_for_different_request() -> None:
    service, applications, events, _ = build_service()

    first = await service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="workflow-123",
        )
    )

    with pytest.raises(
        IdempotencyConflictError,
        match="already used for a different request",
    ):
        await service.execute(
            CreateApplicationCommand(
                user_id="USER-001",
                company_name="Monzo",
                role_title="AI Engineer",
                actor_id="USER-001",
                idempotency_key="workflow-123",
            )
        )

    assert applications.all() == (first.application,)
    assert events.all() == (first.event,)
