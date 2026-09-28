from typing import Any, cast

import pytest
from mcp import Client

from careerops_automation_mcp_hub.application.evidence import (
    ApprovedEvidence,
    EvidenceCategory,
    EvidenceDocument,
    EvidenceDocumentFormat,
    EvidenceDocumentStatus,
    EvidenceLifecycleStatus,
    EvidenceRegistryEdit,
    EvidenceRegistryPage,
    EvidenceReviewDecision,
    EvidenceReviewRun,
    EvidenceReviewStatus,
    EvidenceSourceReference,
    EvidenceSourceType,
    EvidenceVerificationStatus,
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


def _approved_evidence(
    *,
    lifecycle_status: EvidenceLifecycleStatus = EvidenceLifecycleStatus.ACTIVE,
    title: str = "CareerOps",
) -> ApprovedEvidence:
    return ApprovedEvidence(
        evidence_id="EVD-MCP-001",
        category=EvidenceCategory.PROJECT,
        title=title,
        verification_status=EvidenceVerificationStatus.APPROVED,
        lifecycle_status=lifecycle_status,
        technologies=["Python"],
        capabilities=["API development"],
        approved_claims=["Built a Python API."],
        source_references=[
            EvidenceSourceReference(
                source_type=EvidenceSourceType.MANUAL_ENTRY,
                source_id="DOC-MCP-001",
                source_excerpt="Built a Python API.",
            )
        ],
    )


class _RegistryService:
    def __init__(self) -> None:
        self.user_ids: list[str] = []
        self.edit_request: EvidenceRegistryEdit | None = None

    async def query(
        self,
        *,
        user_id: str,
        query: str | None,
        category: EvidenceCategory | None,
        lifecycle_status: EvidenceLifecycleStatus,
        offset: int,
        limit: int,
    ) -> EvidenceRegistryPage:
        self.user_ids.append(user_id)
        assert query == "python"
        assert category is EvidenceCategory.PROJECT
        assert lifecycle_status is EvidenceLifecycleStatus.ACTIVE
        assert offset == 0
        assert limit == 10
        return EvidenceRegistryPage(
            items=[_approved_evidence()],
            count=1,
            total=1,
            offset=0,
            limit=10,
            has_more=False,
        )

    async def get(self, *, user_id: str, evidence_id: str) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-MCP-001"
        return _approved_evidence()

    async def edit(
        self,
        *,
        user_id: str,
        evidence_id: str,
        edit: EvidenceRegistryEdit,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        self.edit_request = edit
        assert evidence_id == "EVD-MCP-001"
        return _approved_evidence(title=edit.title or "CareerOps")

    async def archive(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-MCP-001"
        return _approved_evidence(lifecycle_status=EvidenceLifecycleStatus.ARCHIVED)

    async def restore(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-MCP-001"
        return _approved_evidence()


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


@pytest.mark.anyio
async def test_registry_tools_preserve_principal_filters_and_mutation_intent() -> None:
    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=InMemoryJobApplicationRepository(),
        events=InMemoryApplicationEventRepository(),
        actions=InMemoryActionItemRepository(),
    )
    registry_service = _RegistryService()

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
        evidence_registry_service=cast(Any, registry_service),
    )

    async with Client(server, raise_exceptions=True) as client:
        searched = await client.call_tool(
            "search_evidence_registry",
            {
                "query": "python",
                "category": "project",
                "lifecycle_status": "active",
                "offset": 0,
                "limit": 10,
            },
        )
        found = await client.call_tool(
            "get_registry_evidence",
            {"evidence_id": "EVD-MCP-001"},
        )
        edited = await client.call_tool(
            "edit_registry_evidence",
            {
                "evidence_id": "EVD-MCP-001",
                "edit": {"title": "CareerOps Platform"},
            },
        )
        archived = await client.call_tool(
            "archive_registry_evidence",
            {"evidence_id": "EVD-MCP-001"},
        )
        restored = await client.call_tool(
            "restore_registry_evidence",
            {"evidence_id": "EVD-MCP-001"},
        )

    assert searched.structured_content is not None
    assert searched.structured_content["total"] == 1
    assert found.structured_content is not None
    assert found.structured_content["evidence_id"] == "EVD-MCP-001"
    assert edited.structured_content is not None
    assert edited.structured_content["title"] == "CareerOps Platform"
    assert archived.structured_content is not None
    assert archived.structured_content["lifecycle_status"] == "archived"
    assert restored.structured_content is not None
    assert restored.structured_content["lifecycle_status"] == "active"
    assert registry_service.user_ids == ["USER-MCP-001"] * 5
    assert registry_service.edit_request == EvidenceRegistryEdit(
        title="CareerOps Platform"
    )
