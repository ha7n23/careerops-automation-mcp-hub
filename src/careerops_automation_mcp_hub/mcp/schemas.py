from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineAnalysisStatus,
    AgentEngineCVProposal,
    AgentEngineEvidenceMatch,
    AgentEngineJobAnalysis,
    AgentEngineRequirement,
    AgentEngineReviewAction,
)
from careerops_automation_mcp_hub.application.services.prepare_application import (
    PrepareApplicationResult,
)
from careerops_automation_mcp_hub.application.services.review_application import (
    ReviewApplicationResult,
)
from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemStatus,
    ActionItemType,
)
from careerops_automation_mcp_hub.domain.application_lifecycle import (
    ApplicationStatus,
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
from careerops_automation_mcp_hub.domain.job_application import JobApplication


class ApplicationSummary(BaseModel):
    application_id: UUID
    company_name: str
    role_title: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        application: JobApplication,
    ) -> "ApplicationSummary":
        return cls(
            application_id=application.application_id,
            company_name=application.company_name,
            role_title=application.role_title,
            status=application.status,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class ApplicationListResult(BaseModel):
    applications: list[ApplicationSummary]
    count: int


class ActionItemSummary(BaseModel):
    action_id: UUID
    application_id: UUID
    action_type: ActionItemType
    description: str
    status: ActionItemStatus
    due_at: datetime | None

    @classmethod
    def from_domain(cls, action: ActionItem) -> "ActionItemSummary":
        return cls(
            action_id=action.action_id,
            application_id=action.application_id,
            action_type=action.action_type,
            description=action.description,
            status=action.status,
            due_at=action.due_at,
        )


class PendingActionsResult(BaseModel):
    actions: list[ActionItemSummary]
    count: int


class ApplicationPreparationSummary(BaseModel):
    preparation_id: UUID
    application_id: UUID
    status: ApplicationPreparationStatus
    agent_engine_job_id: str
    agent_engine_thread_id: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        preparation: ApplicationPreparation,
    ) -> "ApplicationPreparationSummary":
        return cls(
            preparation_id=preparation.preparation_id,
            application_id=preparation.application_id,
            status=preparation.status,
            agent_engine_job_id=preparation.agent_engine_job_id,
            agent_engine_thread_id=preparation.agent_engine_thread_id,
            error_message=preparation.error_message,
            created_at=preparation.created_at,
            updated_at=preparation.updated_at,
        )


class AgentEngineRequirementSummary(BaseModel):
    requirement_id: str
    name: str
    category: str
    importance_score: int

    @classmethod
    def from_domain(
        cls,
        requirement: AgentEngineRequirement,
    ) -> "AgentEngineRequirementSummary":
        return cls(
            requirement_id=requirement.requirement_id,
            name=requirement.name,
            category=requirement.category,
            importance_score=requirement.importance_score,
        )


class AgentEngineEvidenceMatchSummary(BaseModel):
    requirement_id: str
    match_strength: str
    explanation: str
    gap: bool

    @classmethod
    def from_domain(
        cls,
        match: AgentEngineEvidenceMatch,
    ) -> "AgentEngineEvidenceMatchSummary":
        return cls(
            requirement_id=match.requirement_id,
            match_strength=match.match_strength,
            explanation=match.explanation,
            gap=match.gap,
        )


class AgentEngineCVProposalSummary(BaseModel):
    proposal_id: str
    section: str
    current_text: str | None
    proposed_text: str
    confidence_score: float
    warnings: list[str]

    @classmethod
    def from_domain(
        cls,
        proposal: AgentEngineCVProposal,
    ) -> "AgentEngineCVProposalSummary":
        return cls(
            proposal_id=proposal.proposal_id,
            section=proposal.section,
            current_text=proposal.current_text,
            proposed_text=proposal.proposed_text,
            confidence_score=proposal.confidence_score,
            warnings=list(proposal.warnings),
        )


