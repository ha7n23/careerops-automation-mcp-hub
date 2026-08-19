from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from mcp.server.auth.provider import TokenVerifier

from careerops_automation_mcp_hub.bootstrap import create_runtime
from careerops_automation_mcp_hub.core.config import Settings


def create_app(
    *,
    token_verifier: TokenVerifier,
    settings: Settings | None = None,
) -> FastAPI:
    """Create the CareerOps HTTP application."""
    runtime = create_runtime(settings)

    mcp_server = runtime.build_authenticated_mcp_server(token_verifier=token_verifier)

    mcp_http_app = mcp_server.streamable_http_app(
        json_response=runtime.settings.mcp_json_response,
        host=runtime.settings.mcp_host,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            async with mcp_server.session_manager.run():
                yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="CareerOps Automation & MCP Hub",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return process-level service health."""
        return {"status": "ok"}

    # Keep this mount last because "/" matches every remaining path.
    app.mount("/", mcp_http_app)

    return app
