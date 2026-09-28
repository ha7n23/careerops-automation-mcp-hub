from typing import Protocol

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
)
from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocument,
    EvidenceDocumentHistory,
    EvidenceReviewDecision,
    EvidenceReviewHistory,
    EvidenceReviewRun,
)


class AgentEngineClient(Protocol):
    """Boundary used by Module 2 to communicate with the Agent Engine."""

    async def analyse_job(
        self,
        *,
        user_id: str,
        job_id: str,
        job_description: str,
    ) -> AgentEngineJobAnalysis:
        """Start an evidence-grounded job analysis."""
        ...

    async def get_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> AgentEngineJobAnalysis:
        """Recover the current durable state of one job analysis."""
        ...

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        """Submit a human review decision to a paused analysis."""
        ...

    async def list_evidence_documents(
        self,
        *,
        user_id: str,
        limit: int,
    ) -> EvidenceDocumentHistory:
        """List the user's bounded evidence-source history."""
        ...

    async def upload_evidence_document(
        self,
        *,
        user_id: str,
        filename: str,
        media_type: str,
        data: bytes,
    ) -> EvidenceDocument:
        """Upload one PDF or DOCX evidence source."""
        ...

    async def create_text_evidence_source(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
    ) -> EvidenceDocument:
        """Create one pasted-text evidence source."""
        ...

    async def start_evidence_review(
        self,
        *,
        user_id: str,
        document_id: str,
    ) -> EvidenceReviewRun:
        """Start or recover evidence extraction and review."""
        ...

    async def list_evidence_reviews(
        self,
        *,
        user_id: str,
        limit: int,
    ) -> EvidenceReviewHistory:
        """List the user's bounded evidence-review history."""
        ...

    async def get_evidence_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
    ) -> EvidenceReviewRun:
        """Recover one durable evidence-review run."""
        ...

    async def submit_evidence_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
        decision: EvidenceReviewDecision,
    ) -> EvidenceReviewRun:
        """Submit a complete human evidence decision."""
        ...
