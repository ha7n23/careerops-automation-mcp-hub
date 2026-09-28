from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from careerops_automation_mcp_hub.application.job_analysis import JobReviewStatus


class FinalCVContractModel(BaseModel):
    """Forward-compatible Module 1 final-CV contract model."""

    model_config = ConfigDict(extra="ignore")


class FinalCVInputModel(BaseModel):
    """Strict final-CV input accepted at the Module 2 boundary."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CVVersionStatus(StrEnum):
    ASSEMBLED = "assembled"
    RENDERED = "rendered"
    VERIFIED = "verified"


class CVArtifactFormat(StrEnum):
    DOCX = "docx"
    PDF = "pdf"


class CVArtifactVerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class FinalCVGenerationRequest(FinalCVInputModel):
    thread_id: str = Field(min_length=1, max_length=64)
    source_document_id: str = Field(min_length=1, max_length=64)


class CVArtifactMetadata(FinalCVContractModel):
    artifact_id: str
    artifact_format: CVArtifactFormat
    size_bytes: int
    sha256_hex: str
    verification_status: CVArtifactVerificationStatus


class CVVersionMetadata(FinalCVContractModel):
    cv_version_id: str
    cv_id: str
    version_number: int
    parent_version_id: str | None
    status: CVVersionStatus
    source_document_id: str
    job_id: str
    thread_id: str
    review_status: JobReviewStatus
    template_id: str
    template_version: str
    workflow_version: str
    artifacts: list[CVArtifactMetadata]


class FinalCVVersion(CVVersionMetadata):
    reused_existing_version: bool


@dataclass(frozen=True, slots=True)
class CVArtifactDownload:
    data: bytes
    media_type: str
    content_disposition: str
