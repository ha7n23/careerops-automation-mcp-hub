import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from uuid import UUID

from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication

MAX_IDEMPOTENCY_KEY_LENGTH = 128


class IdempotencyOperation(StrEnum):
    """Write operations protected by durable idempotency."""

    CREATE_APPLICATION = "create_application"
    UPDATE_APPLICATION_STATUS = "update_application_status"


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    """Result of attempting to acquire an idempotency key."""

    acquired: bool
    request_fingerprint: str
    response_payload: dict[str, object] | None


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for another request."""


class IdempotencyReplayUnavailableError(RuntimeError):
    """Raised when a stored idempotency result cannot be replayed."""


def normalize_idempotency_key(value: str) -> str:
    """Validate and normalize a caller-supplied idempotency key."""
    normalized = value.strip()

    if not normalized:
        raise ValueError("idempotency_key must not be blank.")

    if len(normalized) > MAX_IDEMPOTENCY_KEY_LENGTH:
        raise ValueError(
            f"idempotency_key must not exceed {MAX_IDEMPOTENCY_KEY_LENGTH} characters."
        )

    return normalized


def build_request_fingerprint(
    values: Mapping[str, str],
) -> str:
    """Return a deterministic SHA-256 fingerprint for request semantics."""
    canonical_request = json.dumps(
        dict(values),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )

    return sha256(canonical_request.encode("utf-8")).hexdigest()


def resolve_idempotency_claim(
    claim: IdempotencyClaim,
    *,
    request_fingerprint: str,
) -> dict[str, object] | None:
    """Return a replay payload or validate ownership of a new claim."""
    if claim.acquired:
        return None

    if claim.request_fingerprint != request_fingerprint:
        raise IdempotencyConflictError(
            "Idempotency key was already used for a different request."
        )

    if claim.response_payload is None:
        raise IdempotencyReplayUnavailableError(
            "Idempotency result is not available for replay."
        )

    return dict(claim.response_payload)


def build_application_mutation_payload(
    *,
    application: JobApplication,
    event: ApplicationEvent,
) -> dict[str, object]:
    """Serialize an application mutation result for durable replay."""
    return {
        "application": {
            "application_id": str(application.application_id),
            "user_id": application.user_id,
            "company_name": application.company_name,
            "role_title": application.role_title,
            "status": application.status.value,
            "created_at": application.created_at.isoformat(),
            "updated_at": application.updated_at.isoformat(),
        },
        "event": {
            "event_id": str(event.event_id),
            "application_id": str(event.application_id),
            "user_id": event.user_id,
            "event_type": event.event_type.value,
            "actor_id": event.actor_id,
            "occurred_at": event.occurred_at.isoformat(),
            "attributes": dict(event.attributes),
        },
    }


def restore_application_mutation_payload(
    payload: Mapping[str, object],
) -> tuple[JobApplication, ApplicationEvent]:
    """Rehydrate the original mutation result from an idempotency payload."""
    application_payload = _require_mapping(
        payload,
        "application",
    )
    event_payload = _require_mapping(
        payload,
        "event",
    )
    attributes_payload = _require_mapping(
        event_payload,
        "attributes",
    )

    attributes: list[tuple[str, str]] = []

    for key, value in attributes_payload.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise IdempotencyReplayUnavailableError(
                "Stored idempotency event attributes are invalid."
            )

        attributes.append((key, value))

    try:
        application = JobApplication(
            application_id=UUID(
                _require_string(
                    application_payload,
                    "application_id",
                )
            ),
            user_id=_require_string(
                application_payload,
                "user_id",
            ),
            company_name=_require_string(
                application_payload,
                "company_name",
            ),
            role_title=_require_string(
                application_payload,
                "role_title",
            ),
            status=ApplicationStatus(
                _require_string(
                    application_payload,
                    "status",
                )
            ),
            created_at=datetime.fromisoformat(
                _require_string(
                    application_payload,
                    "created_at",
                )
            ),
            updated_at=datetime.fromisoformat(
                _require_string(
                    application_payload,
                    "updated_at",
                )
            ),
        )

        event = ApplicationEvent(
            event_id=UUID(
                _require_string(
                    event_payload,
                    "event_id",
                )
            ),
            application_id=UUID(
                _require_string(
                    event_payload,
                    "application_id",
                )
            ),
            user_id=_require_string(
                event_payload,
                "user_id",
            ),
            event_type=ApplicationEventType(
                _require_string(
                    event_payload,
                    "event_type",
                )
            ),
            actor_id=_require_string(
                event_payload,
                "actor_id",
            ),
            occurred_at=datetime.fromisoformat(
                _require_string(
                    event_payload,
                    "occurred_at",
                )
            ),
            attributes=tuple(sorted(attributes)),
        )
    except ValueError as exc:
        raise IdempotencyReplayUnavailableError(
            "Stored idempotency result is invalid."
        ) from exc

    if (
        event.application_id != application.application_id
        or event.user_id != application.user_id
    ):
        raise IdempotencyReplayUnavailableError(
            "Stored idempotency result is inconsistent."
        )

    return application, event


def _require_mapping(
    payload: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    value = payload.get(key)

    if not isinstance(value, dict):
        raise IdempotencyReplayUnavailableError(
            f"Stored idempotency field '{key}' is invalid."
        )

    return value


def _require_string(
    payload: Mapping[str, object],
    key: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str):
        raise IdempotencyReplayUnavailableError(
            f"Stored idempotency field '{key}' is invalid."
        )

    return value
