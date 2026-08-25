"""Unit tests for durable application-preparation state transitions."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
)


def test_create_application_preparation() -> None:
    """A new preparation should start in the pending state."""

    application_id = uuid4()
    now = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)

    preparation = ApplicationPreparation.create(
        application_id=application_id,
        user_id="USER-123",
        now=now,
    )

    assert preparation.application_id == application_id
    assert preparation.user_id == "USER-123"
    assert preparation.status is ApplicationPreparationStatus.PENDING
    assert preparation.agent_engine_job_id == str(application_id)
    assert preparation.agent_engine_thread_id is None
    assert preparation.error_message is None
    assert preparation.created_at == now
    assert preparation.updated_at == now


def test_pending_preparation_can_start() -> None:
    """A pending preparation should transition to starting."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    at = datetime(2026, 8, 25, 10, 1, tzinfo=UTC)

    preparation.mark_starting(at=at)

    assert preparation.status is ApplicationPreparationStatus.STARTING
    assert preparation.updated_at == at


def test_starting_preparation_can_await_review() -> None:
    """A successful remote pause should persist the Agent Engine thread."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    preparation.mark_starting()

    at = datetime(2026, 8, 25, 10, 2, tzinfo=UTC)

    preparation.mark_awaiting_review(
        thread_id="THR-123",
        at=at,
    )

    assert preparation.status is ApplicationPreparationStatus.AWAITING_REVIEW
    assert preparation.agent_engine_thread_id == "THR-123"
    assert preparation.error_message is None
    assert preparation.updated_at == at


def test_starting_preparation_can_complete() -> None:
    """A completed remote analysis should persist its thread identifier."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    preparation.mark_starting()

    preparation.mark_completed(thread_id="THR-456")

    assert preparation.status is ApplicationPreparationStatus.COMPLETED
    assert preparation.agent_engine_thread_id == "THR-456"
    assert preparation.error_message is None


def test_starting_preparation_can_fail() -> None:
    """A known failure should be recorded durably."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    preparation.mark_starting()

    preparation.mark_failed(
        error_message="Agent Engine rejected the request.",
    )

    assert preparation.status is ApplicationPreparationStatus.FAILED
    assert preparation.agent_engine_thread_id is None
    assert preparation.error_message == "Agent Engine rejected the request."


def test_starting_preparation_can_record_unknown_outcome() -> None:
    """An ambiguous remote outcome should prevent blind retries."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    preparation.mark_starting()

    preparation.mark_outcome_unknown(
        error_message="Agent Engine request timed out.",
    )

    assert preparation.status is ApplicationPreparationStatus.OUTCOME_UNKNOWN
    assert preparation.agent_engine_thread_id is None
    assert preparation.error_message == "Agent Engine request timed out."


def test_pending_preparation_cannot_complete_directly() -> None:
    """A preparation must be marked starting before recording a result."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )

    with pytest.raises(
        ValueError,
        match="Preparation result can only be recorded after starting",
    ):
        preparation.mark_completed(thread_id="THR-123")


def test_completed_preparation_cannot_be_marked_failed() -> None:
    """A terminal successful preparation must not later become failed."""

    preparation = ApplicationPreparation.create(
        application_id=uuid4(),
        user_id="USER-123",
    )
    preparation.mark_starting()
    preparation.mark_completed(thread_id="THR-123")

    with pytest.raises(
        ValueError,
        match="Preparation result can only be recorded after starting",
    ):
        preparation.mark_failed(error_message="Late failure.")
