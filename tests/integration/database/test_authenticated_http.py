import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import AnyHttpUrl, SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.api.app import create_app
from careerops_automation_mcp_hub.core.config import Settings
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ApplicationEventRecord,
    JobApplicationRecord,
)


class StubTokenVerifier(TokenVerifier):
    """Test-only verifier for exercising the HTTP authentication boundary."""

    async def verify_token(
        self,
        token: str,
    ) -> AccessToken | None:
        if token != "valid-token":
            return None

        return AccessToken(
            token=token,
            client_id="openclaw",
            scopes=["careerops:applications"],
            subject="USER-HTTP",
        )


def build_test_settings(database_url: str) -> Settings:
    return Settings(
        database_url=SecretStr(database_url),
        auth_issuer_url=AnyHttpUrl("https://auth.example.com"),
        mcp_resource_url=AnyHttpUrl("http://testserver/mcp"),
        mcp_host="testserver",
        mcp_required_scope="careerops:applications",
        mcp_json_response=True,
    )


_MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2026-07-28",
    "Mcp-Method": "tools/call",
    "Mcp-Name": "create_application",
}

_CREATE_APPLICATION_REQUEST = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "create_application",
        "arguments": {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
        "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientInfo": {
                "name": "CareerOpsTestClient",
                "version": "1.0.0",
            },
            "io.modelcontextprotocol/clientCapabilities": {},
        },
    },
}


def test_health_endpoint_is_public(
    postgres_database_url: str,
) -> None:
    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(postgres_database_url),
    )

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_protected_resource_metadata_is_public(
    postgres_database_url: str,
) -> None:
    settings = build_test_settings(postgres_database_url)

    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=settings,
    )

    with TestClient(app) as client:
        response = client.get("/.well-known/oauth-protected-resource/mcp")

    assert response.status_code == 200

    payload = response.json()

    assert payload["resource"] == str(settings.mcp_resource_url)
    assert payload["authorization_servers"] == [str(settings.auth_issuer_url)]
    assert payload["scopes_supported"] == [settings.mcp_required_scope]


def test_mcp_endpoint_rejects_missing_token(
    postgres_database_url: str,
) -> None:
    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(postgres_database_url),
    )

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers=_MCP_HEADERS,
            json=_CREATE_APPLICATION_REQUEST,
        )

    assert response.status_code == 401
    assert "Bearer" in response.headers["WWW-Authenticate"]


def test_mcp_endpoint_rejects_invalid_token(
    postgres_database_url: str,
) -> None:
    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(postgres_database_url),
    )

    headers = {
        **_MCP_HEADERS,
        "Authorization": "Bearer invalid-token",
    }

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers=headers,
            json=_CREATE_APPLICATION_REQUEST,
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_authenticated_mcp_request_uses_token_principal(
    postgres_database_url: str,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(postgres_database_url),
    )

    headers = {
        **_MCP_HEADERS,
        "Authorization": "Bearer valid-token",
    }

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers=headers,
            json=_CREATE_APPLICATION_REQUEST,
        )

    assert response.status_code == 200

    payload = response.json()

    assert "result" in payload
    assert payload["result"]["isError"] is False

    async with postgres_session_factory() as session:
        application_result = await session.execute(select(JobApplicationRecord))
        event_result = await session.execute(select(ApplicationEventRecord))

        applications = application_result.scalars().all()
        events = event_result.scalars().all()

    assert len(applications) == 1
    assert len(events) == 1

    assert applications[0].user_id == "USER-HTTP"
    assert events[0].user_id == "USER-HTTP"
    assert events[0].actor_id == "openclaw"


def test_ready_endpoint_reports_database_available(
    postgres_database_url: str,
) -> None:
    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(postgres_database_url),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_endpoint_returns_503_when_database_unavailable() -> None:
    unavailable_database_url = (
        "postgresql+asyncpg://careerops:careerops@127.0.0.1:65432/careerops_test"
    )

    app = create_app(
        token_verifier=StubTokenVerifier(),
        settings=build_test_settings(unavailable_database_url),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
