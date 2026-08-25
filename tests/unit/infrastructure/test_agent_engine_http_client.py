import json

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
    AgentEngineContractError,
    AgentEngineUnavailableError,
    AgentEngineValidationError,
)
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


def _awaiting_review_payload() -> dict[str, object]:
    return {
        "status": "awaiting_review",
        "thread_id": "THR-001",
        "job_id": "JOB-001",
        "role_title": "Junior AI Engineer",
        "requirements": [
            {
                "requirement_id": "REQ-001",
                "name": "Python",
                "category": "essential",
                "importance_score": 5,
            }
        ],
        "evidence_matches": [
            {
                "requirement_id": "REQ-001",
                "match_strength": "strong",
                "explanation": "Approved evidence supports Python.",
                "gap": False,
            }
        ],
        "fit_score": 92.5,
        "cv_proposals": [
            {
                "proposal_id": "CVP-001",
                "section": "projects",
                "current_text": None,
                "proposed_text": "Built a tested Python AI service.",
                "confidence_score": 0.95,
                "warnings": [],
            }
        ],
        "reviewable_proposal_ids": ["CVP-001"],
        "blocked_proposal_ids": [],
        "review": {
            "allowed_actions": [
                "approve",
                "reject",
            ]
        },
    }


def _completed_payload() -> dict[str, object]:
    payload = _awaiting_review_payload()

    payload.pop("review")

    payload["status"] = "completed"
    payload["review_status"] = "approved"

    return payload


@pytest.mark.anyio
async def test_analyse_job_maps_awaiting_review_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/api/v1/job-analysis"

        assert request.headers["X-CareerOps-Service-Key"] == "test-service-key"
        assert request.headers["X-User-ID"] == "USER-001"

        body = json.loads(request.content)

        assert body == {
            "job_id": "JOB-001",
            "job_description": "Strong Python required.",
        }

        return httpx.Response(
            200,
            json=_awaiting_review_payload(),
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        result = await client.analyse_job(
            user_id="USER-001",
            job_id="JOB-001",
            job_description="Strong Python required.",
        )

    assert result.status is AgentEngineAnalysisStatus.AWAITING_REVIEW
    assert result.thread_id == "THR-001"
    assert result.job_id == "JOB-001"
    assert result.fit_score == 92.5

    assert result.requirements[0].name == "Python"
    assert result.evidence_matches[0].gap is False
    assert result.cv_proposals[0].proposal_id == "CVP-001"

    assert result.allowed_review_actions == (
        AgentEngineReviewAction.APPROVE,
        AgentEngineReviewAction.REJECT,
    )
    assert result.review_status is None


@pytest.mark.anyio
async def test_review_job_analysis_maps_completed_response() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.url.path == "/api/v1/job-analysis/THR-001/review"

        body = json.loads(request.content)

        assert body == {
            "action": "approve",
            "approved_proposal_ids": ["CVP-001"],
            "rejected_proposal_ids": [],
            "edits": [],
            "reviewer_comment": "Looks good.",
        }

        return httpx.Response(
            200,
            json=_completed_payload(),
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        result = await client.review_job_analysis(
            user_id="USER-001",
            thread_id="THR-001",
            decision=AgentEngineReviewDecision(
                action=AgentEngineReviewAction.APPROVE,
                approved_proposal_ids=("CVP-001",),
                reviewer_comment="Looks good.",
            ),
        )

    assert result.status is AgentEngineAnalysisStatus.COMPLETED
    assert result.review_status == "approved"
    assert result.allowed_review_actions == ()


@pytest.mark.anyio
async def test_agent_engine_validation_error_preserves_detail() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": "The job description is invalid.",
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        with pytest.raises(
            AgentEngineValidationError,
            match="job description is invalid",
        ):
            await client.analyse_job(
                user_id="USER-001",
                job_id="JOB-001",
                job_description="Invalid",
            )


@pytest.mark.anyio
async def test_agent_engine_authentication_error_is_mapped() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            json={"detail": "Missing or invalid service credentials."},
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="wrong-key",
        )

        with pytest.raises(AgentEngineAuthenticationError):
            await client.analyse_job(
                user_id="USER-001",
                job_id="JOB-001",
                job_description="Strong Python required.",
            )


@pytest.mark.anyio
async def test_agent_engine_missing_analysis_is_mapped() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            404,
            json={"detail": "Job-analysis thread is unavailable."},
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        with pytest.raises(AgentEngineAnalysisNotFoundError):
            await client.review_job_analysis(
                user_id="USER-001",
                thread_id="THR-MISSING",
                decision=AgentEngineReviewDecision(
                    action=AgentEngineReviewAction.REJECT,
                    rejected_proposal_ids=("CVP-001",),
                ),
            )


@pytest.mark.anyio
async def test_invalid_success_response_raises_contract_error() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "awaiting_review",
                "unexpected": "payload",
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        with pytest.raises(AgentEngineContractError):
            await client.analyse_job(
                user_id="USER-001",
                job_id="JOB-001",
                job_description="Strong Python required.",
            )


@pytest.mark.anyio
async def test_transport_failure_maps_to_unavailable() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "Connection failed.",
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key="test-service-key",
        )

        with pytest.raises(AgentEngineUnavailableError):
            await client.analyse_job(
                user_id="USER-001",
                job_id="JOB-001",
                job_description="Strong Python required.",
            )