class AgentEngineAnalysisSummary(BaseModel):
    status: AgentEngineAnalysisStatus
    thread_id: str
    job_id: str
    role_title: str | None
    fit_score: float
    requirements: list[AgentEngineRequirementSummary]
    evidence_matches: list[AgentEngineEvidenceMatchSummary]
    cv_proposals: list[AgentEngineCVProposalSummary]
    reviewable_proposal_ids: list[str]
    blocked_proposal_ids: list[str]
    allowed_review_actions: list[AgentEngineReviewAction]
    review_status: str | None

    @classmethod
    def from_domain(
        cls,
        analysis: AgentEngineJobAnalysis,
    ) -> "AgentEngineAnalysisSummary":
        return cls(
            status=analysis.status,
            thread_id=analysis.thread_id,
            job_id=analysis.job_id,
            role_title=analysis.role_title,
            fit_score=analysis.fit_score,
            requirements=[
                AgentEngineRequirementSummary.from_domain(requirement)
                for requirement in analysis.requirements
            ],
            evidence_matches=[
                AgentEngineEvidenceMatchSummary.from_domain(match)
                for match in analysis.evidence_matches
            ],
            cv_proposals=[
                AgentEngineCVProposalSummary.from_domain(proposal)
                for proposal in analysis.cv_proposals
            ],
            reviewable_proposal_ids=list(analysis.reviewable_proposal_ids),
            blocked_proposal_ids=list(analysis.blocked_proposal_ids),
            allowed_review_actions=list(analysis.allowed_review_actions),
            review_status=analysis.review_status,
        )


class PrepareApplicationToolResult(BaseModel):
    application: ApplicationSummary
    preparation: ApplicationPreparationSummary
    analysis: AgentEngineAnalysisSummary | None
    started_new_analysis: bool

    @classmethod
    def from_application_result(
        cls,
        result: PrepareApplicationResult,
    ) -> "PrepareApplicationToolResult":
        analysis = (
            AgentEngineAnalysisSummary.from_domain(result.analysis)
            if result.analysis is not None
            else None
        )

        return cls(
            application=ApplicationSummary.from_domain(result.application),
            preparation=ApplicationPreparationSummary.from_domain(result.preparation),
            analysis=analysis,
            started_new_analysis=result.started_new_analysis,
        )


class ApplicationReviewEditInput(BaseModel):
    proposal_id: str
    edited_text: str


class ApplicationReviewEditSummary(BaseModel):
    proposal_id: str
    edited_text: str

    @classmethod
    def from_domain(
        cls,
        edit: ApplicationReviewEdit,
    ) -> "ApplicationReviewEditSummary":
        return cls(
            proposal_id=edit.proposal_id,
            edited_text=edit.edited_text,
        )


class ApplicationReviewSubmissionSummary(BaseModel):
    review_submission_id: UUID
    preparation_id: UUID
    application_id: UUID
    thread_id: str
    idempotency_key: str

    action: ApplicationReviewAction
    approved_proposal_ids: list[str]
    rejected_proposal_ids: list[str]
    edits: list[ApplicationReviewEditSummary]
    reviewer_comment: str | None

    status: ApplicationReviewSubmissionStatus
    outcome: ApplicationReviewOutcome | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        submission: ApplicationReviewSubmission,
    ) -> "ApplicationReviewSubmissionSummary":
        return cls(
            review_submission_id=submission.review_submission_id,
            preparation_id=submission.preparation_id,
            application_id=submission.application_id,
            thread_id=submission.thread_id,
            idempotency_key=submission.idempotency_key,
            action=submission.action,
            approved_proposal_ids=list(submission.approved_proposal_ids),
            rejected_proposal_ids=list(submission.rejected_proposal_ids),
            edits=[
                ApplicationReviewEditSummary.from_domain(edit)
                for edit in submission.edits
            ],
            reviewer_comment=submission.reviewer_comment,
            status=submission.status,
            outcome=submission.outcome,
            error_message=submission.error_message,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )


class ReviewApplicationToolResult(BaseModel):
    application: ApplicationSummary
    preparation: ApplicationPreparationSummary
    submission: ApplicationReviewSubmissionSummary
    analysis: AgentEngineAnalysisSummary | None
    started_new_review: bool

    @classmethod
    def from_application_result(
        cls,
        result: ReviewApplicationResult,
    ) -> "ReviewApplicationToolResult":
        analysis = (
            AgentEngineAnalysisSummary.from_domain(result.analysis)
            if result.analysis is not None
            else None
        )

        return cls(
            application=ApplicationSummary.from_domain(result.application),
            preparation=ApplicationPreparationSummary.from_domain(result.preparation),
            submission=ApplicationReviewSubmissionSummary.from_domain(
                result.submission
            ),
            analysis=analysis,
            started_new_review=result.started_new_review,
        )
