from enum import StrEnum


class ApplicationStatus(StrEnum):
    SAVED = "saved"
    PREPARING = "preparing"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


class InvalidApplicationStatusTransition(ValueError):
    """Raised when an application lifecycle transition is not allowed."""


_ALLOWED_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.SAVED: frozenset(
        {
            ApplicationStatus.PREPARING,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.PREPARING: frozenset(
        {
            ApplicationStatus.READY_TO_APPLY,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.READY_TO_APPLY: frozenset(
        {
            ApplicationStatus.APPLIED,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.APPLIED: frozenset(
        {
            ApplicationStatus.INTERVIEWING,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.INTERVIEWING: frozenset(
        {
            ApplicationStatus.OFFER,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.OFFER: frozenset(
        {
            ApplicationStatus.CLOSED,
            ApplicationStatus.WITHDRAWN,
        }
    ),
    ApplicationStatus.REJECTED: frozenset(
        {
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.WITHDRAWN: frozenset(
        {
            ApplicationStatus.CLOSED,
        }
    ),
    ApplicationStatus.CLOSED: frozenset(),
}


def ensure_valid_status_transition(
    current: ApplicationStatus,
    target: ApplicationStatus,
) -> None:
    """Raise if an application cannot move from current to target status."""
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidApplicationStatusTransition(
            f"Application cannot transition from {current.value!r} to {target.value!r}."
        )
