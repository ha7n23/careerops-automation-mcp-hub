from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyClaim,
    IdempotencyOperation,
)
from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
)
from careerops_automation_mcp_hub.domain.application_event import ApplicationEvent
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewSubmission,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication
from careerops_automation_mcp_hub.infrastructure.database.mappers import (
    action_item_from_record,
    action_item_to_record,
    application_event_to_record,
    application_preparation_from_record,
    application_preparation_to_record,
    application_review_submission_from_record,
    application_review_submission_to_record,
    job_application_from_record,
    job_application_to_record,
)
from careerops_automation_mcp_hub.infrastructure.database.models import (
    ActionItemRecord,
    ApplicationPreparationRecord,
    ApplicationReviewSubmissionRecord,
    IdempotencyRecord,
    JobApplicationRecord,
)


class SqlAlchemyJobApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, application: JobApplication) -> None:
        self._session.add(job_application_to_record(application))
        await self._session.flush()

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        statement = select(JobApplicationRecord).where(
            JobApplicationRecord.application_id == application_id,
            JobApplicationRecord.user_id == user_id,
        )

        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return job_application_from_record(record)

    async def save(self, application: JobApplication) -> None:
        statement = (
            update(JobApplicationRecord)
            .where(
                JobApplicationRecord.application_id == application.application_id,
                JobApplicationRecord.user_id == application.user_id,
            )
            .values(
                company_name=application.company_name,
                role_title=application.role_title,
                status=application.status.value,
                updated_at=application.updated_at,
            )
        )

        await self._session.execute(statement)

    async def list_for_user(
        self,
        *,
        user_id: str,
        status: ApplicationStatus | None = None,
    ) -> tuple[JobApplication, ...]:
        statement = select(JobApplicationRecord).where(
            JobApplicationRecord.user_id == user_id
        )

        if status is not None:
            statement = statement.where(JobApplicationRecord.status == status.value)

        statement = statement.order_by(
            JobApplicationRecord.created_at,
            JobApplicationRecord.application_id,
        )

        result = await self._session.execute(statement)
        records = result.scalars().all()

        return tuple(job_application_from_record(record) for record in records)


class SqlAlchemyApplicationEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: ApplicationEvent) -> None:
        self._session.add(application_event_to_record(event))


class SqlAlchemyActionItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, action: ActionItem) -> None:
        self._session.add(action_item_to_record(action))

    async def list_pending(
        self,
        *,
        user_id: str,
        due_before: datetime | None = None,
    ) -> tuple[ActionItem, ...]:
        statement = select(ActionItemRecord).where(
            ActionItemRecord.user_id == user_id,
            ActionItemRecord.status == ActionItemStatus.PENDING.value,
        )

        if due_before is not None:
            statement = statement.where(
                ActionItemRecord.due_at.is_not(None),
                ActionItemRecord.due_at <= due_before,
            )

        statement = statement.order_by(
            ActionItemRecord.due_at.asc().nulls_last(),
            ActionItemRecord.created_at,
            ActionItemRecord.action_id,
        )

        result = await self._session.execute(statement)
        records = result.scalars().all()

        return tuple(action_item_from_record(record) for record in records)


class SqlAlchemyApplicationPreparationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        self._session.add(application_preparation_to_record(preparation))
        await self._session.flush()

    async def get_for_application(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> ApplicationPreparation | None:
        statement = select(ApplicationPreparationRecord).where(
            ApplicationPreparationRecord.user_id == user_id,
            ApplicationPreparationRecord.application_id == application_id,
        )

        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return application_preparation_from_record(record)

    async def save(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        statement = (
            update(ApplicationPreparationRecord)
            .where(
                ApplicationPreparationRecord.preparation_id
                == preparation.preparation_id,
                ApplicationPreparationRecord.user_id == preparation.user_id,
                ApplicationPreparationRecord.application_id
                == preparation.application_id,
            )
            .values(
                status=preparation.status.value,
                agent_engine_thread_id=preparation.agent_engine_thread_id,
                error_message=preparation.error_message,
                updated_at=preparation.updated_at,
            )
        )

        await self._session.execute(statement)


class SqlAlchemyApplicationReviewSubmissionRepository:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def add(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        self._session.add(application_review_submission_to_record(submission))
        await self._session.flush()

    async def get_by_idempotency_key(
        self,
        *,
        user_id: str,
        idempotency_key: str,
    ) -> ApplicationReviewSubmission | None:
        statement = select(ApplicationReviewSubmissionRecord).where(
            ApplicationReviewSubmissionRecord.user_id == user_id,
            ApplicationReviewSubmissionRecord.idempotency_key == idempotency_key,
        )

        result = await self._session.execute(statement)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        return application_review_submission_from_record(record)

    async def save(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        statement = (
            update(ApplicationReviewSubmissionRecord)
            .where(
                ApplicationReviewSubmissionRecord.review_submission_id
                == submission.review_submission_id,
                ApplicationReviewSubmissionRecord.user_id == submission.user_id,
            )
            .values(
                status=submission.status.value,
                outcome=(
                    submission.outcome.value if submission.outcome is not None else None
                ),
                error_message=submission.error_message,
                updated_at=submission.updated_at,
            )
        )

        await self._session.execute(statement)


class SqlAlchemyIdempotencyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def claim(
        self,
        *,
        user_id: str,
        operation: IdempotencyOperation,
        idempotency_key: str,
        request_fingerprint: str,
        created_at: datetime,
    ) -> IdempotencyClaim:
        statement = (
            insert(IdempotencyRecord)
            .values(
                user_id=user_id,
                operation=operation.value,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                response_payload=None,
                created_at=created_at,
                completed_at=None,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    IdempotencyRecord.user_id,
                    IdempotencyRecord.operation,
                    IdempotencyRecord.idempotency_key,
                ]
            )
            .returning(IdempotencyRecord.request_fingerprint)
        )

        result = await self._session.execute(statement)
        inserted_fingerprint = result.scalar_one_or_none()

        if inserted_fingerprint is not None:
            return IdempotencyClaim(
                acquired=True,
                request_fingerprint=inserted_fingerprint,
                response_payload=None,
            )

        existing_statement = select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.operation == operation.value,
            IdempotencyRecord.idempotency_key == idempotency_key,
        )

        existing_result = await self._session.execute(existing_statement)
        existing = existing_result.scalar_one()

        response_payload = (
            dict(existing.response_payload)
            if existing.response_payload is not None
            else None
        )

        return IdempotencyClaim(
            acquired=False,
            request_fingerprint=existing.request_fingerprint,
            response_payload=response_payload,
        )

    async def complete(
        self,
        *,
        user_id: str,
        operation: IdempotencyOperation,
        idempotency_key: str,
        request_fingerprint: str,
        response_payload: Mapping[str, object],
        completed_at: datetime,
    ) -> None:
        statement = (
            update(IdempotencyRecord)
            .where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.operation == operation.value,
                IdempotencyRecord.idempotency_key == idempotency_key,
                IdempotencyRecord.request_fingerprint == request_fingerprint,
                IdempotencyRecord.response_payload.is_(None),
                IdempotencyRecord.completed_at.is_(None),
            )
            .values(
                response_payload=dict(response_payload),
                completed_at=completed_at,
            )
            .returning(IdempotencyRecord.idempotency_key)
        )

        result = await self._session.execute(statement)

        if result.scalar_one_or_none() is None:
            raise RuntimeError("Idempotency record could not be completed.")
