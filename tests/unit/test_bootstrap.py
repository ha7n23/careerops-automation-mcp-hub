import httpx
import pytest
from pydantic import AnyHttpUrl, SecretStr

from careerops_automation_mcp_hub.bootstrap import create_runtime
from careerops_automation_mcp_hub.core.config import Settings
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


@pytest.mark.anyio
async def test_runtime_owns_agent_engine_http_client_lifecycle() -> None:
    settings = Settings(
        database_url=SecretStr(
            "postgresql+asyncpg://careerops:careerops@127.0.0.1:65432/careerops_test"
        ),
        agent_engine_base_url=AnyHttpUrl("http://agent-engine.test"),
        agent_engine_service_key=SecretStr("a" * 32),
    )

    runtime = create_runtime(settings)

    assert isinstance(
        runtime.agent_engine_client,
        HttpAgentEngineClient,
    )
    assert runtime.agent_engine_http_client.base_url == httpx.URL(
        "http://agent-engine.test/"
    )
    assert runtime.agent_engine_http_client.is_closed is False

    await runtime.close()

    assert runtime.agent_engine_http_client.is_closed is True


def test_settings_reject_short_agent_engine_service_key() -> None:
    with pytest.raises(
        ValueError,
        match="at least 32 characters",
    ):
        Settings(
            agent_engine_service_key=SecretStr("too-short"),
        )
