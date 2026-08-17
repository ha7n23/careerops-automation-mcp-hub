import pytest

from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    InvalidApplicationStatusTransition,
    ensure_valid_status_transition,
)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ApplicationStatus.SAVED, ApplicationStatus.PREPARING),
        (ApplicationStatus.SAVED, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.PREPARING, ApplicationStatus.READY_TO_APPLY),
        (ApplicationStatus.PREPARING, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.READY_TO_APPLY, ApplicationStatus.APPLIED),
        (ApplicationStatus.READY_TO_APPLY, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING),
        (ApplicationStatus.APPLIED, ApplicationStatus.REJECTED),
        (ApplicationStatus.APPLIED, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.INTERVIEWING, ApplicationStatus.OFFER),
        (ApplicationStatus.INTERVIEWING, ApplicationStatus.REJECTED),
        (ApplicationStatus.INTERVIEWING, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.OFFER, ApplicationStatus.CLOSED),
        (ApplicationStatus.OFFER, ApplicationStatus.WITHDRAWN),
        (ApplicationStatus.REJECTED, ApplicationStatus.CLOSED),
        (ApplicationStatus.WITHDRAWN, ApplicationStatus.CLOSED),
    ],
)
def test_valid_status_transitions_are_allowed(
    current: ApplicationStatus,
    target: ApplicationStatus,
) -> None:
    ensure_valid_status_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ApplicationStatus.SAVED, ApplicationStatus.APPLIED),
        (ApplicationStatus.SAVED, ApplicationStatus.OFFER),
        (ApplicationStatus.PREPARING, ApplicationStatus.INTERVIEWING),
        (ApplicationStatus.READY_TO_APPLY, ApplicationStatus.OFFER),
        (ApplicationStatus.REJECTED, ApplicationStatus.INTERVIEWING),
        (ApplicationStatus.WITHDRAWN, ApplicationStatus.APPLIED),
        (ApplicationStatus.CLOSED, ApplicationStatus.SAVED),
        (ApplicationStatus.CLOSED, ApplicationStatus.INTERVIEWING),
    ],
)
def test_invalid_status_transitions_are_rejected(
    current: ApplicationStatus,
    target: ApplicationStatus,
) -> None:
    with pytest.raises(InvalidApplicationStatusTransition):
        ensure_valid_status_transition(current, target)


def test_transition_to_same_status_is_rejected() -> None:
    with pytest.raises(InvalidApplicationStatusTransition):
        ensure_valid_status_transition(
            ApplicationStatus.APPLIED,
            ApplicationStatus.APPLIED,
        )
