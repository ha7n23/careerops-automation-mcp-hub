from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceContractModel(BaseModel):
    """Forward-compatible Module 1 evidence contract model."""

    model_config = ConfigDict(extra="ignore")


class EvidenceInputModel(BaseModel):
    """Strict input accepted at the Module 2 evidence boundary."""

    model_config = ConfigDict(extra="forbid")


class EvidenceDocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"


class EvidenceDocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    EXTRACTED = "extracted"
    QUARANTINED = "quarantined"


class EvidenceReviewStatus(StrEnum):
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    INVALID = "invalid"


class EvidenceCategory(StrEnum):
    PROJECT = "project"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    CERTIFICATION = "certification"
    ACHIEVEMENT = "achievement"
    SKILL = "skill"


class EvidenceVerificationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class EvidenceLifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EvidenceSourceType(StrEnum):
    UPLOADED_CV = "uploaded_cv"
    MANUAL_ENTRY = "manual_entry"
    GITHUB = "github"
    EMPLOYMENT_RECORD = "employment_record"
    EDUCATION_RECORD = "education_record"
    CERTIFICATE = "certificate"


class EvidenceSection(StrEnum):
    PROFILE = "profile"
    SKILLS = "skills"
    EXPERIENCE = "experience"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"


class EvidenceOverlapScope(StrEnum):
    WITHIN_DOCUMENT = "within_document"
    APPROVED_EVIDENCE = "approved_evidence"


class EvidenceDuplicateAction(StrEnum):
    KEEP_EXISTING = "keep_existing"
    ACCEPT_SEPARATE = "accept_separate"
    REPLACE_EXISTING = "replace_existing"
    MERGE_INTO_EXISTING = "merge_into_existing"


class EvidenceDocument(EvidenceContractModel):
    document_id: str
    original_filename: str
    document_format: EvidenceDocumentFormat
    media_type: str
    size_bytes: int
    sha256_hex: str
    status: EvidenceDocumentStatus


class EvidenceDocumentSummary(EvidenceContractModel):
    document_id: str
    original_filename: str
    document_format: EvidenceDocumentFormat
    size_bytes: int
    status: EvidenceDocumentStatus
    uploaded_at: datetime
    updated_at: datetime


class EvidenceDocumentHistory(EvidenceContractModel):
    items: list[EvidenceDocumentSummary]
    count: int
    limit: int


class EvidenceSourceReference(EvidenceContractModel):
    source_type: EvidenceSourceType
    source_id: str
    page_number: int | None = None
    source_excerpt: str | None = None


class EvidenceProposal(EvidenceContractModel):
    proposal_id: str
    category: EvidenceCategory
    title: str
    verification_status: EvidenceVerificationStatus
    source_section: EvidenceSection
    source_section_order_index: int
    technologies: list[str]
    capabilities: list[str]
    claims: list[str]
    source_references: list[EvidenceSourceReference]
    warnings: list[str]


class EvidenceOverlapFinding(EvidenceContractModel):
    proposal_id: str
    scope: EvidenceOverlapScope
    matching_proposal_id: str | None = None
    matching_evidence_id: str | None = None
    matched_claims: list[str]
    same_source_excerpt: bool
    allowed_actions: list[EvidenceDuplicateAction]


class ApprovedEvidence(EvidenceContractModel):
    evidence_id: str
    category: EvidenceCategory
    title: str
    verification_status: EvidenceVerificationStatus
    lifecycle_status: EvidenceLifecycleStatus
    technologies: list[str]
    capabilities: list[str]
    approved_claims: list[str]
    source_references: list[EvidenceSourceReference]


class EvidenceProposalEdit(EvidenceInputModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=250)
    technologies: list[str] | None = None
    capabilities: list[str] | None = None
    claims: list[str] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if all(
            value is None
            for value in (
                self.title,
                self.technologies,
                self.capabilities,
                self.claims,
            )
        ):
            raise ValueError("An evidence edit must change at least one field.")

        return self


class EvidenceDuplicateResolution(EvidenceInputModel):
    proposal_id: str = Field(min_length=1, max_length=64)
    scope: EvidenceOverlapScope
    action: EvidenceDuplicateAction
    matching_proposal_id: str | None = Field(default=None, max_length=64)
    matching_evidence_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.scope is EvidenceOverlapScope.WITHIN_DOCUMENT:
            if (
                self.matching_proposal_id is None
                or self.matching_evidence_id is not None
            ):
                raise ValueError(
                    "Within-document resolution requires one matching proposal."
                )

            if self.action not in {
                EvidenceDuplicateAction.KEEP_EXISTING,
                EvidenceDuplicateAction.ACCEPT_SEPARATE,
            }:
                raise ValueError(
                    "Within-document overlap supports only keep-existing "
                    "or accept-separate."
                )

        if self.scope is EvidenceOverlapScope.APPROVED_EVIDENCE and (
            self.matching_evidence_id is None or self.matching_proposal_id is not None
        ):
            raise ValueError(
                "Approved-evidence resolution requires one matching evidence item."
            )

        return self


class EvidenceReviewDecision(EvidenceInputModel):
    approved_proposal_ids: list[str] = Field(default_factory=list)
    rejected_proposal_ids: list[str] = Field(default_factory=list)
    edits: list[EvidenceProposalEdit] = Field(default_factory=list)
    duplicate_resolutions: list[EvidenceDuplicateResolution] = Field(
        default_factory=list
    )
    reviewer_comment: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def validate_decisions(self) -> Self:
        approved = self.approved_proposal_ids
        rejected = self.rejected_proposal_ids
        edited = [edit.proposal_id for edit in self.edits]

        if len(approved) != len(set(approved)):
            raise ValueError("Approved evidence proposal identifiers must be unique.")

        if len(rejected) != len(set(rejected)):
            raise ValueError("Rejected evidence proposal identifiers must be unique.")

        if len(edited) != len(set(edited)):
            raise ValueError("Edited evidence proposal identifiers must be unique.")

        if set(approved) & set(rejected):
            raise ValueError(
                "An evidence proposal cannot be both approved and rejected."
            )

        if set(approved) & set(edited):
            raise ValueError("An evidence proposal cannot be both approved and edited.")

        if set(rejected) & set(edited):
            raise ValueError("An evidence proposal cannot be both rejected and edited.")

        if not (approved or rejected or edited):
            raise ValueError("Evidence review requires at least one proposal decision.")

        return self


class EvidenceDuplicateUpdate(EvidenceContractModel):
    proposal_id: str
    action: EvidenceDuplicateAction
    before: ApprovedEvidence
    after: ApprovedEvidence


class EvidenceReviewResult(EvidenceContractModel):
    approved_proposal_ids: list[str]
    edited_proposal_ids: list[str]
    rejected_proposal_ids: list[str]
    duplicate_resolutions: list[EvidenceDuplicateResolution]
    approved_evidence: list[ApprovedEvidence]
    evidence_updates: list[EvidenceDuplicateUpdate]


class EvidenceReviewRun(EvidenceContractModel):
    review_run_id: str
    document_id: str
    status: EvidenceReviewStatus
    proposals: list[EvidenceProposal]
    overlap_findings: list[EvidenceOverlapFinding]
    document_warnings: list[str]
    review_result: EvidenceReviewResult | None = None


class EvidenceReviewRunSummary(EvidenceContractModel):
    review_run_id: str
    document_id: str
    status: EvidenceReviewStatus
    proposal_count: int
    approved_evidence_count: int
    created_at: datetime
    updated_at: datetime


class EvidenceReviewHistory(EvidenceContractModel):
    items: list[EvidenceReviewRunSummary]
    count: int
    limit: int
