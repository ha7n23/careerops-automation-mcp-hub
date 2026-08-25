import pytest
from mcp import Client
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from careerops_automation_mcp_hub.bootstrap import create_runtime
from careerops_automation_mcp_hub.core.config import Settings
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ApplicationEventRecord,
    JobApplicationRecord,
)


@pytest.mark.anyio
async def test_runtime_composes_mcp_server_with_postgresql(
    postgres_database_url: str,
    postgres_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = Settings(
        database_url=SecretStr(postgres_database_url),
        agent_engine_service_key=SecretStr("a" * 32),
    )

    runtime = create_runtime(settings)

    try:
        server = runtime.build_mcp_server_for_principal(
            user_id="USER-RUNTIME",
            actor_id="MCP-RUNTIME",
        )

        async with Client(server, raise_exceptions=True) as client:
            result = await client.call_tool(
                "create_application",
                {
                    "company_name": "Monzo",
                    "role_title": "Junior AI Engineer",
                    "idempotency_key": "runtime-create-1",
                },
            )

        assert result.is_error is False
        assert result.structured_content is not None
        assert result.structured_content["company_name"] == "Monzo"
        assert result.structured_content["status"] == "saved"

        async with postgres_session_factory() as session:
            application_count = await session.scalar(
                select(func.count()).select_from(JobApplicationRecord)
            )
            event_count = await session.scalar(
                select(func.count()).select_from(ApplicationEventRecord)
            )

        assert application_count == 1
        assert event_count == 1

    finally:
        await runtime.close()
