from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)


def test_create_application_event() -> None:
    application_id = uuid4()
    occurred_at = datetime(2026, 8, 17, 11, 0, tzinfo=UTC)

    event = ApplicationEvent.create(
        application_id=application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.APPLICATION_CREATED,
        actor_id="USER-001",
        occurred_at=occurred_at,
    )

    assert event.application_id == application_id
    assert event.user_id == "USER-001"
    assert event.event_type is ApplicationEventType.APPLICATION_CREATED
    assert event.actor_id == "USER-001"
    assert event.occurred_at == occurred_at


def test_application_events_receive_unique_ids() -> None:
    application_id = uuid4()

    first = ApplicationEvent.create(
        application_id=application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.APPLICATION_CREATED,
        actor_id="USER-001",
    )
    second = ApplicationEvent.create(
        application_id=application_id,
        user_id="USER-001",
        event_type=ApplicationEventType.STATUS_CHANGED,
        actor_id="USER-001",
    )

    assert first.event_id != second.event_id


def test_event_attributes_are_stored_immutably() -> None:
    event = ApplicationEvent.create(
        application_id=uuid4(),
        user_id="USER-001",
        event_type=ApplicationEventType.STATUS_CHANGED,
        actor_id="USER-001",
        attributes={
            "previous_status": "saved",
            "new_status": "preparing",
        },
    )

    assert dict(event.attributes) == {
        "new_status": "preparing",
        "previous_status": "saved",
    }


def test_application_event_is_immutable() -> None:
    event = ApplicationEvent.create(
        application_id=uuid4(),
        user_id="USER-001",
        event_type=ApplicationEventType.APPLICATION_CREATED,
        actor_id="USER-001",
    )

    with pytest.raises(FrozenInstanceError):
        event.actor_id = "USER-999"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", ""),
        ("actor_id", "   "),
    ],
)
def test_application_event_rejects_blank_identity_fields(
    field: str,
    value: str,
) -> None:
    values = {
        "user_id": "USER-001",
        "actor_id": "USER-001",
    }
    values[field] = value

    with pytest.raises(ValueError):
        ApplicationEvent.create(
            application_id=uuid4(),
            user_id=values["user_id"],
            event_type=ApplicationEventType.APPLICATION_CREATED,
            actor_id=values["actor_id"],
        )
