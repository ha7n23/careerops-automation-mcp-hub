"""PostgreSQL integration tests for application-preparation persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)


@pytest.mark.anyio
async def test_application_preparation_round_trip(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Preparation state should survive a real PostgreSQL transaction."""

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application = JobApplication.create(
        user_id="USER-PREPARATION-TEST",
        company_name="Example AI",
        role_title="Junior AI Engineer",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.applications.add(application)
        await unit_of_work.commit()

    preparation = ApplicationPreparation.create(
        application_id=application.application_id,
        user_id=application.user_id,
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.preparations.add(preparation)
        await unit_of_work.commit()

    preparation.mark_starting()
    preparation.mark_completed(thread_id="THR-PERSISTED")

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.preparations.save(preparation)
        await unit_of_work.commit()

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.preparations.get_for_application(
            user_id=application.user_id,
            application_id=application.application_id,
        )

    assert stored is not None
    assert stored.preparation_id == preparation.preparation_id
    assert stored.application_id == application.application_id
    assert stored.status is ApplicationPreparationStatus.COMPLETED
    assert stored.agent_engine_job_id == str(application.application_id)
    assert stored.agent_engine_thread_id == "THR-PERSISTED"
    assert stored.error_message is None
