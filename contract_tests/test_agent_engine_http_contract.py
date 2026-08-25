import os

import httpx
import pytest

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineReviewAction,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineAnalysisNotFoundError,
    AgentEngineAuthenticationError,
    AgentEngineValidationError,
)
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)

_CONTRACT_SERVICE_KEY = "c" * 32
_DEFAULT_BASE_URL = "http://127.0.0.1:8011"


@pytest.fixture(scope="session")
def agent_engine_contract_base_url() -> str:
    base_url = os.getenv(
        "AGENT_ENGINE_CONTRACT_BASE_URL",
        _DEFAULT_BASE_URL,
    ).rstrip("/")

    try:
        response = httpx.get(
            f"{base_url}/health",
            timeout=2.0,
        )
    except httpx.RequestError as exc:
        pytest.fail(
            "Module 1 contract server is not running. "
            "Start agent_engine_contract_server.py first."
        )
        raise AssertionError from exc

    if response.status_code != 200:
        pytest.fail("Module 1 contract server health check failed.")

    return base_url


@pytest.mark.anyio
async def test_module2_matches_real_module1_job_analysis_contract(
    agent_engine_contract_base_url: str,
) -> None:
    async with httpx.AsyncClient(
        base_url=agent_engine_contract_base_url,
        timeout=5.0,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key=_CONTRACT_SERVICE_KEY,
        )

        paused = await client.analyse_job(
            user_id="USER-CONTRACT-001",
            job_id="JOB-CONTRACT-001",
            job_description=(
                "We require strong Python engineering and FastAPI experience."
            ),
        )

        assert paused.status is AgentEngineAnalysisStatus.AWAITING_REVIEW
        assert paused.job_id == "JOB-CONTRACT-001"
        assert paused.role_title == "Junior AI Engineer"
        assert paused.fit_score == 92.5

        assert paused.requirements[0].name == "Python"
        assert paused.evidence_matches[0].gap is False

        proposal_id = paused.cv_proposals[0].proposal_id

        assert paused.allowed_review_actions == (
            AgentEngineReviewAction.APPROVE,
            AgentEngineReviewAction.EDIT,
            AgentEngineReviewAction.REGENERATE,
            AgentEngineReviewAction.REJECT,
        )

        completed = await client.review_job_analysis(
            user_id="USER-CONTRACT-001",
            thread_id=paused.thread_id,
            decision=AgentEngineReviewDecision(
                action=AgentEngineReviewAction.APPROVE,
                approved_proposal_ids=(proposal_id,),
            ),
        )

    assert completed.status is AgentEngineAnalysisStatus.COMPLETED
    assert completed.thread_id == paused.thread_id
    assert completed.review_status == "approved"
    assert completed.allowed_review_actions == ()


@pytest.mark.anyio
async def test_real_module1_rejects_wrong_service_key(
    agent_engine_contract_base_url: str,
) -> None:
    async with httpx.AsyncClient(
        base_url=agent_engine_contract_base_url,
        timeout=5.0,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="x" * 32,
        )

        with pytest.raises(AgentEngineAuthenticationError):
            await client.analyse_job(
                user_id="USER-CONTRACT-001",
                job_id="JOB-AUTH-001",
                job_description=("Strong Python engineering required."),
            )


@pytest.mark.anyio
async def test_real_module1_validation_maps_to_module2_error(
    agent_engine_contract_base_url: str,
) -> None:
    async with httpx.AsyncClient(
        base_url=agent_engine_contract_base_url,
        timeout=5.0,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key=_CONTRACT_SERVICE_KEY,
        )

        with pytest.raises(AgentEngineValidationError):
            await client.analyse_job(
                user_id="USER-CONTRACT-001",
                job_id="",
                job_description=("Strong Python engineering required."),
            )


@pytest.mark.anyio
async def test_real_module1_preserves_user_scoping(
    agent_engine_contract_base_url: str,
) -> None:
    async with httpx.AsyncClient(
        base_url=agent_engine_contract_base_url,
        timeout=5.0,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key=_CONTRACT_SERVICE_KEY,
        )

        paused = await client.analyse_job(
            user_id="USER-CONTRACT-OWNER",
            job_id="JOB-SCOPE-001",
            job_description=("Strong Python engineering required."),
        )

        proposal_id = paused.cv_proposals[0].proposal_id

        with pytest.raises(AgentEngineAnalysisNotFoundError):
            await client.review_job_analysis(
                user_id="USER-CONTRACT-OTHER",
                thread_id=paused.thread_id,
                decision=AgentEngineReviewDecision(
                    action=(AgentEngineReviewAction.APPROVE),
                    approved_proposal_ids=(proposal_id,),
                ),
            )
