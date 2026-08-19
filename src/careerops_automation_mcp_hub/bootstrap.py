from dataclasses import dataclass

from mcp.server import MCPServer
from sqlalchemy.ext.asyncio import AsyncEngine

from careerops_automation_mcp_hub.core.config import Settings, get_settings
from careerops_automation_mcp_hub.infrastructure.database.session import (
    create_database_engine,
    create_session_factory,
)
from careerops_automation_mcp_hub.infrastructure.database.unit_of_work import (
    SqlAlchemyApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.mcp.server import build_mcp_server


@dataclass(slots=True)
class CareerOpsRuntime:
    """Own the long-lived infrastructure resources for one process."""

    engine: AsyncEngine
    unit_of_work_factory: SqlAlchemyApplicationUnitOfWorkFactory

    def build_mcp_server_for_principal(
        self,
        *,
        user_id: str,
        actor_id: str,
    ) -> MCPServer:
        """Build an MCP server for an already-authenticated principal."""
        return build_mcp_server(
            user_id=user_id,
            actor_id=actor_id,
            unit_of_work_factory=self.unit_of_work_factory,
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
        engine=engine,
        unit_of_work_factory=unit_of_work_factory,
    )
