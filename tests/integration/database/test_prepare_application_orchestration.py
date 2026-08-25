"""PostgreSQL integration tests for durable preparation orchestration."""

from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineUnavailableError,
)
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationCommand,
    PrepareApplicationService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)


class _ObservingAgentEngineClient:
    """Fake remote client that observes committed PostgreSQL state."""

    def __init__(
        self,
        *,
        unit_of_work_factory: SqlAlchemyApplicationUnitOfWorkFactory,
        application_id: UUID,
        analysis: AgentEngineJobAnalysis | None = None,
        error: Exception | None = None,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._application_id = application_id
        self._analysis = analysis
        self._error = error

        self.call_count = 0
        self.observed_status: ApplicationPreparationStatus | None = None

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        self.call_count += 1

        async with self._unit_of_work_factory() as unit_of_work:
            preparation = await unit_of_work.preparations.get_for_application(
                user_id=user_id,
                application_id=self._application_id,
            )

        assert preparation is not None
        self.observed_status = preparation.status

        if self._error is not None:
            raise self._error

        if self._analysis is None:
            raise AssertionError("Fake Agent Engine analysis was not configured.")

        return self._analysis

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError(
            "Review is not expected in preparation orchestration tests."
        )


def _completed_analysis(
    *,
    job_id: str,
) -> AgentEngineJobAnalysis:
    return AgentEngineJobAnalysis(
        status=AgentEngineAnalysisStatus.COMPLETED,
        thread_id="THR-POSTGRES-001",
        job_id=job_id,
        role_title="Junior AI Engineer",
        fit_score=0.8,
        requirements=(),
        evidence_matches=(),
        cv_proposals=(),
        reviewable_proposal_ids=(),
        blocked_proposal_ids=(),
        allowed_review_actions=(),
        review_status=None,
    )


async def _persist_application(
    unit_of_work_factory: SqlAlchemyApplicationUnitOfWorkFactory,
) -> JobApplication:
    application = JobApplication.create(
        user_id="USER-ORCHESTRATION-TEST",
        company_name="Example AI",
        role_title="Junior AI Engineer",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.applications.add(application)
        await unit_of_work.commit()

    return application


@pytest.mark.anyio
async def test_starting_state_is_committed_before_remote_analysis(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The remote call must observe STARTING in a separate transaction."""

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application = await _persist_application(unit_of_work_factory)

    client = _ObservingAgentEngineClient(
        unit_of_work_factory=unit_of_work_factory,
        application_id=application.application_id,
        analysis=_completed_analysis(
            job_id=str(application.application_id),
        ),
    )

    service = PrepareApplicationService(
        unit_of_work_factory,
        client,
    )

    result = await service.execute(
        PrepareApplicationCommand(
            user_id=application.user_id,
            application_id=application.application_id,
            job_description="Strong Python skills are essential.",
            actor_id=application.user_id,
        )
    )

    assert client.observed_status is ApplicationPreparationStatus.STARTING
    assert client.call_count == 1

    assert result.preparation.status is ApplicationPreparationStatus.COMPLETED
    assert result.application.status is ApplicationStatus.READY_TO_APPLY

    async with unit_of_work_factory() as unit_of_work:
        stored_preparation = await unit_of_work.preparations.get_for_application(
            user_id=application.user_id,
            application_id=application.application_id,
        )
        stored_application = await unit_of_work.applications.get(
            user_id=application.user_id,
            application_id=application.application_id,
        )

    assert stored_preparation is not None
    assert stored_preparation.status is ApplicationPreparationStatus.COMPLETED
    assert stored_preparation.agent_engine_thread_id == "THR-POSTGRES-001"

    assert stored_application is not None
    assert stored_application.status is ApplicationStatus.READY_TO_APPLY


@pytest.mark.anyio
async def test_unknown_remote_outcome_is_durable_and_not_retried(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """An ambiguous failure must persist and block a second remote POST."""

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application = await _persist_application(unit_of_work_factory)

    client = _ObservingAgentEngineClient(
        unit_of_work_factory=unit_of_work_factory,
        application_id=application.application_id,
        error=AgentEngineUnavailableError("Agent Engine request timed out."),
    )

    service = PrepareApplicationService(
        unit_of_work_factory,
        client,
    )

    command = PrepareApplicationCommand(
        user_id=application.user_id,
        application_id=application.application_id,
        job_description="Strong Python skills are essential.",
        actor_id=application.user_id,
    )

    with pytest.raises(
        AgentEngineUnavailableError,
        match="timed out",
    ):
        await service.execute(command)

    assert client.observed_status is ApplicationPreparationStatus.STARTING
    assert client.call_count == 1

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.preparations.get_for_application(
            user_id=application.user_id,
            application_id=application.application_id,
        )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN

    replay = await service.execute(command)

    assert replay.started_new_analysis is False
    assert replay.preparation.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN

    assert client.call_count == 1
