from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ApplicationPreparationStatus(StrEnum):
    """Durable state of one application-preparation workflow."""

    PENDING = "pending"
    STARTING = "starting"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


@dataclass(slots=True)
class ApplicationPreparation:
    """Durable orchestration state for one Agent Engine analysis."""

    preparation_id: UUID
    application_id: UUID
    user_id: str
    status: ApplicationPreparationStatus
    agent_engine_job_id: str
    agent_engine_thread_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        user_id: str,
        now: datetime | None = None,
    ) -> "ApplicationPreparation":
        """Create preparation state before contacting the Agent Engine."""

        normalized_user_id = user_id.strip()

        if not normalized_user_id:
            raise ValueError("user_id must not be blank.")

        timestamp = now or datetime.now(UTC)

        return cls(
            preparation_id=uuid4(),
            application_id=application_id,
            user_id=normalized_user_id,
            status=ApplicationPreparationStatus.PENDING,
            agent_engine_job_id=str(application_id),
            agent_engine_thread_id=None,
            error_message=None,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def mark_starting(
        self,
        *,
        at: datetime | None = None,
    ) -> None:
        """Record that the remote analysis request is being initiated."""

        if self.status is not ApplicationPreparationStatus.PENDING:
            raise ValueError("Only a pending preparation can be started.")

        self.status = ApplicationPreparationStatus.STARTING
        self.updated_at = at or datetime.now(UTC)

    def mark_awaiting_review(
        self,
        *,
        thread_id: str,
        at: datetime | None = None,
    ) -> None:
        """Record a successful Agent Engine pause for human review."""

        self._ensure_starting()
        self._set_thread_id(thread_id)

        self.status = ApplicationPreparationStatus.AWAITING_REVIEW
        self.updated_at = at or datetime.now(UTC)

    def mark_completed(
        self,
        *,
        thread_id: str,
        at: datetime | None = None,
    ) -> None:
        """Record successful completion of Agent Engine analysis."""

        self._ensure_starting()
        self._set_thread_id(thread_id)

        self.status = ApplicationPreparationStatus.COMPLETED
        self.updated_at = at or datetime.now(UTC)

    def mark_completed_after_review(
        self,
        *,
        at: datetime | None = None,
    ) -> None:
        """Record completion after a successful human review."""

        if self.status is not ApplicationPreparationStatus.AWAITING_REVIEW:
            raise ValueError(
                "Only a preparation awaiting review can complete after review."
            )

        if self.agent_engine_thread_id is None:
            raise ValueError(
                "A preparation awaiting review must have an Agent Engine thread."
            )

        self.status = ApplicationPreparationStatus.COMPLETED
        self.error_message = None
        self.updated_at = at or datetime.now(UTC)

    def mark_failed(
        self,
        *,
        error_message: str,
        at: datetime | None = None,
    ) -> None:
        """Record a known unsuccessful remote operation."""

        self._ensure_starting()

        normalized_error = error_message.strip()

        if not normalized_error:
            raise ValueError("error_message must not be blank.")

        self.status = ApplicationPreparationStatus.FAILED
        self.error_message = normalized_error
        self.updated_at = at or datetime.now(UTC)

    def mark_outcome_unknown(
        self,
        *,
        error_message: str,
        at: datetime | None = None,
    ) -> None:
        """Record an ambiguous remote outcome that must not be auto-retried."""

        self._ensure_starting()

        normalized_error = error_message.strip()

        if not normalized_error:
            raise ValueError("error_message must not be blank.")

        self.status = ApplicationPreparationStatus.OUTCOME_UNKNOWN
        self.error_message = normalized_error
        self.updated_at = at or datetime.now(UTC)

    def _ensure_starting(self) -> None:
        if self.status is not ApplicationPreparationStatus.STARTING:
            raise ValueError("Preparation result can only be recorded after starting.")

    def _set_thread_id(self, thread_id: str) -> None:
        normalized_thread_id = thread_id.strip()

        if not normalized_thread_id:
            raise ValueError("thread_id must not be blank.")

        self.agent_engine_thread_id = normalized_thread_id
        self.error_message = None
