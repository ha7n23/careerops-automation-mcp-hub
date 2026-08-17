from datetime import datetime
from uuid import UUID

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from careerops_automation_mcp_hub.application.ports.repositories import (
    ActionItemRepository,
    ApplicationEventRepository,
    JobApplicationRepository,
)
from careerops_automation_mcp_hub.application.services.create_application import (
    CreateApplicationCommand,
    CreateApplicationService,
)
from careerops_automation_mcp_hub.application.services.get_application import (
    GetApplicationQuery,
    GetApplicationService,
)
from careerops_automation_mcp_hub.application.services.get_pending_actions import (
    GetPendingActionsQuery,
    GetPendingActionsService,
)
from careerops_automation_mcp_hub.application.services.list_applications import (
    ListApplicationsQuery,
    ListApplicationsService,
)
from careerops_automation_mcp_hub.application.services.update_application_status import (
    UpdateApplicationStatusCommand,
    UpdateApplicationStatusService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.mcp.schemas import (
    ActionItemSummary,
    ApplicationListResult,
    ApplicationSummary,
    PendingActionsResult,
)


def build_mcp_server(
    *,
    user_id: str,
    actor_id: str,
    applications: JobApplicationRepository,
    events: ApplicationEventRepository,
    actions: ActionItemRepository,
) -> MCPServer:
    """Build the CareerOps MCP server for a trusted principal."""
    mcp = MCPServer("CareerOps Automation Hub")

    create_service = CreateApplicationService(
        applications,
        events,
    )
    get_service = GetApplicationService(applications)
    update_service = UpdateApplicationStatusService(
        applications,
        events,
    )
    list_service = ListApplicationsService(applications)
    pending_actions_service = GetPendingActionsService(actions)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def create_application(
        company_name: str,
        role_title: str,
    ) -> ApplicationSummary:
        """Create a saved CareerOps job application.

        This changes internal CareerOps state only. It does not submit
        an application to an employer or external website.
        """
        result = await create_service.execute(
            CreateApplicationCommand(
                user_id=user_id,
                company_name=company_name,
                role_title=role_title,
                actor_id=actor_id,
            )
        )

        return ApplicationSummary.from_domain(result.application)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            open_world_hint=False,
        )
    )
    async def get_application(
        application_id: UUID,
    ) -> ApplicationSummary:
        """Return one CareerOps application available to the current user."""
        application = await get_service.execute(
            GetApplicationQuery(
                user_id=user_id,
                application_id=application_id,
            )
        )

        return ApplicationSummary.from_domain(application)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def update_application_status(
        application_id: UUID,
        target_status: ApplicationStatus,
    ) -> ApplicationSummary:
        """Move an application to a valid internal CareerOps lifecycle state.

        This updates CareerOps tracking state only and never changes
        an application on an external employer system.
        """
        result = await update_service.execute(
            UpdateApplicationStatusCommand(
                user_id=user_id,
                application_id=application_id,
                target_status=target_status,
                actor_id=actor_id,
            )
        )

        return ApplicationSummary.from_domain(result.application)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            open_world_hint=False,
        )
    )
    async def list_applications(
        status: ApplicationStatus | None = None,
    ) -> ApplicationListResult:
        """List CareerOps applications available to the current user."""
        applications_found = await list_service.execute(
            ListApplicationsQuery(
                user_id=user_id,
                status=status,
            )
        )

        summaries = [
            ApplicationSummary.from_domain(application)
            for application in applications_found
        ]

        return ApplicationListResult(
            applications=summaries,
            count=len(summaries),
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=True,
            open_world_hint=False,
        )
    )
    async def get_pending_actions(
        due_before: datetime | None = None,
    ) -> PendingActionsResult:
        """Return pending CareerOps actions requiring the user's attention."""
        actions_found = await pending_actions_service.execute(
            GetPendingActionsQuery(
                user_id=user_id,
                due_before=due_before,
            )
        )

        summaries = [ActionItemSummary.from_domain(action) for action in actions_found]

        return PendingActionsResult(
            actions=summaries,
            count=len(summaries),
        )

    @mcp.resource(
        "careerops://applications/{application_id}",
        mime_type="text/markdown",
    )
    async def application_resource(application_id: str) -> str:
        """Human-readable context for one CareerOps application."""
        try:
            parsed_id = UUID(application_id)
        except ValueError as exc:
            raise ValueError("Invalid application ID.") from exc

        application = await get_service.execute(
            GetApplicationQuery(
                user_id=user_id,
                application_id=parsed_id,
            )
        )

        return (
            f"# {application.role_title} — {application.company_name}\n\n"
            f"- Application ID: `{application.application_id}`\n"
            f"- Status: `{application.status.value}`\n"
            f"- Created: {application.created_at.isoformat()}\n"
            f"- Updated: {application.updated_at.isoformat()}\n"
        )

    @mcp.resource(
        "careerops://actions/pending",
        mime_type="text/markdown",
    )
    async def pending_actions_resource() -> str:
        """Human-readable view of the user's pending CareerOps actions."""
        actions_found = await pending_actions_service.execute(
            GetPendingActionsQuery(user_id=user_id)
        )

        if not actions_found:
            return "# Pending Actions\n\nNo pending actions."

        lines = ["# Pending Actions", ""]

        for action in actions_found:
            due = action.due_at.isoformat() if action.due_at else "No due date"
            lines.append(
                f"- **{action.action_type.value}** — "
                f"{action.description} _(due: {due})_"
            )

        return "\n".join(lines)

    return mcp
