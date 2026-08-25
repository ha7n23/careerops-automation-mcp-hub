"""Tests for in-memory application-preparation persistence."""

from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryApplicationPreparationRepository,
)


@pytest.mark.anyio
async def test_preparation_repository_is_user_scoped() -> None:
    repository = InMemoryApplicationPreparationRepository()
    application_id = uuid4()

    preparation = ApplicationPreparation.create(
        application_id=application_id,
        user_id="USER-001",
    )

    await repository.add(preparation)

    found = await repository.get_for_application(
        user_id="USER-001",
        application_id=application_id,
    )
    hidden = await repository.get_for_application(
        user_id="USER-OTHER",
        application_id=application_id,
    )

    assert found is preparation
    assert hidden is None


@pytest.mark.anyio
async def test_preparation_repository_saves_state_changes() -> None:
    repository = InMemoryApplicationPreparationRepository()

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-001",
    )

    await repository.add(preparation)

    preparation.mark_starting()
    await repository.save(preparation)

    stored = await repository.get_for_application(
        user_id=preparation.user_id,
        application_id=preparation.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.STARTING
