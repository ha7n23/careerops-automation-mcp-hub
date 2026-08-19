from fastapi.testclient import TestClient
from pydantic import AnyHttpUrl, SecretStr

import careerops_automation_mcp_hub.api.main as main_module
from careerops_automation_mcp_hub.core.config import Settings


def test_production_factory_builds_runnable_app(
    monkeypatch,
) -> None:
    settings = Settings(
        database_url=SecretStr(
            "postgresql+asyncpg://careerops:careerops@127.0.0.1:65432/careerops_test"
        ),
        auth_issuer_url=AnyHttpUrl("https://auth.test/"),
        auth_jwks_url=AnyHttpUrl("https://auth.test/.well-known/jwks.json"),
        auth_audience="careerops-automation-mcp-hub",
        auth_jwt_algorithm="RS256",
        mcp_resource_url=AnyHttpUrl("http://testserver/mcp"),
        mcp_host="testserver",
        mcp_required_scope="careerops:applications",
        mcp_json_response=True,
    )

    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: settings,
    )

    app = main_module.create_production_app()

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
