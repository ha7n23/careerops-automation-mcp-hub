from dataclasses import dataclass
from enum import StrEnum


class AgentEngineAnalysisStatus(StrEnum):
    """Public job-analysis states understood by Module 2."""

    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"


class AgentEngineReviewAction(StrEnum):
    """Human actions supported by the Agent Engine review workflow."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    REGENERATE = "regenerate"


@dataclass(frozen=True, slots=True)
class AgentEngineRequirement:
    """One extracted job requirement relevant to application preparation."""

    requirement_id: str
    name: str
    category: str
    importance_score: int


@dataclass(frozen=True, slots=True)
class AgentEngineEvidenceMatch:
    """Summary of evidence matched to one requirement."""

    requirement_id: str
    match_strength: str
    explanation: str
    gap: bool


@dataclass(frozen=True, slots=True)
class AgentEngineCVProposal:
    """One evidence-grounded CV change proposed by the Agent Engine."""

    proposal_id: str
    section: str
    current_text: str | None
    proposed_text: str
    confidence_score: float
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AgentEngineJobAnalysis:
    """Module 2's view of one Agent Engine job-analysis result."""

    status: AgentEngineAnalysisStatus
    thread_id: str
    job_id: str
    role_title: str | None
    fit_score: float

    requirements: tuple[AgentEngineRequirement, ...]
    evidence_matches: tuple[AgentEngineEvidenceMatch, ...]
    cv_proposals: tuple[AgentEngineCVProposal, ...]

    reviewable_proposal_ids: tuple[str, ...]
    blocked_proposal_ids: tuple[str, ...]

    allowed_review_actions: tuple[AgentEngineReviewAction, ...]

    review_status: str | None = None


@dataclass(frozen=True, slots=True)
class AgentEngineProposalEdit:
    """Human-edited replacement text for one CV proposal."""

    proposal_id: str
    edited_text: str


@dataclass(frozen=True, slots=True)
class AgentEngineReviewDecision:
    """Human decision sent back to the Agent Engine."""

    action: AgentEngineReviewAction
    approved_proposal_ids: tuple[str, ...] = ()
    rejected_proposal_ids: tuple[str, ...] = ()
    edits: tuple[AgentEngineProposalEdit, ...] = ()
    reviewer_comment: str | None = None
