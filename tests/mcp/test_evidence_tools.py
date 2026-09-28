from typing import Any, cast

import pytest
from mcp import Client

from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocument,
    EvidenceDocumentFormat,
    EvidenceDocumentStatus,
    EvidenceReviewDecision,
    EvidenceReviewRun,
    EvidenceReviewStatus,
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


class _EvidenceService:
    def __init__(self) -> None:
        self.user_id: str | None = None
        self.decision: EvidenceReviewDecision | None = None

    async def create_text_source(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
    ) -> EvidenceDocument:
        self.user_id = user_id
        assert title == "Career notes"
        assert content == "Built a FastAPI service."

        return EvidenceDocument(
            document_id="DOC-MCP-001",
            original_filename="Career notes.txt",
            document_format=EvidenceDocumentFormat.TEXT,
            media_type="text/plain; charset=utf-8",
            size_bytes=24,
            sha256_hex="a" * 64,
            status=EvidenceDocumentStatus.UPLOADED,
        )

    async def submit_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
        decision: EvidenceReviewDecision,
    ) -> EvidenceReviewRun:
        self.user_id = user_id
        self.decision = decision

        return EvidenceReviewRun(
            review_run_id=review_run_id,
            document_id="DOC-MCP-001",
            status=EvidenceReviewStatus.COMPLETED,
            proposals=[],
            overlap_findings=[],
            document_warnings=[],
            review_result=None,
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_evidence_tools_preserve_principal_and_explicit_decision() -> None:
    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=InMemoryJobApplicationRepository(),
        events=InMemoryApplicationEventRepository(),
        actions=InMemoryActionItemRepository(),
    )
    evidence_service = _EvidenceService()

    server = build_mcp_server(
        principal_provider=StaticPrincipalProvider(
            Principal(
                user_id="USER-MCP-001",
                actor_id="MCP-TEST",
            )
        ),
        unit_of_work_factory=unit_of_work_factory,
        prepare_application_service=cast(Any, object()),
        review_application_service=cast(Any, object()),
        get_application_analysis_service=cast(Any, object()),
        evidence_workflow_service=cast(Any, evidence_service),
    )

    async with Client(server, raise_exceptions=True) as client:
        created = await client.call_tool(
            "create_text_evidence_source",
            {
                "title": "Career notes",
                "content": "Built a FastAPI service.",
            },
        )
        reviewed = await client.call_tool(
            "submit_evidence_review",
            {
                "review_run_id": "EVR-MCP-001",
                "decision": {
                    "approved_proposal_ids": ["EVP-MCP-001"],
                    "rejected_proposal_ids": [],
                    "edits": [],
                    "duplicate_resolutions": [],
                    "reviewer_comment": "Confirmed against source.",
                },
            },
        )

    assert created.is_error is False
    assert created.structured_content is not None
    assert created.structured_content["document_id"] == "DOC-MCP-001"

    assert reviewed.is_error is False
    assert reviewed.structured_content is not None
    assert reviewed.structured_content["status"] == "completed"

    assert evidence_service.user_id == "USER-MCP-001"
    assert evidence_service.decision is not None
    assert evidence_service.decision.approved_proposal_ids == ["EVP-MCP-001"]
