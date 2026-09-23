from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyOperation,
)
from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryIdempotencyRepository,
    InMemoryJobApplicationRepository,
)


@pytest.mark.anyio
async def test_action_repository_finds_and_saves_pending_action() -> None:
    repository = InMemoryActionItemRepository()
    application_id = uuid4()
    completed_at = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

    action = ActionItem.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ActionItemType.REVIEW_CV,
        description="Review tailored CV changes.",
    )

    await repository.add(action)

    pending = await repository.get_pending_for_application(
        user_id="USER-001",
        application_id=application_id,
        action_type=ActionItemType.REVIEW_CV,
    )

    assert pending is action
    assert (
        await repository.get_pending_for_application(
            user_id="USER-OTHER",
            application_id=application_id,
            action_type=ActionItemType.REVIEW_CV,
        )
        is None
    )

    action.complete(at=completed_at)
    await repository.save(action)

    assert action.status is ActionItemStatus.COMPLETED
    assert action.completed_at == completed_at
    assert (
        await repository.get_pending_for_application(
            user_id="USER-001",
            application_id=application_id,
            action_type=ActionItemType.REVIEW_CV,
        )
        is None
    )


@pytest.mark.anyio
async def test_application_repository_is_user_scoped() -> None:
    repository = InMemoryJobApplicationRepository()

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )

    await repository.add(application)

    assert (
        await repository.get(
            user_id="USER-001",
            application_id=application.application_id,
        )
        is application
    )

    assert (
        await repository.get(
            user_id="USER-OTHER",
            application_id=application.application_id,
        )
        is None
    )


@pytest.mark.anyio
async def test_event_repository_preserves_append_order() -> None:
    repository = InMemoryApplicationEventRepository()
    application_id = uuid4()

    first = ApplicationEvent.create(
        application_id=application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.APPLICATION_CREATED,
        actor_id="USER-001",
    )
    second = ApplicationEvent.create(
        application_id=application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.STATUS_CHANGED,
        actor_id="USER-001",
    )

    await repository.add(first)
    await repository.add(second)

    assert repository.all() == (first, second)


@pytest.mark.anyio
async def test_in_memory_idempotency_repository_replays_completed_result() -> None:
    repository = InMemoryIdempotencyRepository()

    now = datetime(2026, 8, 19, 18, 0, tzinfo=UTC)

    first = await repository.claim(
        user_id="USER-001",
        operation=IdempotencyOperation.CREATE_APPLICATION,
        idempotency_key="workflow-123",
        request_fingerprint="a" * 64,
        created_at=now,
    )

    assert first.acquired is True

    await repository.complete(
        user_id="USER-001",
        operation=IdempotencyOperation.CREATE_APPLICATION,
        idempotency_key="workflow-123",
        request_fingerprint="a" * 64,
        response_payload={
            "application_id": "APP-123",
        },
        completed_at=now,
    )

    replay = await repository.claim(
        user_id="USER-001",
        operation=IdempotencyOperation.CREATE_APPLICATION,
        idempotency_key="workflow-123",
        request_fingerprint="a" * 64,
        created_at=now,
    )

    assert replay.acquired is False
    assert replay.request_fingerprint == "a" * 64
    assert replay.response_payload == {"application_id": "APP-123"}
