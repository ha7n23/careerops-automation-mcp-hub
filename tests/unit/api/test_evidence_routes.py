from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from careerops_automation_mcp_hub.api.evidence import build_evidence_router
from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocument,
    EvidenceDocumentFormat,
    EvidenceDocumentStatus,
)


class _TokenVerifier:
    def __init__(
        self,
        *,
        scopes: list[str] | None = None,
    ) -> None:
        self._scopes = scopes or ["careerops:applications"]

    async def verify_token(self, token: str) -> AccessToken | None:
        if token != "valid-token":
            return None

        return AccessToken(
            token=token,
            client_id="module-3",
            scopes=self._scopes,
            expires_at=2_000_000_000,
            resource="careerops-automation-mcp-hub",
            subject="USER-HTTP-001",
            claims={},
        )


class _EvidenceService:
    def __init__(self) -> None:
        self.user_id: str | None = None

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
            document_id="DOC-HTTP-001",
            original_filename="Career notes.txt",
            document_format=EvidenceDocumentFormat.TEXT,
            media_type="text/plain; charset=utf-8",
            size_bytes=24,
            sha256_hex="a" * 64,
            status=EvidenceDocumentStatus.UPLOADED,
        )

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"Unexpected evidence service call: {name}")


def _build_app(
    *,
    service: _EvidenceService,
    verifier: _TokenVerifier,
) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_evidence_router(
            service=service,  # type: ignore[arg-type]
            token_verifier=verifier,  # type: ignore[arg-type]
            required_scope="careerops:applications",
        )
    )
    return app


def test_evidence_gateway_requires_bearer_authentication() -> None:
    app = _build_app(
        service=_EvidenceService(),
        verifier=_TokenVerifier(),
    )

    with TestClient(app) as client:
        response = client.get("/api/v1/cv-documents")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_evidence_gateway_requires_careerops_scope() -> None:
    app = _build_app(
        service=_EvidenceService(),
        verifier=_TokenVerifier(scopes=["unrelated:scope"]),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/cv-documents",
            headers={"Authorization": "Bearer valid-token"},
        )

    assert response.status_code == 403


def test_text_evidence_gateway_derives_user_from_verified_token() -> None:
    service = _EvidenceService()
    app = _build_app(
        service=service,
        verifier=_TokenVerifier(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/cv-documents/text",
            headers={"Authorization": "Bearer valid-token"},
            json={
                "title": "Career notes",
                "content": "Built a FastAPI service.",
            },
        )

    assert response.status_code == 201
    assert response.json()["document_id"] == "DOC-HTTP-001"
    assert service.user_id == "USER-HTTP-001"
