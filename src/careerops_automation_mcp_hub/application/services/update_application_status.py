from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.errors import (
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyOperation,
    IdempotencyReplayUnavailableError,
    build_application_mutation_payload,
    build_request_fingerprint,
    normalize_idempotency_key,
    resolve_idempotency_claim,
    restore_application_mutation_payload,
)
from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class UpdateApplicationStatusCommand:
    user_id: str
    application_id: UUID
    target_status: ApplicationStatus
    actor_id: str
    idempotency_key: str
    at: datetime | None = None


@dataclass(frozen=True, slots=True)
class UpdateApplicationStatusResult:
    application: JobApplication
    event: ApplicationEvent


class UpdateApplicationStatusService:
    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        command: UpdateApplicationStatusCommand,
    ) -> UpdateApplicationStatusResult:
        idempotency_key = normalize_idempotency_key(command.idempotency_key)

        actor_id = command.actor_id.strip()

        if not actor_id:
            raise ValueError("actor_id must not be blank.")

        operation_at = command.at or datetime.now(UTC)

        request_fingerprint = build_request_fingerprint(
            {
                "application_id": str(command.application_id),
                "target_status": command.target_status.value,
                "actor_id": actor_id,
            }
        )

        operation = IdempotencyOperation.UPDATE_APPLICATION_STATUS

        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=command.user_id,
                application_id=command.application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(command.application_id)

            claim = await unit_of_work.idempotency.claim(
                user_id=command.user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                created_at=operation_at,
            )

            replay_payload = resolve_idempotency_claim(
                claim,
                request_fingerprint=request_fingerprint,
            )

            if replay_payload is not None:
                replay_application, replay_event = restore_application_mutation_payload(
                    replay_payload
                )

                if (
                    replay_application.application_id != command.application_id
                    or replay_application.user_id != command.user_id
                ):
                    raise IdempotencyReplayUnavailableError(
                        "Stored idempotency result does not match "
                        "the requested application."
                    )

                return UpdateApplicationStatusResult(
                    application=replay_application,
                    event=replay_event,
                )

            previous_status = application.status

            application.transition_to(
                command.target_status,
                at=operation_at,
            )

            event = ApplicationEvent.create(
                application_id=application.application_id,
                user_id=application.user_id,
                event_type=ApplicationEventType.STATUS_CHANGED,
                actor_id=actor_id,
                occurred_at=operation_at,
                attributes={
                    "previous_status": previous_status.value,
                    "new_status": application.status.value,
                },
            )

            await unit_of_work.applications.save(application)
            await unit_of_work.events.add(event)

            response_payload = build_application_mutation_payload(
                application=application,
                event=event,
            )

            await unit_of_work.idempotency.complete(
                user_id=application.user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                response_payload=response_payload,
                completed_at=event.occurred_at,
            )

            await unit_of_work.commit()

        return UpdateApplicationStatusResult(
            application=application,
            event=event,
        )
