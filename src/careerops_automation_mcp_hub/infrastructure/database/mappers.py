from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_event import ApplicationEvent
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ActionItemRecord,
    ApplicationEventRecord,
    JobApplicationRecord,
)


def job_application_to_record(
    application: JobApplication,
) -> JobApplicationRecord:
    """Convert a job-application domain entity to a persistence record."""
    return JobApplicationRecord(
        application_id=application.application_id,
        user_id=application.user_id,
        company_name=application.company_name,
        role_title=application.role_title,
        status=application.status.value,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


def job_application_from_record(
    record: JobApplicationRecord,
) -> JobApplication:
    """Rehydrate a job-application domain entity from persistence."""
    return JobApplication(
        application_id=record.application_id,
        user_id=record.user_id,
        company_name=record.company_name,
        role_title=record.role_title,
        status=ApplicationStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def application_event_to_record(
    event: ApplicationEvent,
) -> ApplicationEventRecord:
    """Convert an application event to a persistence record."""
    return ApplicationEventRecord(
        event_id=event.event_id,
        application_id=event.application_id,
        user_id=event.user_id,
        event_type=event.event_type.value,
        actor_id=event.actor_id,
        occurred_at=event.occurred_at,
        attributes=dict(event.attributes),
    )


def action_item_to_record(
    action: ActionItem,
) -> ActionItemRecord:
    """Convert an action-item domain entity to a persistence record."""
    return ActionItemRecord(
        action_id=action.action_id,
        application_id=action.application_id,
        user_id=action.user_id,
        action_type=action.action_type.value,
        description=action.description,
        status=action.status.value,
        due_at=action.due_at,
        created_at=action.created_at,
        completed_at=action.completed_at,
    )


def action_item_from_record(
    record: ActionItemRecord,
) -> ActionItem:
    """Rehydrate an action-item domain entity from persistence."""
    return ActionItem(
        action_id=record.action_id,
        application_id=record.application_id,
        user_id=record.user_id,
        action_type=ActionItemType(record.action_type),
        description=record.description,
        status=ActionItemStatus(record.status),
        due_at=record.due_at,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )
