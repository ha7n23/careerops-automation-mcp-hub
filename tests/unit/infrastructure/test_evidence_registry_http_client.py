import json

import httpx
import pytest

from careerops_automation_mcp_hub.application.evidence import (
    EvidenceCategory,
    EvidenceLifecycleStatus,
    EvidenceRegistryEdit,
)
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


def _evidence_payload(
    *,
    lifecycle_status: str = "active",
    title: str = "CareerOps",
) -> dict[str, object]:
    return {
        "evidence_id": "EVD-001",
        "category": "project",
        "title": title,
        "verification_status": "approved",
        "lifecycle_status": lifecycle_status,
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
async def test_registry_query_forwards_filters_pagination_and_user_scope() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/v1/evidence"
        assert request.headers["X-CareerOps-Service-Key"] == "service-key"
        assert request.headers["X-User-ID"] == "USER-001"
        assert dict(request.url.params) == {
            "q": "python api",
            "category": "project",
            "lifecycle_status": "archived",
            "offset": "20",
            "limit": "10",
        }

        return httpx.Response(
            200,
            json={
                "items": [_evidence_payload(lifecycle_status="archived")],
                "count": 1,
                "total": 21,
                "offset": 20,
                "limit": 10,
                "has_more": False,
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")
        result = await client.query_evidence_registry(
            user_id="USER-001",
            query="python api",
            category=EvidenceCategory.PROJECT,
            lifecycle_status=EvidenceLifecycleStatus.ARCHIVED,
            offset=20,
            limit=10,
        )

    assert result.count == 1
    assert result.total == 21
    assert result.items[0].lifecycle_status is EvidenceLifecycleStatus.ARCHIVED


@pytest.mark.anyio
async def test_registry_detail_edit_archive_and_restore_follow_contract() -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["X-User-ID"] == "USER-001"

        if request.method == "PATCH":
            assert json.loads(request.content) == {
                "title": "CareerOps Platform",
                "technologies": ["Python", "FastAPI"],
            }
            return httpx.Response(
                200,
                json=_evidence_payload(title="CareerOps Platform"),
            )

        if request.url.path.endswith("/archive"):
            return httpx.Response(
                200,
                json=_evidence_payload(lifecycle_status="archived"),
            )

        return httpx.Response(200, json=_evidence_payload())

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        base_url="http://agent-engine.test",
        transport=transport,
    ) as http_client:
        client = HttpAgentEngineClient(http_client, service_key="service-key")

        found = await client.get_evidence(
            user_id="USER-001",
            evidence_id="EVD-001",
        )
        edited = await client.edit_evidence(
            user_id="USER-001",
            evidence_id="EVD-001",
            edit=EvidenceRegistryEdit(
                title="CareerOps Platform",
                technologies=["Python", "FastAPI"],
            ),
        )
        archived = await client.archive_evidence(
            user_id="USER-001",
            evidence_id="EVD-001",
        )
        restored = await client.restore_evidence(
            user_id="USER-001",
            evidence_id="EVD-001",
        )

    assert calls == [
        ("GET", "/api/v1/evidence/EVD-001"),
        ("PATCH", "/api/v1/evidence/EVD-001"),
        ("POST", "/api/v1/evidence/EVD-001/archive"),
        ("POST", "/api/v1/evidence/EVD-001/restore"),
    ]
    assert found.evidence_id == "EVD-001"
    assert edited.title == "CareerOps Platform"
    assert archived.lifecycle_status is EvidenceLifecycleStatus.ARCHIVED
    assert restored.lifecycle_status is EvidenceLifecycleStatus.ACTIVE
