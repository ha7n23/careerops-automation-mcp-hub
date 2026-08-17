from dataclasses import dataclass
from datetime import datetime

from careerops_automation_mcp_hub.application.ports.repositories import (
    ActionItemRepository,
)
from careerops_automation_mcp_hub.domain.action_item import ActionItem


@dataclass(frozen=True, slots=True)
class GetPendingActionsQuery:
    user_id: str
    due_before: datetime | None = None


class GetPendingActionsService:
    def __init__(
        self,
        actions: ActionItemRepository,
    ) -> None:
        self._actions = actions

    async def execute(
        self,
        query: GetPendingActionsQuery,
    ) -> tuple[ActionItem, ...]:
        return await self._actions.list_pending(
            user_id=query.user_id,
            due_before=query.due_before,
        )
