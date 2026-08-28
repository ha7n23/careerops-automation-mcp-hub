from collections.abc import Mapping
from datetime import datetime
from typing import Protocol
from uuid import UUID

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyClaim,
    IdempotencyOperation,
)
from careerops_automation_mcp_hub.domain.action_item import ActionItem
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


class JobApplicationRepository(Protocol):
    async def add(self, application: JobApplication) -> None:
        """Persist a new job application."""

    async def get(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> JobApplication | None:
        """Return a user-scoped application if it exists."""

    async def save(self, application: JobApplication) -> None:
        """Persist changes to an existing application."""

    async def list_for_user(
        self,
        *,
        user_id: str,
        status: ApplicationStatus | None = None,
    ) -> tuple[JobApplication, ...]:
        """Return applications available to one user."""
        ...


class ApplicationEventRepository(Protocol):
    async def add(self, event: ApplicationEvent) -> None:
        """Persist an application event."""


class ActionItemRepository(Protocol):
    async def add(self, action: ActionItem) -> None:
        """Persist an action item."""

    async def list_pending(
        self,
        *,
        user_id: str,
        due_before: datetime | None = None,
    ) -> tuple[ActionItem, ...]:
        """Return pending actions available to one user."""
        ...


class ApplicationPreparationRepository(Protocol):
    async def add(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        """Persist a new application-preparation workflow."""

    async def get_for_application(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> ApplicationPreparation | None:
        """Return the preparation workflow for one user-scoped application."""

    async def get_for_application_for_update(
        self,
        *,
        user_id: str,
        application_id: UUID,
    ) -> ApplicationPreparation | None:
        """Lock and return one preparation for orchestration."""

    async def save(
        self,
        preparation: ApplicationPreparation,
    ) -> None:
        """Persist changes to an existing preparation workflow."""


class ApplicationReviewSubmissionRepository(Protocol):
    async def add(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        """Persist a new human-review submission."""

    async def get_by_idempotency_key(
        self,
        *,
        user_id: str,
        idempotency_key: str,
    ) -> ApplicationReviewSubmission | None:
        """Return one user-scoped review submission."""

    async def get_unresolved_for_preparation(
        self,
        *,
        user_id: str,
        preparation_id: UUID,
    ) -> ApplicationReviewSubmission | None:
        """Return an unresolved review that blocks another submission."""

    async def save(
        self,
        submission: ApplicationReviewSubmission,
    ) -> None:
        """Persist changes to an existing review submission."""


class IdempotencyRepository(Protocol):
    async def claim(
        self,
        *,
        user_id: str,
        operation: IdempotencyOperation,
        idempotency_key: str,
        request_fingerprint: str,
        created_at: datetime,
    ) -> IdempotencyClaim:
        """Attempt to acquire a scoped idempotency key."""
        ...

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
        """Store the successful result for an acquired key."""
        ...
