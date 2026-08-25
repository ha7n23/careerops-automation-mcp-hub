from typing import Protocol

from careerops_automation_mcp_hub.application.agent_engine import (
    AgentEngineJobAnalysis,
    AgentEngineReviewDecision,
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

    async def review_job_analysis(
        self,
        *,
        user_id: str,
        thread_id: str,
        decision: AgentEngineReviewDecision,
    ) -> AgentEngineJobAnalysis:
        """Submit a human review decision to a paused analysis."""
        ...
