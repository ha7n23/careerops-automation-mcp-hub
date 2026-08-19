from dataclasses import dataclass

from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops_automation_mcp_hub.core.config import Settings, get_settings
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
            token_verifier=token_verifier,
            auth=auth,
        )

    async def close(self) -> None:
        """Release long-lived runtime resources."""
        await self.engine.dispose()


def create_runtime(
    settings: Settings | None = None,
) -> CareerOpsRuntime:
    """Compose the production CareerOps infrastructure graph."""
    resolved_settings = settings if settings is not None else get_settings()

    engine = create_database_engine(resolved_settings.database_url.get_secret_value())
    session_factory = create_session_factory(engine)

    unit_of_work_factory = SqlAlchemyApplicationUnitOfWorkFactory(session_factory)

    return CareerOpsRuntime(
        settings=resolved_settings,
        engine=engine,
        unit_of_work_factory=unit_of_work_factory,
    )
