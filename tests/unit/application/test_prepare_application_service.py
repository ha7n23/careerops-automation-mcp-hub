from dataclasses import dataclass
from uuid import UUID

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
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationCommand,
    PrepareApplicationService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
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
class _AnalyseCall:
    user_id: str
    job_id: str
    job_description: str


class _FakeAgentEngineClient:
    def __init__(
        self,
        *,
        analysis: AgentEngineJobAnalysis | None = None,
        error: Exception | None = None,
    ) -> None:
        self.analysis = analysis
        self.error = error
        self.calls: list[_AnalyseCall] = []

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        self.calls.append(
            _AnalyseCall(
                user_id=user_id,
                job_id=job_id,
                job_description=job_description,
            )
        )

        if self.error is not None:
            raise self.error

        if self.analysis is None:
            raise AssertionError("Fake Agent Engine analysis was not configured.")

        return self.analysis

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError("Review is not expected in preparation-service tests.")


def _build_application() -> JobApplication:
    return JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )


def _build_analysis(
    *,
    job_id: str,
    status: AgentEngineAnalysisStatus,
    thread_id: str = "THR-001",
) -> AgentEngineJobAnalysis:
    return AgentEngineJobAnalysis(
        status=status,
        thread_id=thread_id,
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


def _build_service(
    *,
    client: _FakeAgentEngineClient,
) -> tuple[
    PrepareApplicationService,
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

    return (
        PrepareApplicationService(
            unit_of_work_factory,
            client,
        ),
        applications,
        events,
        unit_of_work_factory,
    )


async def _get_preparation(
    unit_of_work_factory: InMemoryApplicationUnitOfWorkFactory,
    *,
    application_id: UUID,
) -> ApplicationPreparation | None:
    async with unit_of_work_factory() as unit_of_work:
        return await unit_of_work.preparations.get_for_application(
            user_id="USER-001",
            application_id=application_id,
        )


@pytest.mark.anyio
async def test_completed_analysis_advances_application_to_ready_to_apply() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        analysis=_build_analysis(
            job_id=str(application.application_id),
            status=AgentEngineAnalysisStatus.COMPLETED,
        )
    )

    service, applications, events, unit_of_work_factory = _build_service(client=client)

    await applications.add(application)

    result = await service.execute(
        PrepareApplicationCommand(
            user_id="USER-001",
            application_id=application.application_id,
            job_description="Strong Python skills are essential.",
            actor_id="USER-001",
        )
    )

    assert result.started_new_analysis is True
    assert result.analysis is client.analysis
    assert result.application.status is ApplicationStatus.READY_TO_APPLY

    assert result.preparation.status is ApplicationPreparationStatus.COMPLETED
    assert result.preparation.agent_engine_thread_id == "THR-001"

    assert client.calls == [
        _AnalyseCall(
            user_id="USER-001",
            job_id=str(application.application_id),
            job_description="Strong Python skills are essential.",
        )
    ]

    assert [dict(event.attributes) for event in events.all()] == [
        {
            "new_status": "preparing",
            "previous_status": "saved",
        },
        {
            "new_status": "ready_to_apply",
            "previous_status": "preparing",
        },
    ]

    stored = await _get_preparation(
        unit_of_work_factory,
        application_id=application.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.COMPLETED


@pytest.mark.anyio
async def test_awaiting_review_keeps_application_preparing() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        analysis=_build_analysis(
            job_id=str(application.application_id),
            status=AgentEngineAnalysisStatus.AWAITING_REVIEW,
        )
    )

    service, applications, events, _ = _build_service(client=client)

    await applications.add(application)

    result = await service.execute(
        PrepareApplicationCommand(
            user_id="USER-001",
            application_id=application.application_id,
            job_description="Strong Python skills are essential.",
            actor_id="USER-001",
        )
    )

    assert result.application.status is ApplicationStatus.PREPARING
    assert result.preparation.status is ApplicationPreparationStatus.AWAITING_REVIEW
    assert result.preparation.agent_engine_thread_id == "THR-001"

    assert len(events.all()) == 1


@pytest.mark.anyio
async def test_existing_completed_preparation_does_not_start_second_analysis() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        analysis=_build_analysis(
            job_id=str(application.application_id),
            status=AgentEngineAnalysisStatus.COMPLETED,
        )
    )

    service, applications, _, _ = _build_service(client=client)

    await applications.add(application)

    command = PrepareApplicationCommand(
        user_id="USER-001",
        application_id=application.application_id,
        job_description="Strong Python skills are essential.",
        actor_id="USER-001",
    )

    first = await service.execute(command)
    replay = await service.execute(command)

    assert first.started_new_analysis is True
    assert replay.started_new_analysis is False
    assert replay.analysis is None

    assert replay.preparation.status is ApplicationPreparationStatus.COMPLETED

    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_ambiguous_agent_engine_failure_is_not_automatically_retried() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        error=AgentEngineUnavailableError("Agent Engine request timed out.")
    )

    service, applications, _, unit_of_work_factory = _build_service(client=client)

    await applications.add(application)

    command = PrepareApplicationCommand(
        user_id="USER-001",
        application_id=application.application_id,
        job_description="Strong Python skills are essential.",
        actor_id="USER-001",
    )

    with pytest.raises(
        AgentEngineUnavailableError,
        match="timed out",
    ):
        await service.execute(command)

    stored = await _get_preparation(
        unit_of_work_factory,
        application_id=application.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN

    replay = await service.execute(command)

    assert replay.started_new_analysis is False
    assert replay.preparation.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN

    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_known_agent_engine_rejection_is_recorded_as_failed() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        error=AgentEngineValidationError("Job description was rejected.")
    )

    service, applications, _, unit_of_work_factory = _build_service(client=client)

    await applications.add(application)

    command = PrepareApplicationCommand(
        user_id="USER-001",
        application_id=application.application_id,
        job_description="Strong Python skills are essential.",
        actor_id="USER-001",
    )

    with pytest.raises(
        AgentEngineValidationError,
        match="rejected",
    ):
        await service.execute(command)

    stored = await _get_preparation(
        unit_of_work_factory,
        application_id=application.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.FAILED

    replay = await service.execute(command)

    assert replay.started_new_analysis is False
    assert replay.preparation.status is ApplicationPreparationStatus.FAILED

    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_mismatched_agent_engine_job_id_records_unknown_outcome() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient(
        analysis=_build_analysis(
            job_id="UNEXPECTED-JOB",
            status=AgentEngineAnalysisStatus.COMPLETED,
        )
    )

    service, applications, _, unit_of_work_factory = _build_service(client=client)

    await applications.add(application)

    with pytest.raises(
        AgentEngineContractError,
        match="unexpected job_id",
    ):
        await service.execute(
            PrepareApplicationCommand(
                user_id="USER-001",
                application_id=application.application_id,
                job_description="Strong Python skills are essential.",
                actor_id="USER-001",
            )
        )

    stored = await _get_preparation(
        unit_of_work_factory,
        application_id=application.application_id,
    )

    assert stored is not None
    assert stored.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN


@pytest.mark.anyio
async def test_prepare_application_is_user_scoped() -> None:
    application = _build_application()

    client = _FakeAgentEngineClient()

    service, applications, _, _ = _build_service(client=client)

    await applications.add(application)

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            PrepareApplicationCommand(
                user_id="USER-OTHER",
                application_id=application.application_id,
                job_description="Strong Python skills are essential.",
                actor_id="USER-OTHER",
            )
        )

    assert client.calls == []
