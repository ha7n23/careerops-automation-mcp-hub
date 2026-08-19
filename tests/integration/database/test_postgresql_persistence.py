from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.services.create_application import (
    CreateApplicationCommand,
    CreateApplicationService,
)
from careerops_automation_mcp_hub.application.services.get_application import (
    GetApplicationQuery,
    GetApplicationService,
)
from careerops_automation_mcp_hub.application.services.get_pending_actions import (
    GetPendingActionsQuery,
    GetPendingActionsService,
)
from careerops_automation_mcp_hub.application.services.list_applications import (
    ListApplicationsQuery,
    ListApplicationsService,
)
from careerops_automation_mcp_hub.application.services.update_application_status import (
    UpdateApplicationStatusCommand,
    UpdateApplicationStatusService,
)
from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ApplicationEventRecord,
    JobApplicationRecord,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)


@pytest.mark.anyio
async def test_create_and_get_application_round_trip(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    get_service = GetApplicationService(unit_of_work_factory)

    created = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="round-trip-create-1",
        )
    )

    loaded = await get_service.execute(
        GetApplicationQuery(
            user_id="USER-001",
            application_id=created.application.application_id,
        )
    )

    assert loaded.application_id == created.application.application_id
    assert loaded.company_name == "Monzo"
    assert loaded.role_title == "Junior AI Engineer"
    assert loaded.status is ApplicationStatus.SAVED

    async with postgres_session_factory() as session:
        event_count = await session.scalar(
            select(func.count()).select_from(ApplicationEventRecord)
        )

    assert event_count == 1


@pytest.mark.anyio
async def test_application_reads_are_user_scoped(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    get_service = GetApplicationService(unit_of_work_factory)

    created = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Revolut",
            role_title="AI Engineer",
            actor_id="USER-001",
            idempotency_key="scoped-read-create-1",
        )
    )

    with pytest.raises(ApplicationNotFoundError):
        await get_service.execute(
            GetApplicationQuery(
                user_id="USER-OTHER",
                application_id=created.application.application_id,
            )
        )


@pytest.mark.anyio
async def test_status_update_persists_application_and_event(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    update_service = UpdateApplicationStatusService(unit_of_work_factory)
    get_service = GetApplicationService(unit_of_work_factory)

    created = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="status-update-create-1",
        )
    )

    await update_service.execute(
        UpdateApplicationStatusCommand(
            user_id="USER-001",
            application_id=created.application.application_id,
            target_status=ApplicationStatus.PREPARING,
            actor_id="USER-001",
            idempotency_key="postgres-update-1",
        )
    )

    loaded = await get_service.execute(
        GetApplicationQuery(
            user_id="USER-001",
            application_id=created.application.application_id,
        )
    )

    assert loaded.status is ApplicationStatus.PREPARING

    async with postgres_session_factory() as session:
        result = await session.execute(
            select(ApplicationEventRecord).where(
                ApplicationEventRecord.application_id
                == created.application.application_id
            )
        )
        events = result.scalars().all()

    assert len(events) == 2
    assert {event.event_type for event in events} == {
        "application_created",
        "status_changed",
    }

    status_event = next(
        event for event in events if event.event_type == "status_changed"
    )

    assert status_event.attributes == {
        "new_status": "preparing",
        "previous_status": "saved",
    }


@pytest.mark.anyio
async def test_failed_transaction_rolls_back_all_writes(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )

    event = ApplicationEvent.create(
        application_id=application.application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.APPLICATION_CREATED,
        actor_id="USER-001",
    )

    with pytest.raises(IntegrityError):
        async with unit_of_work_factory() as unit_of_work:
            await unit_of_work.applications.add(application)

            # Two records with the same event_id force a primary-key
            # violation when this transaction is committed.
            await unit_of_work.events.add(event)
            await unit_of_work.events.add(event)

            await unit_of_work.commit()

    get_service = GetApplicationService(unit_of_work_factory)

    with pytest.raises(ApplicationNotFoundError):
        await get_service.execute(
            GetApplicationQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )

    async with postgres_session_factory() as session:
        event_count = await session.scalar(
            select(func.count()).select_from(ApplicationEventRecord)
        )

    assert event_count == 0


