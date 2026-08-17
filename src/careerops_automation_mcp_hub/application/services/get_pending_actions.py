from dataclasses import dataclass
from datetime import datetime

from careerops_automation_mcp_hub.application.ports.unit_of_work import (
    ApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.domain.action_item import ActionItem


@dataclass(frozen=True, slots=True)
class GetPendingActionsQuery:
    user_id: str
    due_before: datetime | None = None


class GetPendingActionsService:
    def __init__(
        self,
        unit_of_work_factory: ApplicationUnitOfWorkFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def execute(
        self,
        query: GetPendingActionsQuery,
    ) -> tuple[ActionItem, ...]:
        async with self._unit_of_work_factory() as unit_of_work:
            return await unit_of_work.actions.list_pending(
                user_id=query.user_id,
                due_before=query.due_before,
            )
