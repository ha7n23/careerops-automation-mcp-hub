from typing import Annotated, Literal
from urllib.parse import quote

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
)

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineCVProposal,
    AgentEngineEvidenceMatch,
    AgentEngineJobAnalysis,
    AgentEngineProposalEdit,
    AgentEngineRequirement,
    AgentEngineReviewAction,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineAnalysisNotFoundError,
    AgentEngineAuthenticationError,
    AgentEngineContractError,
    AgentEngineRequestError,
    AgentEngineUnavailableError,
    AgentEngineValidationError,
)


class _PayloadModel(BaseModel):
    """Base model for the subset of Module 1 API data Module 2 consumes."""

    model_config = ConfigDict(extra="ignore")


class _RequirementPayload(_PayloadModel):
    requirement_id: str
    name: str
    category: str
    importance_score: int


class _EvidenceMatchPayload(_PayloadModel):
    requirement_id: str
    match_strength: str
    explanation: str
    gap: bool


class _CVProposalPayload(_PayloadModel):
    proposal_id: str
    section: str
    current_text: str | None
    proposed_text: str
    confidence_score: float
    warnings: list[str]


class _ReviewPayload(_PayloadModel):
    allowed_actions: list[AgentEngineReviewAction]


class _JobAnalysisBasePayload(_PayloadModel):
    thread_id: str
    job_id: str
    role_title: str | None

    requirements: list[_RequirementPayload]
    evidence_matches: list[_EvidenceMatchPayload]

    fit_score: float

    cv_proposals: list[_CVProposalPayload]

    reviewable_proposal_ids: list[str]
    blocked_proposal_ids: list[str]


class _AwaitingReviewPayload(_JobAnalysisBasePayload):
    status: Literal["awaiting_review"]
    review: _ReviewPayload


class _CompletedPayload(_JobAnalysisBasePayload):
    status: Literal["completed"]
    review_status: str | None = None


_RESPONSE_ADAPTER: TypeAdapter[_AwaitingReviewPayload | _CompletedPayload] = (
    TypeAdapter(
        Annotated[
            _AwaitingReviewPayload | _CompletedPayload,
            Field(discriminator="status"),
        ]
    )
)


class HttpAgentEngineClient:
    """HTTP adapter for the CareerOps Agent Engine API."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        service_key: str,
    ) -> None:
        if not service_key.strip():
            raise ValueError("service_key must not be blank.")

        self._client = client
        self._service_key = service_key

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        """Start an evidence-grounded Module 1 job analysis."""
        return await self._post_job_analysis(
            path="/api/v1/job-analysis",
            user_id=user_id,
            json_payload={
                "job_id": job_id,
                "job_description": job_description,
            },
        )

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        """Submit a human review decision to Module 1."""
        encoded_thread_id = quote(
            thread_id,
            safe="",
        )

        return await self._post_job_analysis(
            path=(f"/api/v1/job-analysis/{encoded_thread_id}/review"),
            user_id=user_id,
            json_payload=_build_review_payload(decision),
        )

    async def _post_job_analysis(
        self,
        *,
        path: str,
        user_id: str,
        json_payload: dict[str, object],
    ) -> AgentEngineJobAnalysis:
        try:
            response = await self._client.post(
                path,
                headers={
                    "X-CareerOps-Service-Key": self._service_key,
                    "X-User-ID": user_id,
                },
                json=json_payload,
            )
        except httpx.TimeoutException as exc:
            raise AgentEngineUnavailableError(
                "Agent Engine request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise AgentEngineUnavailableError("Agent Engine is unavailable.") from exc

        if not response.is_success:
            _raise_for_agent_engine_error(response)

        try:
            raw_payload = response.json()
        except ValueError as exc:
            raise AgentEngineContractError(
                "Agent Engine returned invalid JSON."
            ) from exc

        try:
            payload = _RESPONSE_ADAPTER.validate_python(raw_payload)
        except ValidationError as exc:
            raise AgentEngineContractError(
                "Agent Engine response did not match the expected contract."
            ) from exc

        return _map_job_analysis(payload)


def _build_review_payload(
    decision: AgentEngineReviewDecision,
) -> dict[str, object]:
    edits: list[dict[str, str]] = [_build_edit_payload(edit) for edit in decision.edits]

    return {
        "action": decision.action.value,
        "approved_proposal_ids": list(decision.approved_proposal_ids),
        "rejected_proposal_ids": list(decision.rejected_proposal_ids),
        "edits": edits,
        "reviewer_comment": decision.reviewer_comment,
    }


def _build_edit_payload(
    edit: AgentEngineProposalEdit,
) -> dict[str, str]:
    return {
        "proposal_id": edit.proposal_id,
        "edited_text": edit.edited_text,
    }


def _map_job_analysis(
    payload: _AwaitingReviewPayload | _CompletedPayload,
) -> AgentEngineJobAnalysis:
    if isinstance(payload, _AwaitingReviewPayload):
        allowed_review_actions = tuple(payload.review.allowed_actions)
        review_status = None
    else:
        allowed_review_actions = ()
        review_status = payload.review_status

    return AgentEngineJobAnalysis(
        status=AgentEngineAnalysisStatus(payload.status),
        thread_id=payload.thread_id,
        job_id=payload.job_id,
        role_title=payload.role_title,
        fit_score=payload.fit_score,
        requirements=tuple(
            AgentEngineRequirement(
                requirement_id=requirement.requirement_id,
                name=requirement.name,
                category=requirement.category,
                importance_score=requirement.importance_score,
            )
            for requirement in payload.requirements
        ),
        evidence_matches=tuple(
            AgentEngineEvidenceMatch(
                requirement_id=match.requirement_id,
                match_strength=match.match_strength,
                explanation=match.explanation,
                gap=match.gap,
            )
            for match in payload.evidence_matches
        ),
        cv_proposals=tuple(
            AgentEngineCVProposal(
                proposal_id=proposal.proposal_id,
                section=proposal.section,
                current_text=proposal.current_text,
                proposed_text=proposal.proposed_text,
                confidence_score=proposal.confidence_score,
                warnings=tuple(proposal.warnings),
            )
            for proposal in payload.cv_proposals
        ),
        reviewable_proposal_ids=tuple(payload.reviewable_proposal_ids),
        blocked_proposal_ids=tuple(payload.blocked_proposal_ids),
        allowed_review_actions=allowed_review_actions,
        review_status=review_status,
    )


def _raise_for_agent_engine_error(
    response: httpx.Response,
) -> None:
    status_code = response.status_code

    if status_code in {401, 403}:
        raise AgentEngineAuthenticationError(
            "Agent Engine rejected service authentication."
        )

    if status_code == 404:
        raise AgentEngineAnalysisNotFoundError("Agent Engine analysis was not found.")

    if status_code == 422:
        raise AgentEngineValidationError(
            _extract_error_detail(response) or "Agent Engine rejected the request."
        )

    if status_code >= 500:
        raise AgentEngineUnavailableError(f"Agent Engine returned HTTP {status_code}.")

    raise AgentEngineRequestError(status_code)


def _extract_error_detail(
    response: httpx.Response,
) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    detail = payload.get("detail")

    return detail if isinstance(detail, str) else None
