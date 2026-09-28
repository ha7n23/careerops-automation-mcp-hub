import json

import httpx
import pytest

from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocumentFormat,
    EvidenceDuplicateAction,
    EvidenceDuplicateResolution,
    EvidenceOverlapScope,
    EvidenceReviewDecision,
    EvidenceReviewStatus,
)
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


def _document_payload() -> dict[str, object]:
    return {
        "document_id": "DOC-001",
        "original_filename": "Career notes.txt",
        "document_format": "text",
        "media_type": "text/plain; charset=utf-8",
        "size_bytes": 41,
        "sha256_hex": "a" * 64,
        "status": "uploaded",
    }


def _review_payload(
    *,
    status: str = "awaiting_review",
) -> dict[str, object]:
    review_result: dict[str, object] | None = None

    if status == "completed":
        review_result = {
            "approved_proposal_ids": ["EVP-001"],
            "edited_proposal_ids": [],
            "rejected_proposal_ids": [],
            "duplicate_resolutions": [
                {
                    "proposal_id": "EVP-001",
                    "scope": "approved_evidence",
                    "action": "merge_into_existing",
                    "matching_proposal_id": None,
                    "matching_evidence_id": "EVD-001",
                }
            ],
            "approved_evidence": [],
            "evidence_updates": [
                {
                    "proposal_id": "EVP-001",
                    "action": "merge_into_existing",
                    "before": _approved_evidence_payload(),
                    "after": _approved_evidence_payload(),
                }
            ],
        }

    return {
        "review_run_id": "EVR-001",
        "document_id": "DOC-001",
        "status": status,
        "proposals": [
            {
                "proposal_id": "EVP-001",
                "category": "project",
                "title": "CareerOps",
                "verification_status": "pending",
                "source_section": "projects",
                "source_section_order_index": 0,
                "technologies": ["Python", "FastAPI"],
                "capabilities": ["API development"],
                "claims": ["Built a FastAPI service."],
                "source_references": [
                    {
                        "source_type": "manual_entry",
                        "source_id": "DOC-001",
                        "page_number": None,
                        "source_excerpt": "Built a FastAPI service.",
                    }
                ],
                "warnings": [],
            }
        ],
        "overlap_findings": [
            {
                "proposal_id": "EVP-001",
                "scope": "approved_evidence",
                "matching_proposal_id": None,
                "matching_evidence_id": "EVD-001",
                "matched_claims": ["Built a FastAPI service."],
                "same_source_excerpt": False,
                "allowed_actions": [
                    "keep_existing",
                    "accept_separate",
                    "replace_existing",
                    "merge_into_existing",
                ],
            }
        ],
        "document_warnings": [],
        "review_result": review_result,
    }


def _approved_evidence_payload() -> dict[str, object]:
    return {
        "evidence_id": "EVD-001",
        "category": "project",
        "title": "CareerOps",
        "verification_status": "approved",
        "lifecycle_status": "active",
        "technologies": ["Python", "FastAPI"],
        "capabilities": ["API development"],
        "approved_claims": ["Built a FastAPI service."],
        "source_references": [
            {
                "source_type": "manual_entry",
                "source_id": "DOC-001",
                "page_number": None,
                "source_excerpt": "Built a FastAPI service.",
            }
        ],
    }


@pytest.mark.anyio
async def test_text_source_review_and_duplicate_decision_follow_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-CareerOps-Service-Key"] == "service-key"
        assert request.headers["X-User-ID"] == "USER-001"

        if request.url.path == "/api/v1/cv-documents/text":
            assert json.loads(request.content) == {
                "title": "Career notes",
                "content": "Built a FastAPI service.",
            }
            return httpx.Response(201, json=_document_payload())

        if request.url.path == "/api/v1/cv-documents/DOC-001/evidence-review":
            return httpx.Response(200, json=_review_payload())

        assert request.url.path == "/api/v1/cv-evidence-reviews/EVR-001/review"
        body = json.loads(request.content)
        assert body["approved_proposal_ids"] == ["EVP-001"]
        assert body["duplicate_resolutions"][0]["action"] == "merge_into_existing"
        return httpx.Response(200, json=_review_payload(status="completed"))

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")

        document = await client.create_text_evidence_source(
            user_id="USER-001",
            title="Career notes",
            content="Built a FastAPI service.",
        )
        pending = await client.start_evidence_review(
            user_id="USER-001",
            document_id=document.document_id,
        )
        completed = await client.submit_evidence_review(
            user_id="USER-001",
            review_run_id=pending.review_run_id,
            decision=EvidenceReviewDecision(
                approved_proposal_ids=["EVP-001"],
                duplicate_resolutions=[
                    EvidenceDuplicateResolution(
                        proposal_id="EVP-001",
                        scope=EvidenceOverlapScope.APPROVED_EVIDENCE,
                        action=EvidenceDuplicateAction.MERGE_INTO_EXISTING,
                        matching_evidence_id="EVD-001",
                    )
                ],
            ),
        )

    assert document.document_format is EvidenceDocumentFormat.TEXT
    assert pending.status is EvidenceReviewStatus.AWAITING_REVIEW
    assert pending.overlap_findings[0].matching_evidence_id == "EVD-001"
    assert completed.status is EvidenceReviewStatus.COMPLETED
    assert completed.review_result is not None
    assert len(completed.review_result.evidence_updates) == 1


@pytest.mark.anyio
async def test_binary_document_upload_uses_multipart_and_user_scope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        content_type = request.headers["content-type"]
        assert content_type.startswith("multipart/form-data; boundary=")
        assert b'filename="candidate.pdf"' in request.content
        assert b"application/pdf" in request.content
        assert b"%PDF-test" in request.content
        assert request.headers["X-User-ID"] == "USER-001"

        payload = _document_payload()
        payload["original_filename"] = "candidate.pdf"
        payload["document_format"] = "pdf"
        payload["media_type"] = "application/pdf"
        return httpx.Response(201, json=payload)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")
        result = await client.upload_evidence_document(
            user_id="USER-001",
            filename="candidate.pdf",
            media_type="application/pdf",
            data=b"%PDF-test",
        )

    assert result.document_format is EvidenceDocumentFormat.PDF


@pytest.mark.anyio
async def test_evidence_history_and_review_recovery_are_typed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/cv-documents":
            assert request.url.params["limit"] == "10"
            return httpx.Response(
                200,
                json={"items": [], "count": 0, "limit": 10},
            )

        if request.url.path == "/api/v1/cv-evidence-reviews":
            assert request.url.params["limit"] == "5"
            return httpx.Response(
                200,
                json={"items": [], "count": 0, "limit": 5},
            )

        assert request.url.path == "/api/v1/cv-evidence-reviews/EVR-001"
        return httpx.Response(200, json=_review_payload())

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")

        documents = await client.list_evidence_documents(
            user_id="USER-001",
            limit=10,
        )
        reviews = await client.list_evidence_reviews(
            user_id="USER-001",
            limit=5,
        )
        review = await client.get_evidence_review(
            user_id="USER-001",
            review_run_id="EVR-001",
        )

    assert documents.count == 0
    assert reviews.count == 0
    assert review.review_run_id == "EVR-001"
