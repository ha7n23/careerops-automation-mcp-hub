"""Development-only Streamable HTTP MCP server for local MCP clients."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from careerops_automation_mcp_hub.bootstrap import create_runtime

USER_ID = os.getenv("CAREEROPS_DEV_MCP_USER_ID", "USER-DEMO-001")
ACTOR_ID = os.getenv("CAREEROPS_DEV_MCP_ACTOR_ID", "LOCAL-DEV")


def create_app() -> FastAPI:
    runtime = create_runtime()

    mcp_server = runtime.build_mcp_server_for_principal(
        user_id=USER_ID,
        actor_id=ACTOR_ID,
    )

    mcp_app = mcp_server.streamable_http_app(
        json_response=True,
        host="0.0.0.0",
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            await runtime.check_database_ready()

            async with mcp_server.session_manager.run():
                yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="CareerOps Local MCP Development Server",
        lifespan=lifespan,
    )

    app.mount("/", mcp_app)

    return app


if __name__ == "__main__":
    uvicorn.run(
        create_app(),
        host="0.0.0.0",
        port=8001,
    )
