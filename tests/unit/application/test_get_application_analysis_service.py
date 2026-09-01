from dataclasses import dataclass

import pytest

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineContractError,
    ApplicationAnalysisUnavailableError,
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.services.get_application_analysis import (
    GetApplicationAnalysisQuery,
    GetApplicationAnalysisService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
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
class _GetCall:
    user_id: str
    thread_id: str


class _FakeAgentEngineClient:
    def __init__(self, analysis: AgentEngineJobAnalysis) -> None:
        self.analysis = analysis
        self.get_calls: list[_GetCall] = []

    async def get_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> AgentEngineJobAnalysis:
        self.get_calls.append(
            _GetCall(
                user_id=user_id,
                thread_id=thread_id,
            )
        )
        return self.analysis

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError("Analysis start is not expected.")

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError("Review is not expected.")


def _build_application(
    *,
    user_id: str = "USER-001",
) -> JobApplication:
    application = JobApplication.create(
        user_id=user_id,
        company_name="Monzo",
        role_title="Junior AI Engineer",
    )
    application.transition_to(ApplicationStatus.PREPARING)
    return application


def _build_analysis(
    *,
    job_id: str,
    thread_id: str = "THR-001",
) -> AgentEngineJobAnalysis:
    return AgentEngineJobAnalysis(
        status=AgentEngineAnalysisStatus.AWAITING_REVIEW,
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


def _build_unit_of_work_factory() -> tuple[
    InMemoryJobApplicationRepository,
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

    return applications, unit_of_work_factory


async def _add_preparation(
    unit_of_work_factory: InMemoryApplicationUnitOfWorkFactory,
    *,
    application: JobApplication,
    thread_id: str = "THR-001",
) -> ApplicationPreparation:
    preparation = ApplicationPreparation.create(
        application_id=application.application_id,
        user_id=application.user_id,
    )
    preparation.mark_starting()
    preparation.mark_awaiting_review(thread_id=thread_id)

    async with unit_of_work_factory() as unit_of_work:
        await unit_of_work.preparations.add(preparation)
        await unit_of_work.commit()

    return preparation


@pytest.mark.anyio
async def test_get_application_analysis_recovers_remote_analysis() -> None:
    application = _build_application()
    applications, unit_of_work_factory = _build_unit_of_work_factory()
    await applications.add(application)

    preparation = await _add_preparation(
        unit_of_work_factory,
        application=application,
    )

    analysis = _build_analysis(
        job_id=str(application.application_id),
    )
    client = _FakeAgentEngineClient(analysis)

    service = GetApplicationAnalysisService(
        unit_of_work_factory,
        client,
    )

    result = await service.execute(
        GetApplicationAnalysisQuery(
            user_id="USER-001",
            application_id=application.application_id,
        )
    )

    assert result.application is application
    assert result.preparation is preparation
    assert result.analysis is analysis

    assert client.get_calls == [
        _GetCall(
            user_id="USER-001",
            thread_id="THR-001",
        )
    ]


@pytest.mark.anyio
async def test_get_application_analysis_requires_recoverable_thread() -> None:
    application = _build_application()
    applications, unit_of_work_factory = _build_unit_of_work_factory()
    await applications.add(application)

    client = _FakeAgentEngineClient(
        _build_analysis(
            job_id=str(application.application_id),
        )
    )
    service = GetApplicationAnalysisService(
        unit_of_work_factory,
        client,
    )

    with pytest.raises(ApplicationAnalysisUnavailableError):
        await service.execute(
            GetApplicationAnalysisQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )

    assert client.get_calls == []


@pytest.mark.anyio
async def test_get_application_analysis_is_user_scoped() -> None:
    application = _build_application(user_id="USER-OTHER")
    applications, unit_of_work_factory = _build_unit_of_work_factory()
    await applications.add(application)

    client = _FakeAgentEngineClient(
        _build_analysis(
            job_id=str(application.application_id),
        )
    )
    service = GetApplicationAnalysisService(
        unit_of_work_factory,
        client,
    )

    with pytest.raises(ApplicationNotFoundError):
        await service.execute(
            GetApplicationAnalysisQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )

    assert client.get_calls == []


@pytest.mark.anyio
async def test_get_application_analysis_rejects_wrong_remote_job() -> None:
    application = _build_application()
    applications, unit_of_work_factory = _build_unit_of_work_factory()
    await applications.add(application)

    await _add_preparation(
        unit_of_work_factory,
        application=application,
    )

    client = _FakeAgentEngineClient(
        _build_analysis(
            job_id="UNEXPECTED-JOB",
        )
    )
    service = GetApplicationAnalysisService(
        unit_of_work_factory,
        client,
    )

    with pytest.raises(
        AgentEngineContractError,
        match="unexpected job_id",
    ):
        await service.execute(
            GetApplicationAnalysisQuery(
                user_id="USER-001",
                application_id=application.application_id,
            )
        )
