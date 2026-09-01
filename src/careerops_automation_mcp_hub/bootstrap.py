from dataclasses import dataclass

import httpx
from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops_automation_mcp_hub.application.services.get_application_analysis import (
    GetApplicationAnalysisService,
)
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationService,
)
from careerops_automation_mcp_hub.application.services.review_application import (
    ReviewApplicationService,
)
from careerops_automation_mcp_hub.core.config import Settings, get_settings
from careerops_automation_mcp_hub.infrastructure.agent_engine.http_client import (
    HttpAgentEngineClient,
)
from careerops_automation_mcp_hub.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.mcp.principal import (
    AccessTokenPrincipalProvider,
    Principal,
    PrincipalProvider,
    StaticPrincipalProvider,
)
from careerops_automation_mcp_hub.mcp.server import (
    build_mcp_server as build_application_mcp_server,
)


@dataclass(slots=True)
class CareerOpsRuntime:
    """Own the long-lived infrastructure resources for one process."""

    settings: Settings
    engine: AsyncEngine
    unit_of_work_factory: SqlAlchemyApplicationUnitOfWorkFactory
    agent_engine_http_client: httpx.AsyncClient
    agent_engine_client: HttpAgentEngineClient
    prepare_application_service: PrepareApplicationService
    review_application_service: ReviewApplicationService
    get_application_analysis_service: GetApplicationAnalysisService

    def build_mcp_server_for_principal(
        self,
        *,
        user_id: str,
        actor_id: str,
    ) -> MCPServer:
        """Build an MCP server for an already-authenticated principal."""
        principal_provider = StaticPrincipalProvider(
            Principal(
                user_id=user_id,
                actor_id=actor_id,
            )
        )

        return self.build_mcp_server(
            principal_provider=principal_provider,
        )

    def build_authenticated_mcp_server(
        self,
        *,
        token_verifier: TokenVerifier,
    ) -> MCPServer:
        """Build the authenticated Streamable HTTP MCP server."""
        auth = AuthSettings(
            issuer_url=self.settings.auth_issuer_url,
            resource_server_url=self.settings.mcp_resource_url,
            required_scopes=[self.settings.mcp_required_scope],
        )

        return self.build_mcp_server(
            principal_provider=AccessTokenPrincipalProvider(),
            token_verifier=token_verifier,
            auth=auth,
        )

    def build_mcp_server(
        self,
        *,
        principal_provider: PrincipalProvider,
        token_verifier: TokenVerifier | None = None,
        auth: AuthSettings | None = None,
    ) -> MCPServer:
        """Build an MCP server using the supplied identity boundary."""
        return build_application_mcp_server(
            principal_provider=principal_provider,
            unit_of_work_factory=self.unit_of_work_factory,
            prepare_application_service=self.prepare_application_service,
            review_application_service=self.review_application_service,
            get_application_analysis_service=self.get_application_analysis_service,
            token_verifier=token_verifier,
            auth=auth,
        )

    async def check_database_ready(self) -> None:
        """Raise if the configured PostgreSQL database is not reachable."""
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        """Release long-lived runtime resources."""
        try:
            await self.agent_engine_http_client.aclose()
        finally:
            await self.engine.dispose()


def create_runtime(
    settings: Settings | None = None,
) -> CareerOpsRuntime:
    """Compose the production CareerOps infrastructure graph."""
    resolved_settings = settings if settings is not None else get_settings()

    engine = create_database_engine(resolved_settings.database_url.get_secret_value())
    session_factory = create_session_factory(engine)

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(session_factory)

    agent_engine_timeout = httpx.Timeout(
        connect=resolved_settings.agent_engine_connect_timeout_seconds,
        read=resolved_settings.agent_engine_read_timeout_seconds,
        write=resolved_settings.agent_engine_write_timeout_seconds,
        pool=resolved_settings.agent_engine_pool_timeout_seconds,
    )

    agent_engine_http_client = httpx.AsyncClient(
        base_url=str(resolved_settings.agent_engine_base_url),
        timeout=agent_engine_timeout,
    )

    agent_engine_client = HttpAgentEngineClient(
        agent_engine_http_client,
        service_key=(resolved_settings.agent_engine_service_key.get_secret_value()),
    )

    prepare_application_service = PrepareApplicationService(
        unit_of_work_factory,
        agent_engine_client,
    )

    get_application_analysis_service = GetApplicationAnalysisService(
        unit_of_work_factory,
        agent_engine_client,
    )

    review_application_service = ReviewApplicationService(
        unit_of_work_factory,
        agent_engine_client,
    )

    return CareerOpsRuntime(
        settings=resolved_settings,
        engine=engine,
        unit_of_work_factory=unit_of_work_factory,
        agent_engine_http_client=agent_engine_http_client,
        agent_engine_client=agent_engine_client,
        prepare_application_service=prepare_application_service,
        review_application_service=review_application_service,
        get_application_analysis_service=get_application_analysis_service,
    )
