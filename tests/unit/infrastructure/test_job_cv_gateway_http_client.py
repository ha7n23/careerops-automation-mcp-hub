import json

import httpx
import pytest

from careerops_automation_mcp_hub.application.final_cv import (
    CVArtifactFormat,
    FinalCVGenerationRequest,
)
from careerops_automation_mcp_hub.application.job_analysis import (
    JobAnalysisCompleted,
    JobAnalysisReviewDecision,
    JobAnalysisStartRequest,
    JobReviewAction,
)
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


def _proposal() -> dict[str, object]:
    return {
        "proposal_id": "CVP-001",
        "section": "projects",
        "target_entry_id": "project-1",
        "current_text": "Built APIs.",
        "proposed_text": "Built production Python APIs with FastAPI.",
        "requirement_ids": ["REQ-001"],
        "supporting_evidence_ids": ["EVD-001"],
        "confidence_score": 0.95,
        "warnings": [],
        "requires_human_approval": True,
    }


def _verification_report() -> dict[str, object]:
    return {
        "proposal_id": "CVP-001",
        "claims": [
            {
                "claim_text": "Built production Python APIs with FastAPI.",
                "supported": True,
                "supporting_evidence_ids": ["EVD-001"],
                "explanation": "Directly supported by approved evidence.",
            }
        ],
        "coverage_complete": True,
        "coverage_notes": [],
        "fully_supported": True,
        "unsupported_claims": [],
    }


def _analysis_payload(*, completed: bool = False) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "completed" if completed else "awaiting_review",
        "thread_id": "THR-001",
        "job_id": "JOB-001",
        "role_title": "AI Engineer",
        "requirements": [
            {
                "requirement_id": "REQ-001",
                "name": "Python API development",
                "category": "essential",
                "evidence_expected": "Production Python API experience.",
                "importance_score": 5,
                "source_text": "Build Python APIs with FastAPI.",
            }
        ],
        "evidence_matches": [
            {
                "requirement_id": "REQ-001",
                "match_strength": "strong",
                "direct_evidence_ids": ["EVD-001"],
                "related_evidence_ids": [],
                "explanation": "Approved project evidence is a direct match.",
                "gap": False,
            }
        ],
        "fit_score": 100.0,
        "cv_proposals": [_proposal()],
        "claim_verification_reports": [_verification_report()],
        "reviewable_proposal_ids": ["CVP-001"],
        "blocked_proposal_ids": [],
        "audit_events": [{"node": "human_review", "event": "paused"}],
    }

    if completed:
        payload["review_status"] = "approved"
        payload["final_cv_proposals"] = [_proposal()]
    else:
        payload["review"] = {
            "type": "cv_proposal_review",
            "proposals": [_proposal()],
            "verification_reports": [_verification_report()],
            "allowed_actions": ["approve", "edit", "reject", "regenerate"],
        }

    return payload


def _cv_version_payload(*, generated: bool) -> dict[str, object]:
    payload: dict[str, object] = {
        "cv_version_id": "CVV-001",
        "cv_id": "CV-001",
        "version_number": 1,
        "parent_version_id": None,
        "status": "verified",
        "source_document_id": "DOC-001",
        "job_id": "JOB-001",
        "thread_id": "THR-001",
        "review_status": "approved",
        "template_id": "careerops-default",
        "template_version": "1.0",
        "workflow_version": "1.0",
        "artifacts": [
            {
                "artifact_id": "ART-001",
                "artifact_format": "pdf",
                "size_bytes": 12,
                "sha256_hex": "a" * 64,
                "verification_status": "verified",
            }
        ],
    }
    if generated:
        payload["reused_existing_version"] = False
    return payload


@pytest.mark.anyio
async def test_full_job_analysis_contract_start_recover_and_review() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["X-CareerOps-Service-Key"] == "service-key"
        assert request.headers["X-User-ID"] == "USER-001"

        if request.url.path == "/api/v1/job-analysis":
            assert json.loads(request.content) == {
                "job_id": "JOB-001",
                "job_description": "Build Python APIs with FastAPI.",
            }
            return httpx.Response(200, json=_analysis_payload())

        if request.url.path.endswith("/review"):
            body = json.loads(request.content)
            assert body["action"] == "approve"
            assert body["approved_proposal_ids"] == ["CVP-001"]
            return httpx.Response(200, json=_analysis_payload(completed=True))

        return httpx.Response(200, json=_analysis_payload())

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")
        started = await client.start_job_analysis(
            user_id="USER-001",
            request=JobAnalysisStartRequest(
                job_id="JOB-001",
                job_description="Build Python APIs with FastAPI.",
            ),
        )
        recovered = await client.recover_job_analysis(
            user_id="USER-001",
            thread_id="THR-001",
        )
        reviewed = await client.submit_job_analysis_review(
            user_id="USER-001",
            thread_id="THR-001",
            decision=JobAnalysisReviewDecision(
                action=JobReviewAction.APPROVE,
                approved_proposal_ids=["CVP-001"],
            ),
        )

    assert calls == [
        ("POST", "/api/v1/job-analysis"),
        ("GET", "/api/v1/job-analysis/THR-001"),
        ("POST", "/api/v1/job-analysis/THR-001/review"),
    ]
    assert started.evidence_matches[0].direct_evidence_ids == ["EVD-001"]
    assert recovered.claim_verification_reports[0].fully_supported is True
    assert isinstance(reviewed, JobAnalysisCompleted)
    assert reviewed.final_cv_proposals[0].proposal_id == "CVP-001"


@pytest.mark.anyio
async def test_final_cv_generation_and_metadata_follow_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-User-ID"] == "USER-001"
        if request.method == "POST":
            assert json.loads(request.content) == {
                "thread_id": "THR-001",
                "source_document_id": "DOC-001",
            }
            return httpx.Response(200, json=_cv_version_payload(generated=True))
        return httpx.Response(200, json=_cv_version_payload(generated=False))

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")
        generated = await client.generate_final_cv(
            user_id="USER-001",
            request=FinalCVGenerationRequest(
                thread_id="THR-001",
                source_document_id="DOC-001",
            ),
        )
        found = await client.get_final_cv(
            user_id="USER-001",
            cv_version_id="CVV-001",
        )

    assert generated.reused_existing_version is False
    assert generated.artifacts[0].verification_status == "verified"
    assert found.cv_version_id == "CVV-001"


@pytest.mark.anyio
async def test_final_cv_download_validates_and_preserves_verified_artifact() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/cv-versions/CVV-001/artifacts/pdf"
        assert request.headers["X-User-ID"] == "USER-001"
        return httpx.Response(
            200,
            content=b"%PDF-careerops",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="careerops.pdf"',
            },
        )

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")
        artifact = await client.download_final_cv_artifact(
            user_id="USER-001",
            cv_version_id="CVV-001",
            artifact_format=CVArtifactFormat.PDF,
        )

    assert artifact.data == b"%PDF-careerops"
    assert artifact.media_type == "application/pdf"
    assert artifact.content_disposition == 'attachment; filename="careerops.pdf"'
