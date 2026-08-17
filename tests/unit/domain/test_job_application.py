from datetime import UTC, datetime
from uuid import UUID

import pytest

from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    InvalidApplicationStatusTransition,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


def test_create_application_starts_saved() -> None:
    now = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
        now=now,
    )

    assert isinstance(application.application_id, UUID)
    assert application.user_id == "USER-001"
    assert application.company_name == "Monzo"
    assert application.role_title == "Junior AI Engineer"
    assert application.status is ApplicationStatus.SAVED
    assert application.created_at == now
    assert application.updated_at == now


def test_create_application_generates_unique_ids() -> None:
    first = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="AI Engineer",
    )
    second = JobApplication.create(
        user_id="USER-001",
        company_name="Revolut",
        role_title="AI Engineer",
    )

    assert first.application_id != second.application_id


def test_transition_updates_status_and_timestamp() -> None:
    created_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
    transitioned_at = datetime(2026, 8, 17, 11, 0, tzinfo=UTC)

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
        now=created_at,
    )

    application.transition_to(
        ApplicationStatus.PREPARING,
        at=transitioned_at,
    )

    assert application.status is ApplicationStatus.PREPARING
    assert application.updated_at == transitioned_at
    assert application.created_at == created_at


def test_invalid_transition_does_not_mutate_application() -> None:
    created_at = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)

    application = JobApplication.create(
        user_id="USER-001",
        company_name="Monzo",
        role_title="Junior AI Engineer",
        now=created_at,
    )

    with pytest.raises(InvalidApplicationStatusTransition):
        application.transition_to(ApplicationStatus.OFFER)

    assert application.status is ApplicationStatus.SAVED
    assert application.updated_at == created_at


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", ""),
        ("company_name", "   "),
        ("role_title", ""),
    ],
)
def test_create_application_rejects_blank_required_fields(
    field: str,
    value: str,
) -> None:
    values = {
        "user_id": "USER-001",
        "company_name": "Monzo",
        "role_title": "Junior AI Engineer",
    }
    values[field] = value

    with pytest.raises(ValueError):
        JobApplication.create(
            user_id=values["user_id"],
            company_name=values["company_name"],
            role_title=values["role_title"],
        )
