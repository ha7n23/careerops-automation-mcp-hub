from careerops_automation_mcp_hub.application.evidence import (
    ApprovedEvidence,
    EvidenceCategory,
    EvidenceLifecycleStatus,
    EvidenceRegistryEdit,
    EvidenceRegistryPage,
)
from careerops_automation_mcp_hub.application.ports.agent_engine import (
    AgentEngineClient,
)


class EvidenceRegistryService:
    """Shared Module 2 boundary for approved evidence management."""

    def __init__(self, agent_engine_client: AgentEngineClient) -> None:
        self._agent_engine_client = agent_engine_client

    async def query(
        self,
        *,
        user_id: str,
        query: str | None = None,
        category: EvidenceCategory | None = None,
        lifecycle_status: EvidenceLifecycleStatus = EvidenceLifecycleStatus.ACTIVE,
        offset: int = 0,
        limit: int = 100,
    ) -> EvidenceRegistryPage:
        return await self._agent_engine_client.query_evidence_registry(
            user_id=user_id,
            query=query,
            category=category,
            lifecycle_status=lifecycle_status,
            offset=offset,
            limit=limit,
        )

    async def get(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        return await self._agent_engine_client.get_evidence(
            user_id=user_id,
            evidence_id=evidence_id,
        )

    async def edit(
        self,
        *,
        user_id: str,
        evidence_id: str,
        edit: EvidenceRegistryEdit,
    ) -> ApprovedEvidence:
        return await self._agent_engine_client.edit_evidence(
            user_id=user_id,
            evidence_id=evidence_id,
            edit=edit,
        )

    async def archive(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        return await self._agent_engine_client.archive_evidence(
            user_id=user_id,
            evidence_id=evidence_id,
        )

    async def restore(
        self,
        *,
        user_id: str,
        evidence_id: str,
    ) -> ApprovedEvidence:
        return await self._agent_engine_client.restore_evidence(
            user_id=user_id,
            evidence_id=evidence_id,
        )
