from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineJobAnalysis,
    AgentEngineProposalEdit,
    AgentEngineReviewAction,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineAnalysisNotFoundError,
    AgentEngineAuthenticationError,
    AgentEngineContractError,
    AgentEngineError,
    AgentEngineRequestError,
    AgentEngineValidationError,
    ApplicationNotFoundError,
    ApplicationReviewBlockedError,
)
from careerops_automation_mcp_hub.application.idempotency import (
    IdempotencyConflictError,
    normalize_idempotency_key,
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
from careerops_automation_mcp_hub.domain.application_review import (
    ApplicationReviewAction,
    ApplicationReviewEdit,
    ApplicationReviewOutcome,
    ApplicationReviewSubmission,
    ApplicationReviewSubmissionStatus,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)


@dataclass(frozen=True, slots=True)
class ReviewApplicationCommand:
    user_id: str
    application_id: UUID
    actor_id: str
    idempotency_key: str

    action: ApplicationReviewAction
    approved_proposal_ids: tuple[str, ...] = ()
    rejected_proposal_ids: tuple[str, ...] = ()
    edits: tuple[ApplicationReviewEdit, ...] = ()
    reviewer_comment: str | None = None

    at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReviewApplicationResult:
    application: JobApplication
    preparation: ApplicationPreparation
    submission: ApplicationReviewSubmission
    analysis: AgentEngineJobAnalysis | None
    started_new_review: bool


class ReviewApplicationService:
    """Durably orchestrate one human decision against Agent Engine review."""

    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
        agent_engine_client: AgentEngineClient,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._agent_engine_client = agent_engine_client

    async def execute(
        self,
        command: ReviewApplicationCommand,
    ) -> ReviewApplicationResult:
        user_id = command.user_id.strip()
        actor_id = command.actor_id.strip()
        idempotency_key = normalize_idempotency_key(command.idempotency_key)

        if not user_id:
            raise ValueError("user_id must not be blank.")

        if not actor_id:
            raise ValueError("actor_id must not be blank.")

        started_at = command.at or datetime.now(UTC)

        initial = await self._start_or_replay_review(
            command=command,
            user_id=user_id,
            idempotency_key=idempotency_key,
            started_at=started_at,
        )

        if not initial.started_new_review:
            return initial

        decision = _to_agent_engine_decision(initial.submission)

        try:
            analysis = await self._agent_engine_client.review_job_analysis(
                user_id=user_id,
                thread_id=initial.submission.thread_id,
                decision=decision,
            )
        except (
            AgentEngineAuthenticationError,
            AgentEngineValidationError,
            AgentEngineAnalysisNotFoundError,
            AgentEngineRequestError,
        ) as exc:
            await self._record_known_failure(
                user_id=user_id,
                idempotency_key=idempotency_key,
                error_message=_error_message(exc),
            )
            raise
        except AgentEngineError as exc:
            await self._record_unknown_outcome(
                user_id=user_id,
                idempotency_key=idempotency_key,
                error_message=_error_message(exc),
            )
            raise

        contract_error = _validate_analysis_correlation(
            analysis,
            submission=initial.submission,
        )

        if contract_error is not None:
            await self._record_unknown_outcome(
                user_id=user_id,
                idempotency_key=idempotency_key,
                error_message=str(contract_error),
            )
            raise contract_error

        return await self._record_success(
            user_id=user_id,
            application_id=command.application_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            analysis=analysis,
        )

    async def _start_or_replay_review(
        self,
        *,
        command: ReviewApplicationCommand,
        user_id: str,
        idempotency_key: str,
        started_at: datetime,
    ) -> ReviewApplicationResult:
        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=user_id,
                application_id=command.application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(command.application_id)

            existing = await unit_of_work.review_submissions.get_by_idempotency_key(
                user_id=user_id,
                idempotency_key=idempotency_key,
            )

            if existing is not None:
                return await _build_replay_result(
                    unit_of_work,
                    application=application,
                    existing=existing,
                    command=command,
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                )

            preparation = (
                await unit_of_work.preparations.get_for_application_for_update(
                    user_id=user_id,
                    application_id=command.application_id,
                )
            )

            if preparation is None:
                raise ApplicationReviewBlockedError(
                    "Application has no preparation available for review."
                )

            # Re-check after acquiring the row lock. Another transaction may
            # have created this key while this request was waiting.
            existing = await unit_of_work.review_submissions.get_by_idempotency_key(
                user_id=user_id,
                idempotency_key=idempotency_key,
            )

            if existing is not None:
                return await _build_replay_result(
                    unit_of_work,
                    application=application,
                    existing=existing,
                    command=command,
                    user_id=user_id,
                    idempotency_key=idempotency_key,
                    preparation=preparation,
                )

            if preparation.status is not ApplicationPreparationStatus.AWAITING_REVIEW:
                raise ApplicationReviewBlockedError(
                    "Application preparation is not awaiting human review."
                )

            if preparation.agent_engine_thread_id is None:
                raise ApplicationReviewBlockedError(
                    "Application preparation has no Agent Engine review thread."
                )

            if application.status is not ApplicationStatus.PREPARING:
                raise InvalidApplicationStatusTransition(
                    "Application review can only run while the application "
                    "is 'preparing'."
                )

            unresolved = (
                await unit_of_work.review_submissions.get_unresolved_for_preparation(
                    user_id=user_id,
                    preparation_id=preparation.preparation_id,
                )
            )

            if unresolved is not None:
                raise ApplicationReviewBlockedError(
                    "Application review is blocked by an unresolved review submission."
                )

            submission = _build_submission(
                command=command,
                user_id=user_id,
                idempotency_key=idempotency_key,
                preparation=preparation,
                started_at=started_at,
            )

            submission.mark_submitting(
                at=started_at,
            )

            await unit_of_work.review_submissions.add(submission)

            # Critical distributed-systems boundary:
            # SUBMITTING must be durable before Module 1 is called.
            await unit_of_work.commit()

        return ReviewApplicationResult(
            application=application,
            preparation=preparation,
            submission=submission,
            analysis=None,
            started_new_review=True,
        )

    async def _record_known_failure(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        error_message: str,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            submission = await _require_submitting_submission(
                unit_of_work,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )

            submission.mark_failed(
                error_message=error_message,
            )

            await unit_of_work.review_submissions.save(submission)
            await unit_of_work.commit()

    async def _record_unknown_outcome(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        error_message: str,
    ) -> None:
        async with self._unit_of_work_factory() as unit_of_work:
            submission = await _require_submitting_submission(
                unit_of_work,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )

            submission.mark_outcome_unknown(
                error_message=error_message,
            )

            await unit_of_work.review_submissions.save(submission)
            await unit_of_work.commit()

    async def _record_success(
        self,
        *,
        user_id: str,
        application_id: UUID,
        actor_id: str,
        idempotency_key: str,
        analysis: AgentEngineJobAnalysis,
    ) -> ReviewApplicationResult:
        completed_at = datetime.now(UTC)

        async with self._unit_of_work_factory() as unit_of_work:
            preparation = (
                await unit_of_work.preparations.get_for_application_for_update(
                    user_id=user_id,
                    application_id=application_id,
                )
            )

            if preparation is None:
                raise RuntimeError(
                    "Application preparation disappeared during review orchestration."
                )

            application = await unit_of_work.applications.get(
                user_id=user_id,
                application_id=application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(application_id)

            submission = await _require_submitting_submission(
                unit_of_work,
                user_id=user_id,
                idempotency_key=idempotency_key,
            )

            outcome = ApplicationReviewOutcome(analysis.status.value)

            submission.mark_completed(
                outcome=outcome,
                at=completed_at,
            )

            if analysis.status is AgentEngineAnalysisStatus.COMPLETED:
                preparation.mark_completed_after_review(
                    at=completed_at,
                )

                await unit_of_work.preparations.save(preparation)

                if application.status is ApplicationStatus.PREPARING:
                    event = _transition_application(
                        application,
                        target_status=ApplicationStatus.READY_TO_APPLY,
                        actor_id=actor_id,
                        at=completed_at,
                    )

                    await unit_of_work.applications.save(application)
                    await unit_of_work.events.add(event)

            await unit_of_work.review_submissions.save(submission)
            await unit_of_work.commit()

        return ReviewApplicationResult(
            application=application,
            preparation=preparation,
            submission=submission,
            analysis=analysis,
            started_new_review=True,
        )


async def _build_replay_result(
    unit_of_work: ApplicationUnitOfWork,
    *,
    application: JobApplication,
    existing: ApplicationReviewSubmission,
    command: ReviewApplicationCommand,
    user_id: str,
    idempotency_key: str,
    preparation: ApplicationPreparation | None = None,
) -> ReviewApplicationResult:
    candidate = ApplicationReviewSubmission.create(
        preparation_id=existing.preparation_id,
        application_id=command.application_id,
        user_id=user_id,
        thread_id=existing.thread_id,
        idempotency_key=idempotency_key,
        action=command.action,
        approved_proposal_ids=command.approved_proposal_ids,
        rejected_proposal_ids=command.rejected_proposal_ids,
        edits=command.edits,
        reviewer_comment=command.reviewer_comment,
    )

    if not _same_review_request(
        existing,
        candidate,
    ):
        raise IdempotencyConflictError(
            "Idempotency key was already used for a different review decision."
        )

    if preparation is None:
        preparation = await unit_of_work.preparations.get_for_application(
            user_id=user_id,
            application_id=command.application_id,
        )

    if preparation is None:
        raise RuntimeError("Stored review submission has no application preparation.")

    return ReviewApplicationResult(
        application=application,
        preparation=preparation,
        submission=existing,
        analysis=None,
        started_new_review=False,
    )


def _build_submission(
    *,
    command: ReviewApplicationCommand,
    user_id: str,
    idempotency_key: str,
    preparation: ApplicationPreparation,
    started_at: datetime,
) -> ApplicationReviewSubmission:
    thread_id = preparation.agent_engine_thread_id

    if thread_id is None:
        raise ApplicationReviewBlockedError(
            "Application preparation has no Agent Engine review thread."
        )

    return ApplicationReviewSubmission.create(
        preparation_id=preparation.preparation_id,
        application_id=command.application_id,
        user_id=user_id,
        thread_id=thread_id,
        idempotency_key=idempotency_key,
        action=command.action,
        approved_proposal_ids=command.approved_proposal_ids,
        rejected_proposal_ids=command.rejected_proposal_ids,
        edits=command.edits,
        reviewer_comment=command.reviewer_comment,
        now=started_at,
    )


def _same_review_request(
    existing: ApplicationReviewSubmission,
    candidate: ApplicationReviewSubmission,
) -> bool:
    return (
        existing.application_id == candidate.application_id
        and existing.user_id == candidate.user_id
        and existing.thread_id == candidate.thread_id
        and existing.action is candidate.action
        and (existing.approved_proposal_ids == candidate.approved_proposal_ids)
        and (existing.rejected_proposal_ids == candidate.rejected_proposal_ids)
        and existing.edits == candidate.edits
        and existing.reviewer_comment == candidate.reviewer_comment
    )


def _to_agent_engine_decision(
    submission: ApplicationReviewSubmission,
) -> AgentEngineReviewDecision:
    return AgentEngineReviewDecision(
        action=AgentEngineReviewAction(submission.action.value),
        approved_proposal_ids=submission.approved_proposal_ids,
        rejected_proposal_ids=submission.rejected_proposal_ids,
        edits=tuple(
            AgentEngineProposalEdit(
                proposal_id=edit.proposal_id,
                edited_text=edit.edited_text,
            )
            for edit in submission.edits
        ),
        reviewer_comment=submission.reviewer_comment,
    )


async def _require_submitting_submission(
    unit_of_work: ApplicationUnitOfWork,
    *,
    user_id: str,
    idempotency_key: str,
) -> ApplicationReviewSubmission:
    submission = await unit_of_work.review_submissions.get_by_idempotency_key(
        user_id=user_id,
        idempotency_key=idempotency_key,
    )

    if submission is None:
        raise RuntimeError("Review submission disappeared during orchestration.")

    if submission.status is not ApplicationReviewSubmissionStatus.SUBMITTING:
        raise RuntimeError("Review submission is no longer in the submitting state.")

    return submission


def _validate_analysis_correlation(
    analysis: AgentEngineJobAnalysis,
    *,
    submission: ApplicationReviewSubmission,
) -> AgentEngineContractError | None:
    if analysis.thread_id != submission.thread_id:
        return AgentEngineContractError(
            "Agent Engine returned review output for an unexpected thread_id."
        )

    if analysis.job_id != str(submission.application_id):
        return AgentEngineContractError(
            "Agent Engine returned review output for an unexpected job_id."
        )

    return None


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


def _error_message(
    error: AgentEngineError,
) -> str:
    message = str(error).strip()

    return message or type(error).__name__
