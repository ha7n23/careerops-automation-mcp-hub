"""Tests for durable Agent Engine human-review submissions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewEdit,
    ApplicationReviewOutcome,
    ApplicationReviewSubmission,
    ApplicationReviewSubmissionStatus,
)


def _build_submission() -> ApplicationReviewSubmission:
    return ApplicationReviewSubmission.create(
        preparation_id=uuid4(),
        application_id=uuid4(),
        user_id=" USER-001 ",
        thread_id=" THR-001 ",
        idempotency_key=" review-001 ",
        action=ApplicationReviewAction.APPROVE,
        approved_proposal_ids=("EVP-001",),
    )


def test_create_review_submission_is_pending() -> None:
    now = datetime(2026, 8, 25, 18, 0, tzinfo=UTC)

    submission = ApplicationReviewSubmission.create(
        preparation_id=uuid4(),
        application_id=uuid4(),
        user_id=" USER-001 ",
        thread_id=" THR-001 ",
        idempotency_key=" review-001 ",
        action=ApplicationReviewAction.APPROVE,
        approved_proposal_ids=("EVP-001",),
        now=now,
    )

    assert submission.user_id == "USER-001"
    assert submission.thread_id == "THR-001"
    assert submission.idempotency_key == "review-001"

    assert submission.status is ApplicationReviewSubmissionStatus.PENDING
    assert submission.outcome is None
    assert submission.error_message is None
    assert submission.created_at == now
    assert submission.updated_at == now


def test_review_edit_normalizes_values() -> None:
    edit = ApplicationReviewEdit(
        proposal_id=" EVP-001 ",
        edited_text=" Improved grounded CV statement. ",
    )

    assert edit.proposal_id == "EVP-001"
    assert edit.edited_text == "Improved grounded CV statement."


def test_pending_review_can_be_marked_submitting() -> None:
    submission = _build_submission()

    submission.mark_submitting()

    assert submission.status is ApplicationReviewSubmissionStatus.SUBMITTING


def test_submitting_review_can_complete() -> None:
    submission = _build_submission()
    submission.mark_submitting()

    submission.mark_completed(
        outcome=ApplicationReviewOutcome.COMPLETED,
    )

    assert submission.status is ApplicationReviewSubmissionStatus.COMPLETED
    assert submission.outcome is ApplicationReviewOutcome.COMPLETED
    assert submission.error_message is None


def test_submitting_review_can_fail() -> None:
    submission = _build_submission()
    submission.mark_submitting()

    submission.mark_failed(
        error_message="Agent Engine rejected the review.",
    )

    assert submission.status is ApplicationReviewSubmissionStatus.FAILED
    assert submission.outcome is None
    assert submission.error_message == "Agent Engine rejected the review."


def test_submitting_review_can_record_unknown_outcome() -> None:
    submission = _build_submission()
    submission.mark_submitting()

    submission.mark_outcome_unknown(
        error_message="Agent Engine request timed out.",
    )

    assert submission.status is ApplicationReviewSubmissionStatus.OUTCOME_UNKNOWN
    assert submission.outcome is None
    assert submission.error_message == "Agent Engine request timed out."


def test_pending_review_cannot_complete_directly() -> None:
    submission = _build_submission()

    with pytest.raises(
        ValueError,
        match="only be recorded after submitting",
    ):
        submission.mark_completed(
            outcome=ApplicationReviewOutcome.COMPLETED,
        )


def test_completed_review_cannot_be_changed_to_failed() -> None:
    submission = _build_submission()
    submission.mark_submitting()
    submission.mark_completed(
        outcome=ApplicationReviewOutcome.COMPLETED,
    )

    with pytest.raises(
        ValueError,
        match="only be recorded after submitting",
    ):
        submission.mark_failed(
            error_message="Late failure.",
        )


def test_duplicate_proposal_ids_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="must not contain duplicates",
    ):
        ApplicationReviewSubmission.create(
            preparation_id=uuid4(),
            application_id=uuid4(),
            user_id="USER-001",
            thread_id="THR-001",
            idempotency_key="review-001",
            action=ApplicationReviewAction.APPROVE,
            approved_proposal_ids=(
                "EVP-001",
                "EVP-001",
            ),
        )
