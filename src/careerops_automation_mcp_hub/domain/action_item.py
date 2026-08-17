from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ActionItemType(StrEnum):
    REVIEW_CV = "review_cv"
    SUBMIT_APPLICATION = "submit_application"
    FOLLOW_UP = "follow_up"
    CHECK_STATUS = "check_status"
    PREPARE_INTERVIEW = "prepare_interview"
    RECORD_OUTCOME = "record_outcome"


class ActionItemStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvalidActionItemTransition(ValueError):
    """Raised when an action item cannot move to the requested state."""


@dataclass(slots=True)
class ActionItem:
    action_id: UUID
    application_id: UUID
    user_id: str
    action_type: ActionItemType
    description: str
    status: ActionItemStatus
    due_at: datetime | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        user_id: str,
        action_type: ActionItemType,
        description: str,
        due_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> "ActionItem":
        """Create a pending action associated with an application."""
        cls._ensure_not_blank("user_id", user_id)
        cls._ensure_not_blank("description", description)

        return cls(
            action_id=uuid4(),
            application_id=application_id,
            user_id=user_id.strip(),
            action_type=action_type,
            description=description.strip(),
            status=ActionItemStatus.PENDING,
            due_at=due_at,
            created_at=created_at or datetime.now(UTC),
            completed_at=None,
        )

    def complete(self, *, at: datetime | None = None) -> None:
        """Mark a pending action as completed."""
        self._ensure_pending()
        self.status = ActionItemStatus.COMPLETED
        self.completed_at = at or datetime.now(UTC)

    def cancel(self) -> None:
        """Cancel a pending action."""
        self._ensure_pending()
        self.status = ActionItemStatus.CANCELLED

    def _ensure_pending(self) -> None:
        if self.status is not ActionItemStatus.PENDING:
            raise InvalidActionItemTransition(
                f"Action item in status {self.status.value!r} cannot be changed."
            )

    @staticmethod
    def _ensure_not_blank(field_name: str, value: str) -> None:
        if not value.strip():
            raise ValueError(f"{field_name} must not be blank.")
