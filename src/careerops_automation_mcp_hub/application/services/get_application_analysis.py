from dataclasses import dataclass
from uuid import UUID

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineJobAnalysis,
)
from careerops_automation_mcp_hub.application.errors import (
    AgentEngineContractError,
    ApplicationAnalysisUnavailableError,
    ApplicationNotFoundError,
)
from careerops_automation_mcp_hub.application.ports.agent_engine import (
    AgentEngineClient,
)
from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.application_preparation import (
    ApplicationPreparation,
)
from careerops_automation_mcp_hub.domain.job_application import (
    JobApplication,
)


@dataclass(frozen=True, slots=True)
class GetApplicationAnalysisQuery:
    user_id: str
    application_id: UUID


@dataclass(frozen=True, slots=True)
class GetApplicationAnalysisResult:
    application: JobApplication
    preparation: ApplicationPreparation
    analysis: AgentEngineJobAnalysis


class GetApplicationAnalysisService:
    """Recover the authoritative Agent Engine analysis for an application."""

    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
        agent_engine_client: AgentEngineClient,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._agent_engine_client = agent_engine_client

    async def execute(
        self,
        query: GetApplicationAnalysisQuery,
    ) -> GetApplicationAnalysisResult:
        user_id = query.user_id.strip()

        if not user_id:
            raise ValueError("user_id must not be blank.")

        async with self._unit_of_work_factory() as unit_of_work:
            application = await unit_of_work.applications.get(
                user_id=user_id,
                application_id=query.application_id,
            )

            if application is None:
                raise ApplicationNotFoundError(query.application_id)

            preparation = await unit_of_work.preparations.get_for_application(
                user_id=user_id,
                application_id=query.application_id,
            )

            if preparation is None or preparation.agent_engine_thread_id is None:
                raise ApplicationAnalysisUnavailableError(query.application_id)

            thread_id = preparation.agent_engine_thread_id
            expected_job_id = preparation.agent_engine_job_id

        analysis = await self._agent_engine_client.get_job_analysis(
            user_id=user_id,
            thread_id=thread_id,
        )

        if analysis.thread_id != thread_id:
            raise AgentEngineContractError(
                "Agent Engine returned an analysis for an unexpected thread_id."
            )

        if analysis.job_id != expected_job_id:
            raise AgentEngineContractError(
                "Agent Engine returned an analysis for an unexpected job_id."
            )

        return GetApplicationAnalysisResult(
            application=application,
            preparation=preparation,
            analysis=analysis,
        )
