from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken

from careerops_automation_mcp_hub.api.evidence import build_evidence_router
from careerops_automation_mcp_hub.application.evidence import (
    ApprovedEvidence,
    EvidenceCategory,
    EvidenceLifecycleStatus,
    EvidenceRegistryEdit,
    EvidenceRegistryPage,
    EvidenceSourceReference,
    EvidenceSourceType,
    EvidenceVerificationStatus,
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


def _evidence(
    *,
    lifecycle_status: EvidenceLifecycleStatus = EvidenceLifecycleStatus.ACTIVE,
    title: str = "CareerOps",
) -> ApprovedEvidence:
    return ApprovedEvidence(
        evidence_id="EVD-HTTP-001",
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
                source_id="DOC-HTTP-001",
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
        assert query == "python api"
        assert category is EvidenceCategory.PROJECT
        assert lifecycle_status is EvidenceLifecycleStatus.ARCHIVED
        assert offset == 10
        assert limit == 5

        return EvidenceRegistryPage(
            items=[_evidence(lifecycle_status=EvidenceLifecycleStatus.ARCHIVED)],
            count=1,
            total=11,
            offset=10,
            limit=5,
            has_more=False,
        )

    async def get(self, *, user_id: str, evidence_id: str) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-HTTP-001"
        return _evidence()

    async def edit(
        self,
        *,
        user_id: str,
        evidence_id: str,
        edit: EvidenceRegistryEdit,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        self.edit_request = edit
        assert evidence_id == "EVD-HTTP-001"
        return _evidence(title=edit.title or "CareerOps")

    async def archive(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-HTTP-001"
        return _evidence(lifecycle_status=EvidenceLifecycleStatus.ARCHIVED)

    async def restore(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        self.user_ids.append(user_id)
        assert evidence_id == "EVD-HTTP-001"
        return _evidence()


def _build_app(service: _RegistryService) -> FastAPI:
    app = FastAPI()
    app.include_router(
        build_evidence_router(
            service=cast(Any, object()),
            registry_service=cast(Any, service),
            token_verifier=cast(Any, _TokenVerifier()),
            required_scope="careerops:applications",
        )
    )
    return app


def test_registry_gateway_forwards_filters_and_verified_user() -> None:
    service = _RegistryService()

    with TestClient(_build_app(service)) as client:
        response = client.get(
            "/api/v1/evidence",
            headers={"Authorization": "Bearer valid-token"},
            params={
                "q": "python api",
                "category": "project",
                "lifecycle_status": "archived",
                "offset": 10,
                "limit": 5,
            },
        )

    assert response.status_code == 200
    assert response.json()["total"] == 11
    assert response.json()["items"][0]["lifecycle_status"] == "archived"
    assert service.user_ids == ["USER-HTTP-001"]


def test_registry_gateway_exposes_detail_edit_and_recoverable_lifecycle() -> None:
    service = _RegistryService()
    headers = {"Authorization": "Bearer valid-token"}

    with TestClient(_build_app(service)) as client:
        found = client.get("/api/v1/evidence/EVD-HTTP-001", headers=headers)
        edited = client.patch(
            "/api/v1/evidence/EVD-HTTP-001",
            headers=headers,
            json={"title": "CareerOps Platform"},
        )
        archived = client.post(
            "/api/v1/evidence/EVD-HTTP-001/archive",
            headers=headers,
        )
        restored = client.post(
            "/api/v1/evidence/EVD-HTTP-001/restore",
            headers=headers,
        )
        invalid = client.patch(
            "/api/v1/evidence/EVD-HTTP-001",
            headers=headers,
            json={},
        )

    assert found.status_code == 200
    assert edited.json()["title"] == "CareerOps Platform"
    assert archived.json()["lifecycle_status"] == "archived"
    assert restored.json()["lifecycle_status"] == "active"
    assert invalid.status_code == 422
    assert service.edit_request == EvidenceRegistryEdit(title="CareerOps Platform")
    assert service.user_ids == ["USER-HTTP-001"] * 4
