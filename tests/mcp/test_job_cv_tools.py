from typing import Any, cast

import pytest
from mcp import Client

from careerops_automation_mcp_hub.application.final_cv import (
    CVVersionMetadata,
    CVVersionStatus,
    FinalCVGenerationRequest,
    FinalCVVersion,
)
from careerops_automation_mcp_hub.application.job_analysis import (
    JobAnalysisCompleted,
    JobAnalysisReviewDecision,
    JobAnalysisStartRequest,
    JobReviewStatus,
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


def _analysis() -> JobAnalysisCompleted:
    return JobAnalysisCompleted(
        status="completed",
        thread_id="THR-MCP-001",
        job_id="JOB-MCP-001",
        role_title="AI Engineer",
        requirements=[],
        evidence_matches=[],
        fit_score=100.0,
        cv_proposals=[],
        claim_verification_reports=[],
        reviewable_proposal_ids=[],
        blocked_proposal_ids=[],
        audit_events=[],
        review_status=JobReviewStatus.APPROVED,
        final_cv_proposals=[],
    )


def _version(*, generated: bool) -> CVVersionMetadata | FinalCVVersion:
    values: dict[str, Any] = {
        "cv_version_id": "CVV-MCP-001",
        "cv_id": "CV-MCP-001",
        "version_number": 1,
        "parent_version_id": None,
        "status": CVVersionStatus.VERIFIED,
        "source_document_id": "DOC-MCP-001",
        "job_id": "JOB-MCP-001",
        "thread_id": "THR-MCP-001",
        "review_status": JobReviewStatus.APPROVED,
        "template_id": "careerops-default",
        "template_version": "1.0",
        "workflow_version": "1.0",
        "artifacts": [],
    }
    if generated:
        return FinalCVVersion(**values, reused_existing_version=False)
    return CVVersionMetadata(**values)


class _JobCVService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.review: JobAnalysisReviewDecision | None = None

    async def start_analysis(
        self,
        *,
        user_id: str,
        request: JobAnalysisStartRequest,
    ) -> JobAnalysisCompleted:
        self.user_ids.append(user_id)
        assert request.job_id == "JOB-MCP-001"
        return _analysis()

    async def recover_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> JobAnalysisCompleted:
        self.user_ids.append(user_id)
        assert thread_id == "THR-MCP-001"
        return _analysis()

    async def review_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: JobAnalysisReviewDecision,
    ) -> JobAnalysisCompleted:
        self.user_ids.append(user_id)
        self.review = decision
        assert thread_id == "THR-MCP-001"
        return _analysis()

    async def generate_final_cv(
        self,
        *,
        user_id: str,
        request: FinalCVGenerationRequest,
    ) -> FinalCVVersion:
        self.user_ids.append(user_id)
        assert request.source_document_id == "DOC-MCP-001"
        return cast(FinalCVVersion, _version(generated=True))

    async def get_final_cv(
        self,
        *,
        user_id: str,
        cv_version_id: str,
    ) -> CVVersionMetadata:
        self.user_ids.append(user_id)
        assert cv_version_id == "CVV-MCP-001"
        return _version(generated=False)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_job_cv_tools_preserve_principal_and_explicit_review() -> None:
    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=InMemoryJobApplicationRepository(),
        events=InMemoryApplicationEventRepository(),
        actions=InMemoryActionItemRepository(),
    )
    service = _JobCVService()
    server = build_mcp_server(
        principal_provider=StaticPrincipalProvider(
            Principal(user_id="USER-MCP-001", actor_id="MCP-TEST")
        ),
        unit_of_work_factory=unit_of_work_factory,
        prepare_application_service=cast(Any, object()),
        review_application_service=cast(Any, object()),
        get_application_analysis_service=cast(Any, object()),
        job_cv_gateway_service=cast(Any, service),
    )

    async with Client(server, raise_exceptions=True) as client:
        started = await client.call_tool(
            "start_job_analysis",
            {
                "job_id": "JOB-MCP-001",
                "job_description": "Build Python APIs.",
            },
        )
        recovered = await client.call_tool(
            "get_job_analysis",
            {"thread_id": "THR-MCP-001"},
        )
        reviewed = await client.call_tool(
            "review_job_analysis",
            {
                "thread_id": "THR-MCP-001",
                "decision": {
                    "action": "approve",
                    "approved_proposal_ids": ["CVP-MCP-001"],
                },
            },
        )
        generated = await client.call_tool(
            "generate_final_cv",
            {
                "thread_id": "THR-MCP-001",
                "source_document_id": "DOC-MCP-001",
            },
        )
        found = await client.call_tool(
            "get_final_cv",
            {"cv_version_id": "CVV-MCP-001"},
        )

    assert started.structured_content is not None
    assert started.structured_content["result"]["thread_id"] == "THR-MCP-001"
    assert recovered.structured_content is not None
    assert recovered.structured_content["result"]["status"] == "completed"
    assert reviewed.structured_content is not None
    assert reviewed.structured_content["result"]["review_status"] == "approved"
    assert generated.structured_content is not None
    assert generated.structured_content["reused_existing_version"] is False
    assert found.structured_content is not None
    assert found.structured_content["cv_version_id"] == "CVV-MCP-001"
    assert service.user_ids == ["USER-MCP-001"] * 5
    assert service.review is not None
    assert service.review.approved_proposal_ids == ["CVP-MCP-001"]
