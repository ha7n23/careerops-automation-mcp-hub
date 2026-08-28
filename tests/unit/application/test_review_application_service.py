from dataclasses import dataclass

import pytest

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineContractError,
    AgentEngineUnavailableError,
    AgentEngineValidationError,
    ApplicationReviewBlockedError,
)
from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyConflictError,
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
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewOutcome,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.unit_of_work import (
    InMemoryApplicationUnitOfWorkFactory,
)


@dataclass(frozen=True, slots=True)
class _ReviewCall:
    user_id: str
    thread_id: str
    decision: AgentEngineReviewDecision


class _FakeAgentEngineClient:
    def __init__(
        self,
        *,
        analysis: AgentEngineJobAnalysis | None = None,
        error: Exception | None = None,
    ) -> None:
        self.analysis = analysis
        self.error = error
        self.review_calls: list[_ReviewCall] = []

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError("Job analysis is not expected in review-service tests.")

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        self.review_calls.append(
            _ReviewCall(
                user_id=user_id,
                thread_id=thread_id,
                decision=decision,
            )
        )

        if self.error is not None:
            raise self.error

        if self.analysis is None:
            raise AssertionError("Fake Agent Engine review result was not configured.")

        return self.analysis


def _analysis(
    *,
    application: JobApplication,
    status: AgentEngineAnalysisStatus,
    thread_id: str = "THR-REVIEW-001",
) -> AgentEngineJobAnalysis:
    return AgentEngineJobAnalysis(
        status=status,
        thread_id=thread_id,
        job_id=str(application.application_id),
        role_title=application.role_title,
        fit_score=0.8,
        requirements=(),
        evidence_matches=(),
        cv_proposals=(),
        reviewable_proposal_ids=(),
        blocked_proposal_ids=(),
        allowed_review_actions=(),
        review_status=None,
    )


async def _build_service(
    client: _FakeAgentEngineClient,
) -> tuple[
    ReviewApplicationService,
    JobApplication,
    ApplicationPreparation,
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

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Example AI",
        role_title="Junior AI Engineer",
    )
    application.transition_to(ApplicationStatus.PREPARING)

    preparation = ApplicationPreparation.create(
        application_id=application.application_id,
        user_id=application.user_id,
    )
    preparation.mark_starting()
    preparation.mark_awaiting_review(
        thread_id="THR-REVIEW-001",
    )

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.applications.add(application)
        await unit_of_work.preparations.add(preparation)
        await unit_of_work.commit()

    return (
        ReviewApplicationService(
            unit_of_work_factory,
            client,
        ),
        application,
        preparation,
        events,
        unit_of_work_factory,
    )


def _approve_command(
    application: JobApplication,
    *,
    idempotency_key: str = "review-001",
) -> ReviewApplicationCommand:
    return ReviewApplicationCommand(
        user_id=application.user_id,
        application_id=application.application_id,
        actor_id="USER-001",
        idempotency_key=idempotency_key,
        action=ApplicationReviewAction.APPROVE,
        approved_proposal_ids=("CVP-001",),
    )


@pytest.mark.anyio
async def test_completed_review_advances_application_to_ready() -> None:
    client = _FakeAgentEngineClient()
    service, application, _, events, unit_of_work_factory = await _build_service(client)

    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.COMPLETED,
    )

    result = await service.execute(_approve_command(application))

    assert result.started_new_review is True
    assert result.analysis is client.analysis

    assert result.submission.status is ApplicationReviewSubmissionStatus.COMPLETED
    assert result.submission.outcome is ApplicationReviewOutcome.COMPLETED

    assert result.preparation.status is ApplicationPreparationStatus.COMPLETED
    assert result.application.status is ApplicationStatus.READY_TO_APPLY

    assert len(client.review_calls) == 1
    assert len(events.all()) == 1

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id="USER-001",
            idempotency_key="review-001",
        )

    assert stored is not None
    assert stored.status is ApplicationReviewSubmissionStatus.COMPLETED


