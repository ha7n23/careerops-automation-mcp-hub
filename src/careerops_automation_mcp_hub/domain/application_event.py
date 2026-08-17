from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ApplicationEventType(StrEnum):
    APPLICATION_CREATED = "application_created"
    STATUS_CHANGED = "status_changed"


@dataclass(frozen=True, slots=True)
class ApplicationEvent:
    event_id: UUID
    application_id: UUID
    user_id: str
    event_type: ApplicationEventType
    actor_id: str
    occurred_at: datetime
    attributes: tuple[tuple[str, str], ...]

    @classmethod
    def create(
        cls,
        *,
        application_id: UUID,
        user_id: str,
        event_type: ApplicationEventType,
        actor_id: str,
        occurred_at: datetime | None = None,
        attributes: Mapping[str, str] | None = None,
    ) -> "ApplicationEvent":
        """Create an immutable application timeline event."""
        cls._ensure_not_blank("user_id", user_id)
        cls._ensure_not_blank("actor_id", actor_id)

        return cls(
            event_id=uuid4(),
            application_id=application_id,
            user_id=user_id.strip(),
            event_type=event_type,
            actor_id=actor_id.strip(),
            occurred_at=occurred_at or datetime.now(UTC),
            attributes=tuple(sorted((attributes or {}).items())),
        )

    @staticmethod
    def _ensure_not_blank(field_name: str, value: str) -> None:
        if not value.strip():
            raise ValueError(f"{field_name} must not be blank.")
