from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


class ApplicationSummary(BaseModel):
    application_id: UUID
    company_name: str
    role_title: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        application: JobApplication,
    ) -> "ApplicationSummary":
        return cls(
            application_id=application.application_id,
            company_name=application.company_name,
            role_title=application.role_title,
            status=application.status,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class ApplicationListResult(BaseModel):
    applications: list[ApplicationSummary]
    count: int


class ActionItemSummary(BaseModel):
    action_id: UUID
    application_id: UUID
    action_type: ActionItemType
    description: str
    status: ActionItemStatus
    due_at: datetime | None

    @classmethod
    def from_domain(cls, action: ActionItem) -> "ActionItemSummary":
        return cls(
            action_id=action.action_id,
            application_id=action.application_id,
            action_type=action.action_type,
            description=action.description,
            status=action.status,
            due_at=action.due_at,
        )


class PendingActionsResult(BaseModel):
    actions: list[ActionItemSummary]
    count: int
