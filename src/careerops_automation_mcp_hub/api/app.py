from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server.auth.provider import TokenVerifier
from sqlalchemy.exc import SQLAlchemyError

from careerops_automation_mcp_hub.api.evidence import build_evidence_router
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineAuthenticationError,
    AgentEngineConflictError,
    AgentEngineContractError,
    AgentEngineNotFoundError,
    AgentEngineRequestError,
    AgentEngineUnavailableError,
    AgentEngineValidationError,
)
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

    app.include_router(
        build_evidence_router(
            service=runtime.evidence_workflow_service,
            registry_service=runtime.evidence_registry_service,
            token_verifier=token_verifier,
            required_scope=runtime.settings.mcp_required_scope,
        )
    )

    @app.exception_handler(AgentEngineNotFoundError)
    async def agent_engine_not_found(
        _: Request,
        exc: AgentEngineNotFoundError,
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": exc.detail})

    @app.exception_handler(AgentEngineConflictError)
    async def agent_engine_conflict(
        _: Request,
        exc: AgentEngineConflictError,
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": exc.detail})

    @app.exception_handler(AgentEngineValidationError)
    async def agent_engine_validation(
        _: Request,
        exc: AgentEngineValidationError,
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.detail})

    @app.exception_handler(AgentEngineUnavailableError)
    async def agent_engine_unavailable(
        _: Request,
        __: AgentEngineUnavailableError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={"detail": "The Agent Engine is temporarily unavailable."},
        )

    @app.exception_handler(AgentEngineAuthenticationError)
    @app.exception_handler(AgentEngineContractError)
    @app.exception_handler(AgentEngineRequestError)
    async def agent_engine_gateway_failure(
        _: Request,
        __: (
            AgentEngineAuthenticationError
            | AgentEngineContractError
            | AgentEngineRequestError
        ),
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": "The Agent Engine returned an invalid response."},
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Return process-level service health."""
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    async def ready() -> JSONResponse:
        """Return whether required runtime dependencies are available."""
        try:
            await runtime.check_database_ready()
        except (SQLAlchemyError, OSError):
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready"},
            )

        return JSONResponse(
            status_code=200,
            content={"status": "ready"},
        )

    # Keep this mount last because "/" matches every remaining path.
    app.mount("/", mcp_http_app)

    return app
