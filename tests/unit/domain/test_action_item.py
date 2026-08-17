from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
    InvalidActionItemTransition,
)


def test_create_action_item_starts_pending() -> None:
    application_id = uuid4()
    created_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    due_at = created_at + timedelta(days=7)

    action = ActionItem.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up with recruiter.",
        due_at=due_at,
        created_at=created_at,
    )

    assert action.application_id == application_id
    assert action.user_id == "USER-001"
    assert action.action_type is ActionItemType.FOLLOW_UP
    assert action.status is ActionItemStatus.PENDING
    assert action.description == "Follow up with recruiter."
    assert action.due_at == due_at
    assert action.created_at == created_at
    assert action.completed_at is None


def test_action_items_receive_unique_ids() -> None:
    application_id = uuid4()

    first = ActionItem.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ActionItemType.REVIEW_CV,
        description="Review CV.",
    )
    second = ActionItem.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up.",
    )

    assert first.action_id != second.action_id


def test_complete_action_item() -> None:
    completed_at = datetime(2026, 8, 17, 15, 0, tzinfo=UTC)

    action = ActionItem.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ActionItemType.PREPARE_INTERVIEW,
        description="Prepare for interview.",
    )

    action.complete(at=completed_at)

    assert action.status is ActionItemStatus.COMPLETED
    assert action.completed_at == completed_at


def test_cancel_action_item() -> None:
    action = ActionItem.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ActionItemType.CHECK_STATUS,
        description="Check application status.",
    )

    action.cancel()

    assert action.status is ActionItemStatus.CANCELLED
    assert action.completed_at is None


@pytest.mark.parametrize(
    "final_status",
    [
        ActionItemStatus.COMPLETED,
        ActionItemStatus.CANCELLED,
    ],
)
def test_finished_action_cannot_be_completed_again(
    final_status: ActionItemStatus,
) -> None:
    action = ActionItem.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up.",
    )

    if final_status is ActionItemStatus.COMPLETED:
        action.complete()
    else:
        action.cancel()

    with pytest.raises(InvalidActionItemTransition):
        action.complete()


def test_completed_action_cannot_be_cancelled() -> None:
    action = ActionItem.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up.",
    )

    action.complete()

    with pytest.raises(InvalidActionItemTransition):
        action.cancel()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", ""),
        ("description", "   "),
    ],
)
def test_create_action_item_rejects_blank_required_fields(
    field: str,
    value: str,
) -> None:
    values = {
        "user_id": "USER-001",
        "description": "Follow up with recruiter.",
    }
    values[field] = value

    with pytest.raises(ValueError):
        ActionItem.create(
            application_id=uuid4(),
            user_id=values["user_id"],
            action_type=ActionItemType.FOLLOW_UP,
            description=values["description"],
        )
