from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    ensure_valid_status_transition,
)


@dataclass(slots=True)
class JobApplication:
    application_id: UUID
    user_id: str
    company_name: str
    role_title: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        user_id: str,
        company_name: str,
        role_title: str,
        now: datetime | None = None,
    ) -> "JobApplication":
        """Create a new saved job application."""
        cls._ensure_not_blank("user_id", user_id)
        cls._ensure_not_blank("company_name", company_name)
        cls._ensure_not_blank("role_title", role_title)

        timestamp = now or datetime.now(UTC)

        return cls(
            application_id=uuid4(),
            user_id=user_id.strip(),
            company_name=company_name.strip(),
            role_title=role_title.strip(),
            status=ApplicationStatus.SAVED,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def transition_to(
        self,
        target: ApplicationStatus,
        *,
        at: datetime | None = None,
    ) -> None:
        """Move the application to another valid lifecycle state."""
        ensure_valid_status_transition(self.status, target)

        self.status = target
        self.updated_at = at or datetime.now(UTC)

    @staticmethod
    def _ensure_not_blank(field_name: str, value: str) -> None:
        if not value.strip():
            raise ValueError(f"{field_name} must not be blank.")
