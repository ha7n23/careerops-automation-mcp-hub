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


class _FakeAgentEngineClient:
    def __init__(self) -> None:
        self.call_count = 0

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        self.call_count += 1

        return AgentEngineJobAnalysis(
            status=AgentEngineAnalysisStatus.COMPLETED,
            thread_id="THR-MCP-PREPARE",
            job_id=job_id,
            role_title="Junior AI Engineer",
            fit_score=0.82,
            requirements=(),
            evidence_matches=(),
            cv_proposals=(),
            reviewable_proposal_ids=(),
            blocked_proposal_ids=(),
            allowed_review_actions=(),
            review_status=None,
        )

    async def get_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError(
            "Analysis recovery is not expected in application MCP tests."
        )

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        raise AssertionError("Review is not expected in preparation MCP tests.")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def preparation_mcp_client():
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    agent_engine_client = _FakeAgentEngineClient()

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

    async with Client(server, raise_exceptions=True) as client:
        yield client, agent_engine_client


@pytest.mark.anyio
async def test_prepare_application_returns_structured_analysis(
    preparation_mcp_client,
) -> None:
    client, agent_engine_client = preparation_mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
            "idempotency_key": "prepare-create-1",
        },
    )

    assert created.structured_content is not None
    application_id = created.structured_content["application_id"]

    result = await client.call_tool(
        "prepare_application",
        {
            "application_id": application_id,
            "job_description": "Strong Python skills are essential.",
        },
    )

    assert result.is_error is False
    assert result.structured_content is not None

    content = result.structured_content

    assert content["started_new_analysis"] is True
    assert content["application"]["status"] == "ready_to_apply"
    assert content["preparation"]["status"] == "completed"

    assert content["analysis"] is not None
    assert content["analysis"]["status"] == "completed"
    assert content["analysis"]["job_id"] == application_id
    assert content["analysis"]["thread_id"] == "THR-MCP-PREPARE"
    assert content["analysis"]["fit_score"] == 0.82

    assert agent_engine_client.call_count == 1


@pytest.mark.anyio
async def test_prepare_application_replay_does_not_start_second_analysis(
    preparation_mcp_client,
) -> None:
    client, agent_engine_client = preparation_mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
            "idempotency_key": "prepare-replay-create-1",
        },
    )

    assert created.structured_content is not None

    arguments = {
        "application_id": created.structured_content["application_id"],
        "job_description": "Strong Python skills are essential.",
    }

    first = await client.call_tool(
        "prepare_application",
        arguments,
    )
    replay = await client.call_tool(
        "prepare_application",
        arguments,
    )

    assert first.is_error is False
    assert replay.is_error is False
    assert replay.structured_content is not None

    assert replay.structured_content["started_new_analysis"] is False
    assert replay.structured_content["preparation"]["status"] == "completed"
    assert replay.structured_content["analysis"] is None

    assert agent_engine_client.call_count == 1
