from dataclasses import dataclass
from datetime import datetime

from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyOperation,
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
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class CreateApplicationCommand:
    user_id: str
    company_name: str
    role_title: str
    actor_id: str
    idempotency_key: str
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class CreateApplicationResult:
    application: JobApplication
    event: ApplicationEvent


class CreateApplicationService:
    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        command: CreateApplicationCommand,
    ) -> CreateApplicationResult:
        idempotency_key = normalize_idempotency_key(command.idempotency_key)

        application = JobApplication.create(
            user_id=command.user_id,
            company_name=command.company_name,
            role_title=command.role_title,
            now=command.now,
        )

        event = ApplicationEvent.create(
            application_id=application.application_id,
            user_id=application.user_id,
            event_type=ApplicationEventType.APPLICATION_CREATED,
            actor_id=command.actor_id,
            occurred_at=command.now,
        )

        request_fingerprint = build_request_fingerprint(
            {
                "company_name": application.company_name,
                "role_title": application.role_title,
                "actor_id": event.actor_id,
            }
        )

        operation = IdempotencyOperation.CREATE_APPLICATION

        async with self._unit_of_work_factory() as unit_of_work:
            claim = await unit_of_work.idempotency.claim(
                user_id=application.user_id,
                operation=operation,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
                created_at=application.created_at,
            )

            replay_payload = resolve_idempotency_claim(
                claim,
                request_fingerprint=request_fingerprint,
            )

            if replay_payload is not None:
                replay_application, replay_event = restore_application_mutation_payload(
                    replay_payload
                )

                return CreateApplicationResult(
                    application=replay_application,
                    event=replay_event,
                )

            await unit_of_work.applications.add(application)
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

        return CreateApplicationResult(
            application=application,
            event=event,
        )
