import asyncio
from uuid import uuid4

import httpx

from careerops_automation_mcp_hub.core.config import get_settings
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)


async def main() -> None:
    settings = get_settings()

    timeout = httpx.Timeout(
        connect=settings.agent_engine_connect_timeout_seconds,
        read=settings.agent_engine_read_timeout_seconds,
        write=settings.agent_engine_write_timeout_seconds,
        pool=settings.agent_engine_pool_timeout_seconds,
    )

    async with httpx.AsyncClient(
        base_url=str(settings.agent_engine_base_url),
        timeout=timeout,
    ) as http_client:
        client = HttpAgentEngineClient(
            http_client,
            service_key=(settings.agent_engine_service_key.get_secret_value()),
        )

        job_id = f"JOB-M2-SMOKE-{uuid4().hex[:8].upper()}"

        result = await client.analyse_job(
            user_id="USER-M2-SMOKE",
            job_id=job_id,
            job_description=(
                "Junior Python Engineer. Strong Python programming "
                "skills are essential."
            ),
        )

        print(f"status={result.status.value}")
        print(f"thread_id={result.thread_id}")
        print(f"job_id={result.job_id}")
        print(f"role_title={result.role_title}")
        print(f"fit_score={result.fit_score}")
        print(f"requirements={len(result.requirements)}")
        print(f"evidence_matches={len(result.evidence_matches)}")
        print(f"cv_proposals={len(result.cv_proposals)}")
        print(
            "review_actions="
            f"{[action.value for action in result.allowed_review_actions]}"
        )


if __name__ == "__main__":
    asyncio.run(main())
