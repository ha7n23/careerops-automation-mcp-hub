"""PostgreSQL concurrency tests for durable human-review orchestration."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    ApplicationReviewBlockedError,
)
from careerops_automation_mcp_hub.application.services.review_application import (
    ReviewApplicationCommand,
    ReviewApplicationService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)


class _BlockingReviewAgentEngineClient:
    """Fake remote service that holds the first review request open."""

    def __init__(
        self,
        *,
        application: JobApplication,
    ) -> None:
        self._application = application

        self.call_count = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError(
            "Job analysis is not expected in review orchestration tests."
        )

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        self.call_count += 1

        self.entered.set()

        await self.release.wait()

        return AgentEngineJobAnalysis(
            status=AgentEngineAnalysisStatus.COMPLETED,
            thread_id=thread_id,
            job_id=str(self._application.application_id),
            role_title=self._application.role_title,
            fit_score=0.8,
            requirements=(),
            evidence_matches=(),
            cv_proposals=(),
            reviewable_proposal_ids=(),
            blocked_proposal_ids=(),
            allowed_review_actions=(),
            review_status=None,
        )


async def _persist_reviewable_application(
    unit_of_work_factory: SqlAlchemyApplicationUnitOfWorkFactory,
) -> tuple[
    JobApplication,
    ApplicationPreparation,
]:
    application = JobApplication.create(
        user_id="USER-REVIEW-CONCURRENCY",
        company_name="Example AI",
        role_title="Junior AI Engineer",
    )

    application.transition_to(ApplicationStatus.PREPARING)

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.applications.add(application)
        await unit_of_work.commit()

    preparation = ApplicationPreparation.create(
        application_id=application.application_id,
        user_id=application.user_id,
    )

    preparation.mark_starting()
    preparation.mark_awaiting_review(
        thread_id="THR-REVIEW-CONCURRENCY",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.preparations.add(preparation)
        await unit_of_work.commit()

    return application, preparation


def _review_command(
    application: JobApplication,
    *,
    idempotency_key: str,
) -> ReviewApplicationCommand:
    return ReviewApplicationCommand(
        user_id=application.user_id,
        application_id=application.application_id,
        actor_id=application.user_id,
        idempotency_key=idempotency_key,
        action=ApplicationReviewAction.APPROVE,
        approved_proposal_ids=("CVP-001",),
    )


@pytest.mark.anyio
async def test_concurrent_review_keys_cannot_cross_remote_boundary_twice(
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A durable unresolved review must block a concurrent second key."""

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(
        postgres_session_factory
    )

    application, preparation = await _persist_reviewable_application(
        unit_of_work_factory
    )

    client = _BlockingReviewAgentEngineClient(
        application=application,
    )

    service = ReviewApplicationService(
        unit_of_work_factory,
        client,
    )

    first_command = _review_command(
        application,
        idempotency_key="review-concurrent-001",
    )

    second_command = _review_command(
        application,
        idempotency_key="review-concurrent-002",
    )

    first_task = asyncio.create_task(service.execute(first_command))

    try:
        await asyncio.wait_for(
            client.entered.wait(),
            timeout=2.0,
        )

        # Reaching the remote client means SUBMITTING should already have
        # been committed by the first orchestration transaction.
        async with unit_of_work_factory() as unit_of_work:
            first_submission = (
                await unit_of_work.review_submissions.get_by_idempotency_key(
                    user_id=application.user_id,
                    idempotency_key="review-concurrent-001",
                )
            )

        assert first_submission is not None
        assert first_submission.status is ApplicationReviewSubmissionStatus.SUBMITTING

        with pytest.raises(
            ApplicationReviewBlockedError,
            match="unresolved",
        ):
            await service.execute(second_command)

        assert client.call_count == 1

        async with unit_of_work_factory() as unit_of_work:
            second_submission = (
                await unit_of_work.review_submissions.get_by_idempotency_key(
                    user_id=application.user_id,
                    idempotency_key="review-concurrent-002",
                )
            )

        assert second_submission is None

    finally:
        client.release.set()

    first_result = await first_task

    assert first_result.started_new_review is True
    assert first_result.submission.status is ApplicationReviewSubmissionStatus.COMPLETED
    assert first_result.application.status is ApplicationStatus.READY_TO_APPLY
    assert client.call_count == 1

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
    assert stored_preparation.preparation_id == preparation.preparation_id

    assert stored_application is not None
    assert stored_application.status is ApplicationStatus.READY_TO_APPLY
