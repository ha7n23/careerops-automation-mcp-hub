from careerops_automation_mcp_hub.application.final_cv import (
    CVArtifactDownload,
    CVArtifactFormat,
    CVVersionMetadata,
    FinalCVGenerationRequest,
    FinalCVVersion,
)
from careerops_automation_mcp_hub.application.job_analysis import (
    JobAnalysisReviewDecision,
    JobAnalysisRun,
    JobAnalysisStartRequest,
)
from careerops_automation_mcp_hub.application.ports.agent_engine import (
    AgentEngineClient,
)


class JobCVGatewayService:
    """Shared Module 2 boundary for job analysis and final-CV delivery."""

    def __init__(self, agent_engine_client: AgentEngineClient) -> None:
        self._agent_engine_client = agent_engine_client

    async def start_analysis(
        self,
        *,
        user_id: str,
        request: JobAnalysisStartRequest,
    ) -> JobAnalysisRun:
        return await self._agent_engine_client.start_job_analysis(
            user_id=user_id,
            request=request,
        )

    async def recover_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
    ) -> JobAnalysisRun:
        return await self._agent_engine_client.recover_job_analysis(
            user_id=user_id,
            thread_id=thread_id,
        )

    async def review_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: JobAnalysisReviewDecision,
    ) -> JobAnalysisRun:
        return await self._agent_engine_client.submit_job_analysis_review(
            user_id=user_id,
            thread_id=thread_id,
            decision=decision,
        )

    async def generate_final_cv(
        self,
        *,
        user_id: str,
        request: FinalCVGenerationRequest,
    ) -> FinalCVVersion:
        return await self._agent_engine_client.generate_final_cv(
            user_id=user_id,
            request=request,
        )

    async def get_final_cv(
        self,
        *,
        user_id: str,
        cv_version_id: str,
    ) -> CVVersionMetadata:
        return await self._agent_engine_client.get_final_cv(
            user_id=user_id,
            cv_version_id=cv_version_id,
        )

    async def download_final_cv_artifact(
        self,
        *,
        user_id: str,
        cv_version_id: str,
        artifact_format: CVArtifactFormat,
    ) -> CVArtifactDownload:
        return await self._agent_engine_client.download_final_cv_artifact(
            user_id=user_id,
            cv_version_id=cv_version_id,
            artifact_format=artifact_format,
        )
