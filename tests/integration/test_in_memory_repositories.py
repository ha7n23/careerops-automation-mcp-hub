from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
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
