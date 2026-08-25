from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineAnalysisNotFoundError,
    AgentEngineAuthenticationError,
    AgentEngineContractError,
    AgentEngineError,
    AgentEngineRequestError,
    AgentEngineValidationError,
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.agent_engine import (
    AgentEngineClient,
)
from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWork,
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.application_event import (
    ApplicationEvent,
    ApplicationEventType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
    InvalidApplicationStatusTransition,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
    ApplicationPreparationStatus,
)
from careerops_automation_mcp_hub.domain.job_application import JobApplication


@dataclass(frozen=True, slots=True)
class PrepareApplicationCommand:
    user_id: str
    application_id: UUID
    job_description: str
    actor_id: str
    at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PrepareApplicationResult:
    application: JobApplication
    preparation: ApplicationPreparation
    analysis: AgentEngineJobAnalysis | None
    started_new_analysis: bool


class PrepareApplicationService:
    """Durably orchestrate one application analysis in the Agent Engine."""

    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
        agent_engine_client: AgentEngineClient,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._agent_engine_client = agent_engine_client

    async def execute(
        self,
        command: PrepareApplicationCommand,
    ) -> PrepareApplicationResult:
        user_id = command.user_id.strip()
        actor_id = command.actor_id.strip()
        job_description = command.job_description.strip()

        if not user_id:
            raise ValueError("user_id must not be blank.")

        if not actor_id:
            raise ValueError("actor_id must not be blank.")

        if not job_description:
            raise ValueError("job_description must not be blank.")

        started_at = command.at or datetime.now(UTC)

        initial = await self._start_or_reuse_preparation(
            user_id=user_id,
            application_id=command.application_id,
            actor_id=actor_id,
            started_at=started_at,
        )

        if initial.preparation.status is not ApplicationPreparationStatus.STARTING:
            return initial

        try:
            analysis = await self._agent_engine_client.analyse_job(
                user_id=user_id,
                job_id=initial.preparation.agent_engine_job_id,
                job_description=job_description,
            )
        except (
            AgentEngineAuthenticationError,
            AgentEngineValidationError,
            AgentEngineAnalysisNotFoundError,
            AgentEngineRequestError,
        ) as exc:
            await self._record_known_failure(
                user_id=user_id,
                application_id=command.application_id,
                error_message=_error_message(exc),
            )
            raise
        except AgentEngineError as exc:
            await self._record_unknown_outcome(
                user_id=user_id,
                application_id=command.application_id,
                error_message=_error_message(exc),
            )
            raise

        contract_error = _validate_analysis_correlation(
            analysis,
            expected_job_id=initial.preparation.agent_engine_job_id,
        )

        if contract_error is not None:
            await self._record_unknown_outcome(
                user_id=user_id,
                application_id=command.application_id,
                error_message=str(contract_error),
            )
            raise contract_error

        return await self._record_success(
            user_id=user_id,
            application_id=command.application_id,
            actor_id=actor_id,
            analysis=analysis,
        )

    async def _start_or_reuse_preparation(
        self,
        *,
        user_id: str,
        application_id: UUID,
        actor_id: str,
        started_at: datetime,
    ) -> PrepareApplicationResult:
        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=user_id,
                application_id=application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(application_id)

            preparation = await unit_of_work.preparations.get_for_application(
                user_id=user_id,
                application_id=application_id,
            )

            if (
                preparation is not None
                and preparation.status is not ApplicationPreparationStatus.PENDING
            ):
                return PrepareApplicationResult(
                    application=application,
                    preparation=preparation,
                    analysis=None,
                    started_new_analysis=False,
                )

            if application.status is ApplicationStatus.SAVED:
                event = _transition_application(
                    application,
                    target_status=ApplicationStatus.PREPARING,
                    actor_id=actor_id,
                    at=started_at,
                )
                await unit_of_work.applications.save(application)
                await unit_of_work.events.add(event)
            elif application.status is not ApplicationStatus.PREPARING:
                raise InvalidApplicationStatusTransition(
                    "Application preparation can only start while the "
                    "application is 'saved' or 'preparing'."
                )

            if preparation is None:
                preparation = ApplicationPreparation.create(
                    application_id=application.application_id,
                    user_id=application.user_id,
                    now=started_at,
                )
                preparation.mark_starting(at=started_at)
                await unit_of_work.preparations.add(preparation)
            else:
                preparation.mark_starting(at=started_at)
                await unit_of_work.preparations.save(preparation)

            await unit_of_work.commit()

        return PrepareApplicationResult(
            application=application,
            preparation=preparation,
            analysis=None,
            started_new_analysis=True,
        )

    async def _record_known_failure(
        self,
        *,
        user_id: str,
        application_id: UUID,
        error_message: str,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            preparation = await _require_starting_preparation(
                unit_of_work,
                user_id=user_id,
                application_id=application_id,
            )

            preparation.mark_failed(
                error_message=error_message,
            )

            await unit_of_work.preparations.save(preparation)
            await unit_of_work.commit()

    async def _record_unknown_outcome(
        self,
        *,
        user_id: str,
        application_id: UUID,
        error_message: str,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            preparation = await _require_starting_preparation(
                unit_of_work,
                user_id=user_id,
                application_id=application_id,
            )

            preparation.mark_outcome_unknown(
                error_message=error_message,
            )

            await unit_of_work.preparations.save(preparation)
            await unit_of_work.commit()

    async def _record_success(
        self,
        *,
        user_id: str,
        application_id: UUID,
        actor_id: str,
        analysis: AgentEngineJobAnalysis,
    ) -> PrepareApplicationResult:
        completed_at = datetime.now(UTC)

        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=user_id,
                application_id=application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(application_id)

            preparation = await _require_starting_preparation(
                unit_of_work,
                user_id=user_id,
                application_id=application_id,
            )

            if analysis.status is AgentEngineAnalysisStatus.AWAITING_REVIEW:
                preparation.mark_awaiting_review(
                    thread_id=analysis.thread_id,
                    at=completed_at,
                )
            else:
                preparation.mark_completed(
                    thread_id=analysis.thread_id,
                    at=completed_at,
                )

                if application.status is ApplicationStatus.PREPARING:
                    event = _transition_application(
                        application,
                        target_status=ApplicationStatus.READY_TO_APPLY,
                        actor_id=actor_id,
                        at=completed_at,
                    )
                    await unit_of_work.applications.save(application)
                    await unit_of_work.events.add(event)

            await unit_of_work.preparations.save(preparation)
            await unit_of_work.commit()

        return PrepareApplicationResult(
            application=application,
            preparation=preparation,
            analysis=analysis,
            started_new_analysis=True,
        )


def _transition_application(
    application: JobApplication,
    *,
    target_status: ApplicationStatus,
    actor_id: str,
    at: datetime,
) -> ApplicationEvent:
    previous_status = application.status

    application.transition_to(
        target_status,
        at=at,
    )

    return ApplicationEvent.create(
        application_id=application.application_id,
        user_id=application.user_id,
        event_type=ApplicationEventType.STATUS_CHANGED,
        actor_id=actor_id,
        occurred_at=at,
        attributes={
            "previous_status": previous_status.value,
            "new_status": target_status.value,
        },
    )


async def _require_starting_preparation(
    unit_of_work: ApplicationUnitOfWork,
    *,
    user_id: str,
    application_id: UUID,
) -> ApplicationPreparation:
    preparation = await unit_of_work.preparations.get_for_application(
        user_id=user_id,
        application_id=application_id,
    )

    if preparation is None:
        raise RuntimeError("Application preparation disappeared during orchestration.")

    if preparation.status is not ApplicationPreparationStatus.STARTING:
        raise RuntimeError(
            "Application preparation is no longer in the starting state."
        )

    return preparation


def _validate_analysis_correlation(
    analysis: AgentEngineJobAnalysis,
    *,
    expected_job_id: str,
) -> AgentEngineContractError | None:
    if analysis.job_id != expected_job_id:
        return AgentEngineContractError(
            "Agent Engine returned an analysis for an unexpected job_id."
        )

    if not analysis.thread_id.strip():
        return AgentEngineContractError(
            "Agent Engine returned a blank analysis thread_id."
        )

    return None


def _error_message(
    error: AgentEngineError,
) -> str:
    message = str(error).strip()

    return message or type(error).__name__
