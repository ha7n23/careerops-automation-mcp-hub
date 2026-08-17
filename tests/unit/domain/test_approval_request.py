from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.approval_request import (
    ApprovalActionType,
    ApprovalRequest,
    ApprovalRequestExpired,
    ApprovalRequestStatus,
    InvalidApprovalRequestTransition,
)


def test_create_approval_request_starts_pending() -> None:
    application_id = uuid4()
    created_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
    expires_at = created_at + timedelta(hours=24)

    approval = ApprovalRequest.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
        payload={"cv_version_id": "CVV-001"},
        created_at=created_at,
        expires_at=expires_at,
    )

    assert approval.application_id == application_id
    assert approval.user_id == "USER-001"
    assert approval.action_type is ApprovalActionType.SUBMIT_APPLICATION
    assert approval.requested_by == "OPENCLAW"
    assert approval.status is ApprovalRequestStatus.PENDING
    assert dict(approval.payload) == {"cv_version_id": "CVV-001"}
    assert approval.created_at == created_at
    assert approval.expires_at == expires_at
    assert approval.decided_at is None
    assert approval.decided_by is None


def test_approval_requests_receive_unique_ids() -> None:
    application_id = uuid4()

    first = ApprovalRequest.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
    )
    second = ApprovalRequest.create(
        application_id=application_id,
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
    )

    assert first.approval_id != second.approval_id


def test_approve_pending_request() -> None:
    decided_at = datetime(2026, 8, 17, 13, 0, tzinfo=UTC)

    approval = ApprovalRequest.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ApprovalActionType.SEND_EXTERNAL_MESSAGE,
        requested_by="OPENCLAW",
    )

    approval.approve(
        decided_by="USER-001",
        at=decided_at,
    )

    assert approval.status is ApprovalRequestStatus.APPROVED
    assert approval.decided_by == "USER-001"
    assert approval.decided_at == decided_at


def test_reject_pending_request() -> None:
    approval = ApprovalRequest.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
    )

    approval.reject(decided_by="USER-001")

    assert approval.status is ApprovalRequestStatus.REJECTED
    assert approval.decided_by == "USER-001"
    assert approval.decided_at is not None


def test_decided_request_cannot_be_decided_again() -> None:
    approval = ApprovalRequest.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
    )

    approval.approve(decided_by="USER-001")

    with pytest.raises(InvalidApprovalRequestTransition):
        approval.reject(decided_by="USER-001")


def test_expired_request_cannot_be_approved() -> None:
    created_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    approval = ApprovalRequest.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
        created_at=created_at,
        expires_at=created_at + timedelta(hours=1),
    )

    with pytest.raises(ApprovalRequestExpired):
        approval.approve(
            decided_by="USER-001",
            at=created_at + timedelta(hours=2),
        )

    assert approval.status is ApprovalRequestStatus.PENDING


def test_pending_request_can_be_marked_expired() -> None:
    approval = ApprovalRequest.create(
        application_id=uuid4(),
        user_id="USER-001",
        action_type=ApprovalActionType.SUBMIT_APPLICATION,
        requested_by="OPENCLAW",
    )

    approval.expire()

    assert approval.status is ApprovalRequestStatus.EXPIRED


def test_expiry_must_be_after_creation() -> None:
    created_at = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

    with pytest.raises(ValueError):
        ApprovalRequest.create(
            application_id=uuid4(),
            user_id="USER-001",
            action_type=ApprovalActionType.SUBMIT_APPLICATION,
            requested_by="OPENCLAW",
            created_at=created_at,
            expires_at=created_at,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", ""),
        ("requested_by", "   "),
    ],
)
def test_create_approval_request_rejects_blank_identity_fields(
    field: str,
    value: str,
) -> None:
    values = {
        "user_id": "USER-001",
        "requested_by": "OPENCLAW",
    }
    values[field] = value

    with pytest.raises(ValueError):
        ApprovalRequest.create(
            application_id=uuid4(),
            user_id=values["user_id"],
            action_type=ApprovalActionType.SUBMIT_APPLICATION,
            requested_by=values["requested_by"],
        )
