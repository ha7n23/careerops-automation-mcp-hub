from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ApplicationReviewAction(StrEnum):
    """Human actions supported by the application-preparation review."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    REGENERATE = "regenerate"


class ApplicationReviewSubmissionStatus(StrEnum):
    """Durable state of one human-review submission."""

    PENDING = "pending"
    SUBMITTING = "submitting"
    COMPLETED = "completed"
    FAILED = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


class ApplicationReviewOutcome(StrEnum):
    """Agent Engine workflow state returned after an accepted review."""

    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ApplicationReviewEdit:
    """One human replacement for an Agent Engine CV proposal."""

    proposal_id: str
    edited_text: str

    def __post_init__(self) -> None:
        proposal_id = self.proposal_id.strip()
        edited_text = self.edited_text.strip()

        if not proposal_id:
            raise ValueError("proposal_id must not be blank.")

        if not edited_text:
            raise ValueError("edited_text must not be blank.")

        object.__setattr__(self, "proposal_id", proposal_id)
        object.__setattr__(self, "edited_text", edited_text)


@dataclass(slots=True)
class ApplicationReviewSubmission:
    """Durable record of one human decision sent to the Agent Engine."""

    review_submission_id: UUID
    preparation_id: UUID
    application_id: UUID
    user_id: str
    thread_id: str
    idempotency_key: str

    action: ApplicationReviewAction
    approved_proposal_ids: tuple[str, ...]
    rejected_proposal_ids: tuple[str, ...]
    edits: tuple[ApplicationReviewEdit, ...]
    reviewer_comment: str | None

    status: ApplicationReviewSubmissionStatus
    outcome: ApplicationReviewOutcome | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        preparation_id: UUID,
        application_id: UUID,
        user_id: str,
        thread_id: str,
        idempotency_key: str,
        action: ApplicationReviewAction,
        approved_proposal_ids: tuple[str, ...] = (),
        rejected_proposal_ids: tuple[str, ...] = (),
        edits: tuple[ApplicationReviewEdit, ...] = (),
        reviewer_comment: str | None = None,
        now: datetime | None = None,
    ) -> "ApplicationReviewSubmission":
        """Create a durable review before crossing the HTTP boundary."""

        normalized_user_id = _require_text(
            "user_id",
            user_id,
        )
        normalized_thread_id = _require_text(
            "thread_id",
            thread_id,
        )
        normalized_idempotency_key = _require_text(
            "idempotency_key",
            idempotency_key,
        )

        normalized_approved_ids = _normalize_proposal_ids(approved_proposal_ids)
        normalized_rejected_ids = _normalize_proposal_ids(rejected_proposal_ids)

        edit_ids = [edit.proposal_id for edit in edits]

        if len(edit_ids) != len(set(edit_ids)):
            raise ValueError("edits must not contain duplicate proposal IDs.")

        normalized_comment = (
            reviewer_comment.strip() if reviewer_comment is not None else None
        )

        if normalized_comment == "":
            normalized_comment = None

        timestamp = now or datetime.now(UTC)

        return cls(
            review_submission_id=uuid4(),
            preparation_id=preparation_id,
            application_id=application_id,
            user_id=normalized_user_id,
            thread_id=normalized_thread_id,
            idempotency_key=normalized_idempotency_key,
            action=action,
            approved_proposal_ids=normalized_approved_ids,
            rejected_proposal_ids=normalized_rejected_ids,
            edits=edits,
            reviewer_comment=normalized_comment,
            status=ApplicationReviewSubmissionStatus.PENDING,
            outcome=None,
            error_message=None,
            created_at=timestamp,
            updated_at=timestamp,
        )

    def mark_submitting(
        self,
        *,
        at: datetime | None = None,
    ) -> None:
        """Record the point immediately before the remote review call."""

        if self.status is not ApplicationReviewSubmissionStatus.PENDING:
            raise ValueError("Only a pending review submission can be submitted.")

        self.status = ApplicationReviewSubmissionStatus.SUBMITTING
        self.updated_at = at or datetime.now(UTC)

    def mark_completed(
        self,
        *,
        outcome: ApplicationReviewOutcome,
        at: datetime | None = None,
    ) -> None:
        """Record a known successful Agent Engine review response."""

        self._ensure_submitting()

        self.status = ApplicationReviewSubmissionStatus.COMPLETED
        self.outcome = outcome
        self.error_message = None
        self.updated_at = at or datetime.now(UTC)

    def mark_failed(
        self,
        *,
        error_message: str,
        at: datetime | None = None,
    ) -> None:
        """Record a definitive rejection of the review request."""

        self._ensure_submitting()

        self.status = ApplicationReviewSubmissionStatus.FAILED
        self.outcome = None
        self.error_message = _require_text(
            "error_message",
            error_message,
        )
        self.updated_at = at or datetime.now(UTC)

    def mark_outcome_unknown(
        self,
        *,
        error_message: str,
        at: datetime | None = None,
    ) -> None:
        """Record an ambiguous review result that must not be retried blindly."""

        self._ensure_submitting()

        self.status = ApplicationReviewSubmissionStatus.OUTCOME_UNKNOWN
        self.outcome = None
        self.error_message = _require_text(
            "error_message",
            error_message,
        )
        self.updated_at = at or datetime.now(UTC)

    def _ensure_submitting(self) -> None:
        if self.status is not ApplicationReviewSubmissionStatus.SUBMITTING:
            raise ValueError("A review result can only be recorded after submitting.")


def _require_text(
    field_name: str,
    value: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")

    return normalized


def _normalize_proposal_ids(
    proposal_ids: tuple[str, ...],
) -> tuple[str, ...]:
    normalized = tuple(
        _require_text("proposal_id", proposal_id) for proposal_id in proposal_ids
    )

    if len(normalized) != len(set(normalized)):
        raise ValueError("Proposal ID collections must not contain duplicates.")

    return normalized