@pytest.mark.anyio
async def test_list_applications_filters_by_user_and_status(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    update_service = UpdateApplicationStatusService(unit_of_work_factory)
    list_service = ListApplicationsService(unit_of_work_factory)

    first = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="list-monzo-1",
        )
    )
    await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Revolut",
            role_title="AI Engineer",
            actor_id="USER-001",
            idempotency_key="list-revolut-1",
        )
    )
    await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-OTHER",
            company_name="Wise",
            role_title="AI Engineer",
            actor_id="USER-OTHER",
            idempotency_key="list-wise-1",
        )
    )

    await update_service.execute(
        UpdateApplicationStatusCommand(
            user_id="USER-001",
            application_id=first.application.application_id,
            target_status=ApplicationStatus.PREPARING,
            actor_id="USER-001",
            idempotency_key="postgres-list-update-1",
        )
    )

    active = await list_service.execute(
        ListApplicationsQuery(
            user_id="USER-001",
            status=ApplicationStatus.PREPARING,
        )
    )

    all_for_user = await list_service.execute(ListApplicationsQuery(user_id="USER-001"))

    assert len(active) == 1
    assert active[0].application_id == first.application.application_id
    assert len(all_for_user) == 2


@pytest.mark.anyio
async def test_pending_actions_are_user_scoped_and_due_filtered(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    pending_service = GetPendingActionsService(unit_of_work_factory)

    user_application = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="pending-user-1",
        )
    )
    other_application = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-OTHER",
            company_name="Wise",
            role_title="AI Engineer",
            actor_id="USER-OTHER",
            idempotency_key="pending-other-1",
        )
    )

    now = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    due_action = ActionItem.create(
        application_id=user_application.application.application_id,
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up with recruiter.",
        due_at=now,
    )
    future_action = ActionItem.create(
        application_id=user_application.application.application_id,
        user_id="USER-001",
        action_type=ActionItemType.CHECK_STATUS,
        description="Check application status.",
        due_at=now + timedelta(days=7),
    )
    other_user_action = ActionItem.create(
        application_id=other_application.application.application_id,
        user_id="USER-OTHER",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up.",
        due_at=now,
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.actions.add(due_action)
        await unit_of_work.actions.add(future_action)
        await unit_of_work.actions.add(other_user_action)
        await unit_of_work.commit()

    pending = await pending_service.execute(
        GetPendingActionsQuery(
            user_id="USER-001",
            due_before=now,
        )
    )

    assert pending == (due_action,)


@pytest.mark.anyio
async def test_create_application_idempotency_persists_only_once(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )
    service = CreateApplicationService(unit_of_work_factory)

    command = CreateApplicationCommand(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
        actor_id="USER-001",
        idempotency_key="postgres-create-replay-1",
    )

    first = await service.execute(command)
    replay = await service.execute(command)

    assert replay.application.application_id == (first.application.application_id)
    assert replay.event.event_id == first.event.event_id

    async with postgres_session_factory() as session:
        application_count = await session.scalar(
            select(func.count()).select_from(JobApplicationRecord)
        )
        event_count = await session.scalar(
            select(func.count()).select_from(ApplicationEventRecord)
        )

    assert application_count == 1
    assert event_count == 1


@pytest.mark.anyio
async def test_update_application_status_idempotency_persists_only_once(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    update_service = UpdateApplicationStatusService(unit_of_work_factory)

    created = await create_service.execute(
        CreateApplicationCommand(
            user_id="USER-001",
            company_name="Monzo",
            role_title="Junior AI Engineer",
            actor_id="USER-001",
            idempotency_key="update-replay-create-1",
        )
    )

    command = UpdateApplicationStatusCommand(
        user_id="USER-001",
        application_id=created.application.application_id,
        target_status=ApplicationStatus.PREPARING,
        actor_id="USER-001",
        idempotency_key="postgres-update-replay-1",
    )

    first = await update_service.execute(command)
    replay = await update_service.execute(command)

    assert replay.application.application_id == (first.application.application_id)
    assert replay.application.status is ApplicationStatus.PREPARING
    assert replay.event.event_id == first.event.event_id

    async with postgres_session_factory() as session:
        application_count = await session.scalar(
            select(func.count()).select_from(JobApplicationRecord)
        )
        event_count = await session.scalar(
            select(func.count()).select_from(ApplicationEventRecord)
        )

    assert application_count == 1

    # APPLICATION_CREATED + one STATUS_CHANGED.
    assert event_count == 2
