from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ApprovalActionType(StrEnum):
    SUBMIT_APPLICATION = "submit_application"
    SEND_EXTERNAL_MESSAGE = "send_external_message"
    CREATE_EXTERNAL_CALENDAR_EVENT = "create_external_calendar_event"


class ApprovalRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class InvalidApprovalRequestTransition(ValueError):
    """Raised when an approval request cannot change to the requested state."""


class ApprovalRequestExpired(ValueError):
    """Raised when an expired approval request is approved."""


@dataclass(slots=True)
class ApprovalRequest:
    approval_id: UUID
    application_id: UUID
    user_id: str
    action_type: ApprovalActionType
    requested_by: str
    payload: tuple[tuple[str, str], ...]
    status: ApprovalRequestStatus
    created_at: datetime
    expires_at: datetime | None
    decided_at: datetime | None
    decided_by: str | None

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        user_id: str,
        action_type: ApprovalActionType,
        requested_by: str,
        payload: Mapping[str, str] | None = None,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> "ApprovalRequest":
        """Create a pending request for human approval."""
        cls._ensure_not_blank("user_id", user_id)
        cls._ensure_not_blank("requested_by", requested_by)

        timestamp = created_at or datetime.now(UTC)

        if expires_at is not None and expires_at <= timestamp:
            raise ValueError("expires_at must be later than created_at.")

        return cls(
            approval_id=uuid4(),
            application_id=application_id,
            user_id=user_id.strip(),
            action_type=action_type,
            requested_by=requested_by.strip(),
            payload=tuple(sorted((payload or {}).items())),
            status=ApprovalRequestStatus.PENDING,
            created_at=timestamp,
            expires_at=expires_at,
            decided_at=None,
            decided_by=None,
        )

    def approve(
        self,
        *,
        decided_by: str,
        at: datetime | None = None,
    ) -> None:
        """Approve a pending request if it has not expired."""
        self._ensure_pending()
        self._ensure_not_blank("decided_by", decided_by)

        timestamp = at or datetime.now(UTC)

        if self.expires_at is not None and timestamp >= self.expires_at:
            raise ApprovalRequestExpired("Approval request has expired.")

        self.status = ApprovalRequestStatus.APPROVED
        self.decided_at = timestamp
        self.decided_by = decided_by.strip()

    def reject(
        self,
        *,
        decided_by: str,
        at: datetime | None = None,
    ) -> None:
        """Reject a pending request."""
        self._ensure_pending()
        self._ensure_not_blank("decided_by", decided_by)

        self.status = ApprovalRequestStatus.REJECTED
        self.decided_at = at or datetime.now(UTC)
        self.decided_by = decided_by.strip()

    def expire(self) -> None:
        """Mark a pending approval request as expired."""
        self._ensure_pending()
        self.status = ApprovalRequestStatus.EXPIRED

    def _ensure_pending(self) -> None:
        if self.status is not ApprovalRequestStatus.PENDING:
            raise InvalidApprovalRequestTransition(
                f"Approval request in status {self.status.value!r} cannot be changed."
            )

    @staticmethod
    def _ensure_not_blank(field_name: str, value: str) -> None:
        if not value.strip():
            raise ValueError(f"{field_name} must not be blank.")
