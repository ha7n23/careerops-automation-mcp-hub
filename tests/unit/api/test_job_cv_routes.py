from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from careerops_automation_mcp_hub.api.job_cv import build_job_cv_router
from careerops_automation_mcp_hub.application.final_cv import (
    CVArtifactDownload,
    CVArtifactFormat,
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


class _TokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-token":
            return None

        return AccessToken(
            token=token,
            client_id="module-3",
            scopes=["careerops:applications"],
            expires_at=2_000_000_000,
            resource="careerops-automation-mcp-hub",
            subject="USER-HTTP-001",
            claims={},
        )


def _analysis() -> JobAnalysisCompleted:
    return JobAnalysisCompleted(
        status="completed",
        thread_id="THR-001",
        job_id="JOB-001",
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
        "cv_version_id": "CVV-001",
        "cv_id": "CV-001",
        "version_number": 1,
        "parent_version_id": None,
        "status": CVVersionStatus.VERIFIED,
        "source_document_id": "DOC-001",
        "job_id": "JOB-001",
        "thread_id": "THR-001",
        "review_status": JobReviewStatus.APPROVED,
        "template_id": "careerops-default",
        "template_version": "1.0",
        "workflow_version": "1.0",
        "artifacts": [],
    }
    if generated:
        return FinalCVVersion(**values, reused_existing_version=False)
    return CVVersionMetadata(**values)


class _GatewayService:
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
        assert request.job_id == "JOB-001"
        return _analysis()

    async def recover_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> JobAnalysisCompleted:
        self.user_ids.append(user_id)
        assert thread_id == "THR-001"
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
        assert thread_id == "THR-001"
        return _analysis()

    async def generate_final_cv(
        self,
        *,
        user_id: str,
        request: FinalCVGenerationRequest,
    ) -> FinalCVVersion:
        self.user_ids.append(user_id)
        assert request.source_document_id == "DOC-001"
        return cast(FinalCVVersion, _version(generated=True))

    async def get_final_cv(
        self,
        *,
        user_id: str,
        cv_version_id: str,
    ) -> CVVersionMetadata:
        self.user_ids.append(user_id)
        assert cv_version_id == "CVV-001"
        return _version(generated=False)

    async def download_final_cv_artifact(
        self,
        *,
        user_id: str,
        cv_version_id: str,
        artifact_format: CVArtifactFormat,
    ) -> CVArtifactDownload:
        self.user_ids.append(user_id)
        assert cv_version_id == "CVV-001"
        assert artifact_format is CVArtifactFormat.PDF
        return CVArtifactDownload(
            data=b"%PDF-careerops",
            media_type="application/pdf",
            content_disposition='attachment; filename="careerops.pdf"',
        )


def _build_app(service: _GatewayService) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_job_cv_router(
            service=cast(Any, service),
            token_verifier=cast(Any, _TokenVerifier()),
            required_scope="careerops:applications",
        )
    )
    return app


def test_job_cv_gateway_requires_bearer_authentication() -> None:
    with TestClient(_build_app(_GatewayService())) as client:
        response = client.post(
            "/api/v1/job-analysis",
            json={"job_id": "JOB-001", "job_description": "Python APIs"},
        )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_job_cv_gateway_preserves_verified_user_and_binary_download() -> None:
    service = _GatewayService()
    headers = {"Authorization": "Bearer valid-token"}

    with TestClient(_build_app(service)) as client:
        started = client.post(
            "/api/v1/job-analysis",
            headers=headers,
            json={"job_id": "JOB-001", "job_description": "Python APIs"},
        )
        recovered = client.get(
            "/api/v1/job-analysis/THR-001",
            headers=headers,
        )
        reviewed = client.post(
            "/api/v1/job-analysis/THR-001/review",
            headers=headers,
            json={"action": "approve", "approved_proposal_ids": ["CVP-001"]},
        )
        generated = client.post(
            "/api/v1/cv-versions",
            headers=headers,
            json={"thread_id": "THR-001", "source_document_id": "DOC-001"},
        )
        found = client.get("/api/v1/cv-versions/CVV-001", headers=headers)
        downloaded = client.get(
            "/api/v1/cv-versions/CVV-001/artifacts/pdf",
            headers=headers,
        )

    assert started.status_code == 200
    assert recovered.status_code == 200
    assert reviewed.status_code == 200
    assert generated.json()["reused_existing_version"] is False
    assert found.json()["cv_version_id"] == "CVV-001"
    assert downloaded.content == b"%PDF-careerops"
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.headers["content-disposition"] == (
        'attachment; filename="careerops.pdf"'
    )
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert service.user_ids == ["USER-HTTP-001"] * 6
    assert service.review is not None
    assert service.review.approved_proposal_ids == ["CVP-001"]