@pytest.mark.anyio
async def test_review_can_return_to_awaiting_review() -> None:
    client = _FakeAgentEngineClient()
    service, application, preparation, events, _ = await _build_service(client)

    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.AWAITING_REVIEW,
    )

    result = await service.execute(
        ReviewApplicationCommand(
            user_id=application.user_id,
            application_id=application.application_id,
            actor_id="USER-001",
            idempotency_key="review-regenerate-001",
            action=ApplicationReviewAction.REGENERATE,
            rejected_proposal_ids=("CVP-001",),
            reviewer_comment="Make the wording more concise.",
        )
    )

    assert result.submission.outcome is ApplicationReviewOutcome.AWAITING_REVIEW
    assert result.preparation.status is ApplicationPreparationStatus.AWAITING_REVIEW
    assert result.preparation is preparation
    assert application.status is ApplicationStatus.PREPARING
    assert events.all() == ()


@pytest.mark.anyio
async def test_same_review_key_replays_without_second_remote_call() -> None:
    client = _FakeAgentEngineClient()
    service, application, _, _, _ = await _build_service(client)

    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.COMPLETED,
    )

    command = _approve_command(application)

    first = await service.execute(command)
    replay = await service.execute(command)

    assert first.started_new_review is True
    assert replay.started_new_review is False
    assert replay.analysis is None

    assert replay.submission.status is ApplicationReviewSubmissionStatus.COMPLETED
    assert len(client.review_calls) == 1


@pytest.mark.anyio
async def test_same_key_with_different_decision_conflicts() -> None:
    client = _FakeAgentEngineClient()
    service, application, _, _, _ = await _build_service(client)

    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.COMPLETED,
    )

    await service.execute(_approve_command(application))

    with pytest.raises(
        IdempotencyConflictError,
        match="different review decision",
    ):
        await service.execute(
            ReviewApplicationCommand(
                user_id=application.user_id,
                application_id=application.application_id,
                actor_id="USER-001",
                idempotency_key="review-001",
                action=ApplicationReviewAction.REJECT,
                rejected_proposal_ids=("CVP-001",),
            )
        )

    assert len(client.review_calls) == 1


@pytest.mark.anyio
async def test_unknown_review_outcome_blocks_new_key() -> None:
    client = _FakeAgentEngineClient(
        error=AgentEngineUnavailableError("Agent Engine request timed out.")
    )

    service, application, _, _, unit_of_work_factory = await _build_service(client)

    command = _approve_command(application)

    with pytest.raises(
        AgentEngineUnavailableError,
        match="timed out",
    ):
        await service.execute(command)

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id="USER-001",
            idempotency_key="review-001",
        )

    assert stored is not None
    assert stored.status is ApplicationReviewSubmissionStatus.OUTCOME_UNKNOWN

    replay = await service.execute(command)

    assert replay.started_new_review is False
    assert len(client.review_calls) == 1

    with pytest.raises(
        ApplicationReviewBlockedError,
        match="unresolved",
    ):
        await service.execute(
            _approve_command(
                application,
                idempotency_key="review-002",
            )
        )

    assert len(client.review_calls) == 1


@pytest.mark.anyio
async def test_known_failure_allows_corrected_new_submission() -> None:
    client = _FakeAgentEngineClient(
        error=AgentEngineValidationError("Review decision was rejected.")
    )

    service, application, _, _, unit_of_work_factory = await _build_service(client)

    with pytest.raises(
        AgentEngineValidationError,
        match="rejected",
    ):
        await service.execute(_approve_command(application))

    async with unit_of_work_factory() as unit_of_work:
        failed = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id="USER-001",
            idempotency_key="review-001",
        )

    assert failed is not None
    assert failed.status is ApplicationReviewSubmissionStatus.FAILED

    client.error = None
    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.COMPLETED,
    )

    result = await service.execute(
        _approve_command(
            application,
            idempotency_key="review-002",
        )
    )

    assert result.started_new_review is True
    assert len(client.review_calls) == 2


@pytest.mark.anyio
async def test_mismatched_review_response_records_unknown_outcome() -> None:
    client = _FakeAgentEngineClient()
    service, application, _, _, unit_of_work_factory = await _build_service(client)

    client.analysis = _analysis(
        application=application,
        status=AgentEngineAnalysisStatus.COMPLETED,
        thread_id="THR-UNEXPECTED",
    )

    with pytest.raises(
        AgentEngineContractError,
        match="unexpected thread_id",
    ):
        await service.execute(_approve_command(application))

    async with unit_of_work_factory() as unit_of_work:
        stored = await unit_of_work.review_submissions.get_by_idempotency_key(
            user_id="USER-001",
            idempotency_key="review-001",
        )

    assert stored is not None
    assert stored.status is ApplicationReviewSubmissionStatus.OUTCOME_UNKNOWN
