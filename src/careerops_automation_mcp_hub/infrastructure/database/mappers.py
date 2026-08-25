from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_event import ApplicationEvent
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewEdit,
    ApplicationReviewOutcome,
    ApplicationReviewSubmission,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ActionItemRecord,
    ApplicationEventRecord,
    ApplicationPreparationRecord,
    ApplicationReviewSubmissionRecord,
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


def application_preparation_to_record(
    preparation: ApplicationPreparation,
) -> ApplicationPreparationRecord:
    """Convert preparation orchestration state to persistence."""

    return ApplicationPreparationRecord(
        preparation_id=preparation.preparation_id,
        application_id=preparation.application_id,
        user_id=preparation.user_id,
        status=preparation.status.value,
        agent_engine_job_id=preparation.agent_engine_job_id,
        agent_engine_thread_id=preparation.agent_engine_thread_id,
        error_message=preparation.error_message,
        created_at=preparation.created_at,
        updated_at=preparation.updated_at,
    )


def application_preparation_from_record(
    record: ApplicationPreparationRecord,
) -> ApplicationPreparation:
    """Rehydrate durable preparation orchestration state."""

    return ApplicationPreparation(
        preparation_id=record.preparation_id,
        application_id=record.application_id,
        user_id=record.user_id,
        status=ApplicationPreparationStatus(record.status),
        agent_engine_job_id=record.agent_engine_job_id,
        agent_engine_thread_id=record.agent_engine_thread_id,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def application_review_submission_to_record(
    submission: ApplicationReviewSubmission,
) -> ApplicationReviewSubmissionRecord:
    return ApplicationReviewSubmissionRecord(
        review_submission_id=submission.review_submission_id,
        preparation_id=submission.preparation_id,
        application_id=submission.application_id,
        user_id=submission.user_id,
        thread_id=submission.thread_id,
        idempotency_key=submission.idempotency_key,
        action=submission.action.value,
        approved_proposal_ids=list(submission.approved_proposal_ids),
        rejected_proposal_ids=list(submission.rejected_proposal_ids),
        edits=[
            {
                "proposal_id": edit.proposal_id,
                "edited_text": edit.edited_text,
            }
            for edit in submission.edits
        ],
        reviewer_comment=submission.reviewer_comment,
        status=submission.status.value,
        outcome=(submission.outcome.value if submission.outcome is not None else None),
        error_message=submission.error_message,
        created_at=submission.created_at,
        updated_at=submission.updated_at,
    )


def application_review_submission_from_record(
    record: ApplicationReviewSubmissionRecord,
) -> ApplicationReviewSubmission:
    return ApplicationReviewSubmission(
        review_submission_id=record.review_submission_id,
        preparation_id=record.preparation_id,
        application_id=record.application_id,
        user_id=record.user_id,
        thread_id=record.thread_id,
        idempotency_key=record.idempotency_key,
        action=ApplicationReviewAction(record.action),
        approved_proposal_ids=tuple(record.approved_proposal_ids),
        rejected_proposal_ids=tuple(record.rejected_proposal_ids),
        edits=tuple(
            ApplicationReviewEdit(
                proposal_id=edit["proposal_id"],
                edited_text=edit["edited_text"],
            )
            for edit in record.edits
        ),
        reviewer_comment=record.reviewer_comment,
        status=ApplicationReviewSubmissionStatus(record.status),
        outcome=(
            ApplicationReviewOutcome(record.outcome)
            if record.outcome is not None
            else None
        ),
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
