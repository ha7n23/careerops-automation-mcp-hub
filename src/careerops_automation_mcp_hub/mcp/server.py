from datetime import datetime
from uuid import UUID

from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations

from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
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
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationCommand,
    PrepareApplicationService,
)
from careerops_automation_mcp_hub.application.services.review_application import (
    ReviewApplicationCommand,
    ReviewApplicationService,
)
from careerops_automation_mcp_hub.application.services.update_application_status import (
    UpdateApplicationStatusCommand,
    UpdateApplicationStatusService,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewEdit,
)
from careerops_automation_mcp_hub.mcp.principal import PrincipalProvider
from careerops_automation_mcp_hub.mcp.schemas import (
    ActionItemSummary,
    ApplicationListResult,
    ApplicationReviewEditInput,
    ApplicationSummary,
    PendingActionsResult,
    PrepareApplicationToolResult,
    ReviewApplicationToolResult,
)


def build_mcp_server(
    *,
    principal_provider: PrincipalProvider,
    unit_of_work_factory: ApplicationUnitOfWorkFactory,
    prepare_application_service: PrepareApplicationService,
    review_application_service: ReviewApplicationService,
    token_verifier: TokenVerifier | None = None,
    auth: AuthSettings | None = None,
) -> MCPServer:
    """Build the CareerOps MCP server for a trusted principal."""

    mcp = MCPServer(
        "CareerOps Automation Hub",
        token_verifier=token_verifier,
        auth=auth,
    )

    create_service = CreateApplicationService(unit_of_work_factory)
    get_service = GetApplicationService(unit_of_work_factory)
    update_service = UpdateApplicationStatusService(unit_of_work_factory)
    list_service = ListApplicationsService(unit_of_work_factory)
    pending_actions_service = GetPendingActionsService(unit_of_work_factory)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    async def create_application(
        company_name: str,
        role_title: str,
        idempotency_key: str,
    ) -> ApplicationSummary:
        """Create a saved CareerOps job application.

        This changes internal CareerOps state only. It does not submit
        an application to an employer or external website.
        """

        principal = principal_provider.get_principal()

        result = await create_service.execute(
            CreateApplicationCommand(
                user_id=principal.user_id,
                company_name=company_name,
                role_title=role_title,
                actor_id=principal.actor_id,
                idempotency_key=idempotency_key,
            )
        )

        return ApplicationSummary.from_domain(result.application)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    async def prepare_application(
        application_id: UUID,
        job_description: str,
    ) -> PrepareApplicationToolResult:
        """Prepare a saved application using the CareerOps Agent Engine.

        This may run evidence-grounded AI analysis and CV proposal generation
        inside CareerOps. It does not submit an application to an employer.

        Durable preparation state prevents an ambiguous remote outcome from
        being blindly retried.
        """

        principal = principal_provider.get_principal()

        result = await prepare_application_service.execute(
            PrepareApplicationCommand(
                user_id=principal.user_id,
                application_id=application_id,
                job_description=job_description,
                actor_id=principal.actor_id,
            )
        )

        return PrepareApplicationToolResult.from_application_result(result)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    async def review_application(
        application_id: UUID,
        idempotency_key: str,
        action: ApplicationReviewAction,
        approved_proposal_ids: list[str] | None = None,
        rejected_proposal_ids: list[str] | None = None,
        edits: list[ApplicationReviewEditInput] | None = None,
        reviewer_comment: str | None = None,
    ) -> ReviewApplicationToolResult:
        """Apply an explicit human decision to a prepared application.

        This acts on CareerOps' internal CV-review workflow only. It does
        not submit an application to an employer or external job portal.

        The caller must supply a new idempotency key for each intentional
        review round. Ambiguous remote outcomes are durably blocked from
        blind resubmission.
        """

        principal = principal_provider.get_principal()

        domain_edits = tuple(
            ApplicationReviewEdit(
                proposal_id=edit.proposal_id,
                edited_text=edit.edited_text,
            )
            for edit in (edits or [])
        )

        result = await review_application_service.execute(
            ReviewApplicationCommand(
                user_id=principal.user_id,
                application_id=application_id,
                actor_id=principal.actor_id,
                idempotency_key=idempotency_key,
                action=action,
                approved_proposal_ids=tuple(approved_proposal_ids or []),
                rejected_proposal_ids=tuple(rejected_proposal_ids or []),
                edits=domain_edits,
                reviewer_comment=reviewer_comment,
            )
        )

        return ReviewApplicationToolResult.from_application_result(result)

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

        principal = principal_provider.get_principal()

        application = await get_service.execute(
            GetApplicationQuery(
                user_id=principal.user_id,
                application_id=application_id,
            )
        )

        return ApplicationSummary.from_domain(application)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    async def update_application_status(
        application_id: UUID,
        target_status: ApplicationStatus,
        idempotency_key: str,
    ) -> ApplicationSummary:
        """Move an application to a valid internal CareerOps lifecycle state.

        This updates CareerOps tracking state only and never changes
        an application on an external employer system.
        """

        principal = principal_provider.get_principal()

        result = await update_service.execute(
            UpdateApplicationStatusCommand(
                user_id=principal.user_id,
                application_id=application_id,
                target_status=target_status,
                actor_id=principal.actor_id,
                idempotency_key=idempotency_key,
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

        principal = principal_provider.get_principal()

        applications_found = await list_service.execute(
            ListApplicationsQuery(
                user_id=principal.user_id,
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

        principal = principal_provider.get_principal()

        actions_found = await pending_actions_service.execute(
            GetPendingActionsQuery(
                user_id=principal.user_id,
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

        principal = principal_provider.get_principal()

        application = await get_service.execute(
            GetApplicationQuery(
                user_id=principal.user_id,
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

        principal = principal_provider.get_principal()

        actions_found = await pending_actions_service.execute(
            GetPendingActionsQuery(user_id=principal.user_id)
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
