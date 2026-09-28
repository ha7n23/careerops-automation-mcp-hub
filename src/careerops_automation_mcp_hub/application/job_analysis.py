from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobAnalysisContractModel(BaseModel):
    """Forward-compatible Module 1 job-analysis contract model."""

    model_config = ConfigDict(extra="ignore")


class JobAnalysisInputModel(BaseModel):
    """Strict job-analysis input accepted at the Module 2 boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class JobAnalysisStatus(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"


class JobRequirementCategory(StrEnum):
    ESSENTIAL = "essential"
    DESIRABLE = "desirable"


class EvidenceMatchStrength(StrEnum):
    STRONG = "strong"
    PARTIAL = "partial"
    RELATED = "related"
    NONE = "none"


class CVSection(StrEnum):
    PROFILE = "profile"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"


class JobReviewAction(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    REGENERATE = "regenerate"


class JobReviewStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    REGENERATION_REQUESTED = "regeneration_requested"


class JobAnalysisStartRequest(JobAnalysisInputModel):
    job_id: str = Field(min_length=1, max_length=64)
    job_description: str = Field(min_length=1, max_length=50_000)


class JobRequirement(JobAnalysisContractModel):
    requirement_id: str
    name: str
    category: JobRequirementCategory
    evidence_expected: str
    importance_score: int
    source_text: str


class JobEvidenceMatch(JobAnalysisContractModel):
    requirement_id: str
    match_strength: EvidenceMatchStrength
    direct_evidence_ids: list[str]
    related_evidence_ids: list[str]
    explanation: str
    gap: bool


class JobCVProposal(JobAnalysisContractModel):
    proposal_id: str
    section: CVSection
    target_entry_id: str | None = None
    current_text: str | None = None
    proposed_text: str
    requirement_ids: list[str]
    supporting_evidence_ids: list[str]
    confidence_score: float
    warnings: list[str]
    requires_human_approval: Literal[True]


class ClaimAssessment(JobAnalysisContractModel):
    claim_text: str
    supported: bool
    supporting_evidence_ids: list[str]
    explanation: str


class ClaimVerificationReport(JobAnalysisContractModel):
    proposal_id: str
    claims: list[ClaimAssessment]
    coverage_complete: bool
    coverage_notes: list[str]
    fully_supported: bool
    unsupported_claims: list[str]


class JobAuditEvent(JobAnalysisContractModel):
    node: str
    event: str


class JobCVProposalReview(JobAnalysisContractModel):
    type: Literal["cv_proposal_review"]
    proposals: list[JobCVProposal]
    verification_reports: list[ClaimVerificationReport]
    allowed_actions: list[JobReviewAction]


class JobAnalysisBase(JobAnalysisContractModel):
    thread_id: str
    job_id: str
    role_title: str | None
    requirements: list[JobRequirement]
    evidence_matches: list[JobEvidenceMatch]
    fit_score: float
    cv_proposals: list[JobCVProposal]
    claim_verification_reports: list[ClaimVerificationReport]
    reviewable_proposal_ids: list[str]
    blocked_proposal_ids: list[str]
    audit_events: list[JobAuditEvent]


class JobAnalysisAwaitingReview(JobAnalysisBase):
    status: Literal["awaiting_review"]
    review: JobCVProposalReview


class JobAnalysisCompleted(JobAnalysisBase):
    status: Literal["completed"]
    review_status: JobReviewStatus | None = None
    final_cv_proposals: list[JobCVProposal]


JobAnalysisRun = Annotated[
    JobAnalysisAwaitingReview | JobAnalysisCompleted,
    Field(discriminator="status"),
]


class JobProposalEdit(JobAnalysisInputModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    edited_text: str = Field(min_length=1, max_length=1_500)


class JobAnalysisReviewDecision(JobAnalysisInputModel):
    action: JobReviewAction
    approved_proposal_ids: list[str] = Field(default_factory=list)
    rejected_proposal_ids: list[str] = Field(default_factory=list)
    edits: list[JobProposalEdit] = Field(default_factory=list)
    reviewer_comment: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        approved_ids = self.approved_proposal_ids
        rejected_ids = self.rejected_proposal_ids
        edited_ids = [edit.proposal_id for edit in self.edits]

        if len(approved_ids) != len(set(approved_ids)):
            raise ValueError("Approved proposal identifiers must be unique.")

        if len(rejected_ids) != len(set(rejected_ids)):
            raise ValueError("Rejected proposal identifiers must be unique.")

        if len(edited_ids) != len(set(edited_ids)):
            raise ValueError("Edited proposal identifiers must be unique.")

        approved = set(approved_ids)
        rejected = set(rejected_ids)
        edited = set(edited_ids)

        if approved & rejected:
            raise ValueError("A proposal cannot be both approved and rejected.")
        if approved & edited:
            raise ValueError("A proposal cannot be both approved and edited.")
        if rejected & edited:
            raise ValueError("A proposal cannot be both rejected and edited.")

        if self.action is JobReviewAction.APPROVE:
            if not approved:
                raise ValueError("An approval decision requires approved proposals.")
            if self.edits:
                raise ValueError("An approval decision cannot contain proposal edits.")

        if self.action is JobReviewAction.EDIT and not self.edits:
            raise ValueError("An edit decision requires at least one edit.")

        if self.action is JobReviewAction.REJECT:
            if not rejected:
                raise ValueError("A rejection decision requires rejected proposals.")
            if approved or self.edits:
                raise ValueError(
                    "A rejection decision cannot approve or edit proposals."
                )

        if self.action is JobReviewAction.REGENERATE:
            if approved or self.edits:
                raise ValueError(
                    "A regeneration request cannot approve or edit proposals."
                )
            if not rejected and not self.reviewer_comment:
                raise ValueError(
                    "A regeneration request requires rejected proposals "
                    "or a reviewer comment."
                )

        return self
