from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyClaim,
    IdempotencyOperation,
)
from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
)
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewSubmission,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)


class InMemoryJobApplicationRepository:
    def __init__(self) -> None:
        self._applications: dict[UUID, JobApplication] = {}

    async def add(self, application: JobApplication) -> None:
        self._applications[application.application_id] = application

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        application = self._applications.get(application_id)

        if application is None or application.user_id != user_id:
            return None

        return application

    async def save(self, application: JobApplication) -> None:
        self._applications[application.application_id] = application

    def all(self) -> tuple[JobApplication, ...]:
        return tuple(self._applications.values())

    async def list_for_user(
        self,
        *,
        user_id: str,
        status: ApplicationStatus | None = None,
    ) -> tuple[JobApplication, ...]:
        applications = [
            application
            for application in self._applications.values()
            if application.user_id == user_id
            and (status is None or application.status is status)
        ]

        return tuple(
            sorted(
                applications,
                key=lambda application: (
                    application.created_at,
                    application.application_id.hex,
                ),
            )
        )


class InMemoryApplicationEventRepository:
    def __init__(self) -> None:
        self._events: list[ApplicationEvent] = []

    async def add(self, event: ApplicationEvent) -> None:
        self._events.append(event)

    def all(self) -> tuple[ApplicationEvent, ...]:
        return tuple(self._events)


class InMemoryActionItemRepository:
    def __init__(self) -> None:
        self._actions: dict[UUID, ActionItem] = {}

    async def add(self, action: ActionItem) -> None:
        self._actions[action.action_id] = action

    async def list_pending(
        self,
        *,
        user_id: str,
        due_before: datetime | None = None,
    ) -> tuple[ActionItem, ...]:
        actions = [
            action
            for action in self._actions.values()
            if action.user_id == user_id
            and action.status is ActionItemStatus.PENDING
            and (
                due_before is None
                or (action.due_at is not None and action.due_at <= due_before)
            )
        ]

        return tuple(
            sorted(
                actions,
                key=lambda action: (
                    action.due_at is None,
                    action.due_at or action.created_at,
                    action.action_id.hex,
                ),
            )
        )

    def all(self) -> tuple[ActionItem, ...]:
        return tuple(self._actions.values())


@dataclass(slots=True)
class _InMemoryIdempotencyRecord:
    request_fingerprint: str
    response_payload: dict[str, object] | None
    created_at: datetime
    completed_at: datetime | None


class InMemoryIdempotencyRepository:
    def __init__(self) -> None:
        self._records: dict[
            tuple[str, IdempotencyOperation, str],
            _InMemoryIdempotencyRecord,
        ] = {}

    async def claim(
        self,
        *,
        user_id: str,
        operation: IdempotencyOperation,
        idempotency_key: str,
        request_fingerprint: str,
        created_at: datetime,
    ) -> IdempotencyClaim:
        key = (
            user_id,
            operation,
            idempotency_key,
        )

        existing = self._records.get(key)

        if existing is not None:
            return IdempotencyClaim(
                acquired=False,
                request_fingerprint=existing.request_fingerprint,
                response_payload=(
                    dict(existing.response_payload)
                    if existing.response_payload is not None
                    else None
                ),
            )

        self._records[key] = _InMemoryIdempotencyRecord(
            request_fingerprint=request_fingerprint,
            response_payload=None,
            created_at=created_at,
            completed_at=None,
        )

        return IdempotencyClaim(
            acquired=True,
            request_fingerprint=request_fingerprint,
            response_payload=None,
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
        key = (
            user_id,
            operation,
            idempotency_key,
        )

        existing = self._records.get(key)

        if (
            existing is None
            or existing.request_fingerprint != request_fingerprint
            or existing.response_payload is not None
            or existing.completed_at is not None
        ):
            raise RuntimeError("Idempotency record could not be completed.")

        existing.response_payload = dict(response_payload)
        existing.completed_at = completed_at


class InMemoryApplicationPreparationRepository:
    def __init__(self) -> None:
        self._preparations: dict[UUID, ApplicationPreparation] = {}

    async def add(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        self._preparations[preparation.preparation_id] = preparation

    async def get_for_application(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> ApplicationPreparation | None:
        for preparation in self._preparations.values():
            if (
                preparation.user_id == user_id
                and preparation.application_id == application_id
            ):
                return preparation

        return None

    async def save(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        self._preparations[preparation.preparation_id] = preparation

    def all(self) -> tuple[ApplicationPreparation, ...]:
        return tuple(self._preparations.values())


class InMemoryApplicationReviewSubmissionRepository:
    def __init__(self) -> None:
        self._submissions: dict[UUID, ApplicationReviewSubmission] = {}

    async def add(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        self._submissions[submission.review_submission_id] = submission

    async def get_by_idempotency_key(
        self,
        *,
        user_id: str,
        idempotency_key: str,
    ) -> ApplicationReviewSubmission | None:
        for submission in self._submissions.values():
            if (
                submission.user_id == user_id
                and submission.idempotency_key == idempotency_key
            ):
                return submission

        return None

    async def save(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        self._submissions[submission.review_submission_id] = submission

    def all(self) -> tuple[ApplicationReviewSubmission, ...]:
        return tuple(self._submissions.values())
