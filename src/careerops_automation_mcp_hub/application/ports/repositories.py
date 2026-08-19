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
