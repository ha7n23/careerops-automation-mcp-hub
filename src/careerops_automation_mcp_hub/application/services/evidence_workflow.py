from careerops_automation_mcp_hub.application.evidence import (
    EvidenceDocument,
    EvidenceDocumentHistory,
    EvidenceReviewDecision,
    EvidenceReviewHistory,
    EvidenceReviewRun,
)
from careerops_automation_mcp_hub.application.ports.agent_engine import (
    AgentEngineClient,
)


class EvidenceWorkflowService:
    """Shared Module 2 application boundary for Module 1 evidence workflows."""

    def __init__(self, agent_engine_client: AgentEngineClient) -> None:
        self._agent_engine_client = agent_engine_client

    async def list_documents(
        self,
        *,
        user_id: str,
        limit: int = 100,
    ) -> EvidenceDocumentHistory:
        return await self._agent_engine_client.list_evidence_documents(
            user_id=user_id,
            limit=limit,
        )

    async def upload_document(
        self,
        *,
        user_id: str,
        filename: str,
        media_type: str,
        data: bytes,
    ) -> EvidenceDocument:
        return await self._agent_engine_client.upload_evidence_document(
            user_id=user_id,
            filename=filename,
            media_type=media_type,
            data=data,
        )

    async def create_text_source(
        self,
        *,
        user_id: str,
        title: str,
        content: str,
    ) -> EvidenceDocument:
        return await self._agent_engine_client.create_text_evidence_source(
            user_id=user_id,
            title=title,
            content=content,
        )

    async def start_review(
        self,
        *,
        user_id: str,
        document_id: str,
    ) -> EvidenceReviewRun:
        return await self._agent_engine_client.start_evidence_review(
            user_id=user_id,
            document_id=document_id,
        )

    async def list_reviews(
        self,
        *,
        user_id: str,
        limit: int = 100,
    ) -> EvidenceReviewHistory:
        return await self._agent_engine_client.list_evidence_reviews(
            user_id=user_id,
            limit=limit,
        )

    async def get_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
    ) -> EvidenceReviewRun:
        return await self._agent_engine_client.get_evidence_review(
            user_id=user_id,
            review_run_id=review_run_id,
        )

    async def submit_review(
        self,
        *,
        user_id: str,
        review_run_id: str,
        decision: EvidenceReviewDecision,
    ) -> EvidenceReviewRun:
        return await self._agent_engine_client.submit_evidence_review(
            user_id=user_id,
            review_run_id=review_run_id,
            decision=decision,
        )
