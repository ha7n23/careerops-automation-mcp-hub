import pytest
from mcp import Client

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.services.get_application_analysis import (
    GetApplicationAnalysisService,
)
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationService,
)
from careerops_automation_mcp_hub.application.services.review_application import (
    ReviewApplicationService,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.unit_of_work import (
    InMemoryApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.mcp.principal import (
    Principal,
    StaticPrincipalProvider,
)
from careerops_automation_mcp_hub.mcp.server import build_mcp_server


class _ReviewMCPAgentEngineClient:
    def __init__(self) -> None:
        self.analysis_call_count = 0
        self.review_call_count = 0
        self.job_id: str | None = None

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        self.analysis_call_count += 1
        self.job_id = job_id

        return AgentEngineJobAnalysis(
            status=AgentEngineAnalysisStatus.AWAITING_REVIEW,
            thread_id="THR-MCP-REVIEW",
            job_id=job_id,
            role_title="Junior AI Engineer",
            fit_score=0.84,
            requirements=(),
            evidence_matches=(),
            cv_proposals=(),
            reviewable_proposal_ids=("CVP-001",),
            blocked_proposal_ids=(),
            allowed_review_actions=(),
            review_status="pending",
        )

    async def get_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> AgentEngineJobAnalysis:
        if self.job_id is None:
            raise AssertionError("Preparation must run before recovery.")

        return AgentEngineJobAnalysis(
            status=AgentEngineAnalysisStatus.AWAITING_REVIEW,
            thread_id=thread_id,
            job_id=self.job_id,
            role_title="Junior AI Engineer",
            fit_score=0.84,
            requirements=(),
            evidence_matches=(),
            cv_proposals=(),
            reviewable_proposal_ids=("CVP-001",),
            blocked_proposal_ids=(),
            allowed_review_actions=(),
            review_status="pending",
        )

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        self.review_call_count += 1

        if self.job_id is None:
            raise AssertionError("Preparation must run before review.")

        return AgentEngineJobAnalysis(
            status=AgentEngineAnalysisStatus.COMPLETED,
            thread_id=thread_id,
            job_id=self.job_id,
            role_title="Junior AI Engineer",
            fit_score=0.84,
            requirements=(),
            evidence_matches=(),
            cv_proposals=(),
            reviewable_proposal_ids=(),
            blocked_proposal_ids=(),
            allowed_review_actions=(),
            review_status="approved",
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def review_mcp_client():
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    agent_engine_client = _ReviewMCPAgentEngineClient()

    prepare_service = PrepareApplicationService(
        unit_of_work_factory,
        agent_engine_client,
    )

    get_application_analysis_service = GetApplicationAnalysisService(
        unit_of_work_factory,
        agent_engine_client,
    )

    review_service = ReviewApplicationService(
        unit_of_work_factory,
        agent_engine_client,
    )

    server = build_mcp_server(
        principal_provider=StaticPrincipalProvider(
            Principal(
                user_id="USER-001",
                actor_id="MCP-TEST",
            )
        ),
        unit_of_work_factory=unit_of_work_factory,
        prepare_application_service=prepare_service,
        review_application_service=review_service,
        get_application_analysis_service=get_application_analysis_service,
    )

    async with Client(
        server,
        raise_exceptions=True,
    ) as client:
        yield client, agent_engine_client


@pytest.mark.anyio
async def test_review_application_returns_structured_completion(
    review_mcp_client,
) -> None:
    client, agent_engine_client = review_mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
            "idempotency_key": "review-create-001",
        },
    )

    assert created.structured_content is not None

    application_id = created.structured_content["application_id"]

    prepared = await client.call_tool(
        "prepare_application",
        {
            "application_id": application_id,
            "job_description": ("Strong Python engineering skills are essential."),
        },
    )

    assert prepared.is_error is False
    assert prepared.structured_content is not None
    assert prepared.structured_content["preparation"]["status"] == "awaiting_review"

    reviewed = await client.call_tool(
        "review_application",
        {
            "application_id": application_id,
            "idempotency_key": "review-submit-001",
            "action": "approve",
            "approved_proposal_ids": ["CVP-001"],
        },
    )

    assert reviewed.is_error is False
    assert reviewed.structured_content is not None

    content = reviewed.structured_content

    assert content["started_new_review"] is True
    assert content["application"]["status"] == "ready_to_apply"
    assert content["preparation"]["status"] == "completed"

    assert content["submission"]["status"] == "completed"
    assert content["submission"]["outcome"] == "completed"
    assert content["submission"]["action"] == "approve"

    assert content["analysis"] is not None
    assert content["analysis"]["status"] == "completed"
    assert content["analysis"]["job_id"] == application_id
    assert content["analysis"]["thread_id"] == "THR-MCP-REVIEW"

    assert agent_engine_client.analysis_call_count == 1
    assert agent_engine_client.review_call_count == 1


@pytest.mark.anyio
async def test_review_application_replay_does_not_resubmit(
    review_mcp_client,
) -> None:
    client, agent_engine_client = review_mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
            "idempotency_key": "review-replay-create-001",
        },
    )

    assert created.structured_content is not None

    application_id = created.structured_content["application_id"]

    await client.call_tool(
        "prepare_application",
        {
            "application_id": application_id,
            "job_description": ("Strong Python engineering skills are essential."),
        },
    )

    arguments = {
        "application_id": application_id,
        "idempotency_key": "review-replay-001",
        "action": "approve",
        "approved_proposal_ids": ["CVP-001"],
    }

    first = await client.call_tool(
        "review_application",
        arguments,
    )

    replay = await client.call_tool(
        "review_application",
        arguments,
    )

    assert first.is_error is False
    assert replay.is_error is False
    assert replay.structured_content is not None

    assert replay.structured_content["started_new_review"] is False

    assert replay.structured_content["submission"]["status"] == "completed"

    assert replay.structured_content["analysis"] is None

    assert agent_engine_client.analysis_call_count == 1
    assert agent_engine_client.review_call_count == 1


@pytest.mark.anyio
async def test_get_application_analysis_recovers_awaiting_review_state(
    review_mcp_client,
) -> None:
    client, _ = review_mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
            "idempotency_key": "analysis-recovery-create-001",
        },
    )

    assert created.structured_content is not None
    application_id = created.structured_content["application_id"]

    prepared = await client.call_tool(
        "prepare_application",
        {
            "application_id": application_id,
            "job_description": "Strong Python engineering skills are essential.",
        },
    )

    assert prepared.is_error is False

    recovered = await client.call_tool(
        "get_application_analysis",
        {
            "application_id": application_id,
        },
    )

    assert recovered.is_error is False
    assert recovered.structured_content is not None

    content = recovered.structured_content

    assert content["application"]["application_id"] == application_id
    assert content["application"]["status"] == "preparing"

    assert content["preparation"]["status"] == "awaiting_review"
    assert content["preparation"]["agent_engine_thread_id"] == "THR-MCP-REVIEW"

    assert content["analysis"]["status"] == "awaiting_review"
    assert content["analysis"]["thread_id"] == "THR-MCP-REVIEW"
    assert content["analysis"]["job_id"] == application_id
    assert content["analysis"]["reviewable_proposal_ids"] == ["CVP-001"]
