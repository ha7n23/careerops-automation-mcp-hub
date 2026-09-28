from typing import Annotated, Any, Literal, NoReturn, TypeVar
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
    AgentEngineConflictError,
    AgentEngineContractError,
    AgentEngineNotFoundError,
    AgentEngineRequestError,
    AgentEngineUnavailableError,
    AgentEngineValidationError,
)
from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocument,
    EvidenceDocumentHistory,
    EvidenceReviewDecision,
    EvidenceReviewHistory,
    EvidenceReviewRun,
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

_ResponseT = TypeVar("_ResponseT")
_HttpMethod = Literal["GET", "POST", "PATCH"]
_DOCUMENT_ADAPTER = TypeAdapter(EvidenceDocument)
_DOCUMENT_HISTORY_ADAPTER = TypeAdapter(EvidenceDocumentHistory)
_EVIDENCE_REVIEW_ADAPTER = TypeAdapter(EvidenceReviewRun)
_EVIDENCE_REVIEW_HISTORY_ADAPTER = TypeAdapter(EvidenceReviewHistory)


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

    async def list_evidence_documents(
        self,
        *,
        user_id: str,
        limit: int,
    ) -> EvidenceDocumentHistory:
        """List one user's bounded Module 1 evidence-source history."""
        return await self._request_json(
            method="GET",
            path="/api/v1/cv-documents",
            user_id=user_id,
            response_adapter=_DOCUMENT_HISTORY_ADAPTER,
            query_params={"limit": limit},
        )

    async def upload_evidence_document(
        self,
        *,
        user_id: str,
        filename: str,
        media_type: str,
        data: bytes,
    ) -> EvidenceDocument:
        """Upload one PDF or DOCX evidence source to Module 1."""
        return await self._request_json(
            method="POST",
            path="/api/v1/cv-documents",
            user_id=user_id,
            response_adapter=_DOCUMENT_ADAPTER,
            files={"file": (filename, data, media_type)},
        )

    async def create_text_evidence_source(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
    ) -> EvidenceDocument:
        """Create one pasted-text evidence source in Module 1."""
        return await self._request_json(
            method="POST",
            path="/api/v1/cv-documents/text",
            user_id=user_id,
            response_adapter=_DOCUMENT_ADAPTER,
            json_payload={
                "title": title,
                "content": content,
            },
        )

    async def start_evidence_review(
        self,
        *,
        user_id: str,
        document_id: str,
    ) -> EvidenceReviewRun:
        """Start or recover evidence extraction and review."""
        encoded_document_id = quote(document_id, safe="")

        return await self._request_json(
            method="POST",
            path=(f"/api/v1/cv-documents/{encoded_document_id}/evidence-review"),
            user_id=user_id,
            response_adapter=_EVIDENCE_REVIEW_ADAPTER,
        )

    async def list_evidence_reviews(
        self,
        *,
        user_id: str,
        limit: int,
    ) -> EvidenceReviewHistory:
        """List one user's bounded Module 1 evidence-review history."""
        return await self._request_json(
            method="GET",
            path="/api/v1/cv-evidence-reviews",
            user_id=user_id,
            response_adapter=_EVIDENCE_REVIEW_HISTORY_ADAPTER,
            query_params={"limit": limit},
        )

    async def get_evidence_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
    ) -> EvidenceReviewRun:
        """Recover one durable Module 1 evidence-review run."""
        encoded_review_run_id = quote(review_run_id, safe="")

        return await self._request_json(
            method="GET",
            path=f"/api/v1/cv-evidence-reviews/{encoded_review_run_id}",
            user_id=user_id,
            response_adapter=_EVIDENCE_REVIEW_ADAPTER,
        )

    async def submit_evidence_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
        decision: EvidenceReviewDecision,
    ) -> EvidenceReviewRun:
        """Submit a complete human evidence decision to Module 1."""
        encoded_review_run_id = quote(review_run_id, safe="")

        return await self._request_json(
            method="POST",
            path=f"/api/v1/cv-evidence-reviews/{encoded_review_run_id}/review",
            user_id=user_id,
            response_adapter=_EVIDENCE_REVIEW_ADAPTER,
            json_payload=decision.model_dump(mode="json"),
        )

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        """Start an evidence-grounded Module 1 job analysis."""
        return await self._request_job_analysis(
            method="POST",
            path="/api/v1/job-analysis",
            user_id=user_id,
            json_payload={
                "job_id": job_id,
                "job_description": job_description,
            },
        )

    async def get_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> AgentEngineJobAnalysis:
        """Recover one durable Module 1 job analysis."""

        encoded_thread_id = quote(
            thread_id,
            safe="",
        )

        return await self._request_job_analysis(
            method="GET",
            path=f"/api/v1/job-analysis/{encoded_thread_id}",
            user_id=user_id,
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

        return await self._request_job_analysis(
            method="POST",
            path=(f"/api/v1/job-analysis/{encoded_thread_id}/review"),
            user_id=user_id,
            json_payload=_build_review_payload(decision),
        )

    async def _request_job_analysis(
        self,
        *,
        method: _HttpMethod,
        path: str,
        user_id: str,
        json_payload: dict[str, object] | None = None,
    ) -> AgentEngineJobAnalysis:
        payload = await self._request_json(
            method=method,
            path=path,
            user_id=user_id,
            response_adapter=_RESPONSE_ADAPTER,
            json_payload=json_payload,
            not_found_error=AgentEngineAnalysisNotFoundError,
        )

        return _map_job_analysis(payload)

    async def _request_json(
        self,
        *,
        method: _HttpMethod,
        path: str,
        user_id: str,
        response_adapter: TypeAdapter[_ResponseT],
        json_payload: dict[str, object] | None = None,
        query_params: dict[str, str | int] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        not_found_error: type[AgentEngineNotFoundError] = AgentEngineNotFoundError,
    ) -> _ResponseT:
        response = await self._request(
            method=method,
            path=path,
            user_id=user_id,
            json_payload=json_payload,
            query_params=query_params,
            files=files,
            not_found_error=not_found_error,
        )

        try:
            raw_payload = response.json()
        except ValueError as exc:
            raise AgentEngineContractError(
                "Agent Engine returned invalid JSON."
            ) from exc

        try:
            return response_adapter.validate_python(raw_payload)
        except ValidationError as exc:
            raise AgentEngineContractError(
                "Agent Engine response did not match the expected contract."
            ) from exc

    async def _request(
        self,
        *,
        method: _HttpMethod,
        path: str,
        user_id: str,
        json_payload: dict[str, object] | None = None,
        query_params: dict[str, str | int] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        not_found_error: type[AgentEngineNotFoundError] = AgentEngineNotFoundError,
    ) -> httpx.Response:
        headers = {
            "X-CareerOps-Service-Key": self._service_key,
            "X-User-ID": user_id,
        }

        request_options: dict[str, Any] = {
            "headers": headers,
        }

        if json_payload is not None:
            request_options["json"] = json_payload

        if query_params is not None:
            request_options["params"] = query_params

        if files is not None:
            request_options["files"] = files

        try:
            response = await self._client.request(
                method,
                path,
                **request_options,
            )
        except httpx.TimeoutException as exc:
            raise AgentEngineUnavailableError(
                "Agent Engine request timed out."
            ) from exc
        except httpx.RequestError as exc:
            raise AgentEngineUnavailableError("Agent Engine is unavailable.") from exc

        if not response.is_success:
            _raise_for_agent_engine_error(
                response,
                not_found_error=not_found_error,
            )

        return response


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
    *,
    not_found_error: type[AgentEngineNotFoundError],
) -> NoReturn:
    status_code = response.status_code

    if status_code in {401, 403}:
        raise AgentEngineAuthenticationError(
            "Agent Engine rejected service authentication."
        )

    if status_code == 404:
        raise not_found_error(
            _extract_error_detail(response)
            or "The requested Agent Engine resource is unavailable."
        )

    if status_code == 409:
        raise AgentEngineConflictError(
            _extract_error_detail(response)
            or "Agent Engine rejected the operation because its state changed."
        )

    if status_code == 422:
        raise AgentEngineValidationError(
            _extract_error_detail(response) or "Agent Engine rejected the request."
        )

    # Do not expose upstream 5xx details to callers.
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

    if isinstance(detail, str):
        return detail

    if not isinstance(detail, list):
        return None

    messages: list[str] = []

    for item in detail:
        if not isinstance(item, dict):
            continue

        message = item.get("msg")
        if isinstance(message, str):
            messages.append(message)

    return "; ".join(messages) or None
