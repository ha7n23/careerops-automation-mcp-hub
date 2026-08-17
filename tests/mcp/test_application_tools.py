from datetime import UTC, datetime
from uuid import UUID

import pytest
from mcp import Client
from mcp.types import TextResourceContents

from careerops_automation_mcp_hub.domain.action_item import (
    ActionItem,
    ActionItemType,
)
from careerops_automation_mcp_hub.infrastructure.memory.repositories import (
    InMemoryActionItemRepository,
    InMemoryApplicationEventRepository,
    InMemoryJobApplicationRepository,
)
from careerops_automation_mcp_hub.infrastructure.memory.unit_of_work import (
    InMemoryApplicationUnitOfWorkFactory,
)
from careerops_automation_mcp_hub.mcp.server import build_mcp_server


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def mcp_client():
    applications = InMemoryJobApplicationRepository()
    events = InMemoryApplicationEventRepository()
    actions = InMemoryActionItemRepository()

    unit_of_work_factory = InMemoryApplicationUnitOfWorkFactory(
        applications=applications,
        events=events,
        actions=actions,
    )

    server = build_mcp_server(
        user_id="USER-001",
        actor_id="MCP-TEST",
        applications=applications,
        actions=actions,
        unit_of_work_factory=unit_of_work_factory,
    )

    async with Client(server, raise_exceptions=True) as client:
        yield client, applications, events, actions


@pytest.mark.anyio
async def test_create_application_tool_returns_structured_result(
    mcp_client,
) -> None:
    client, applications, events, _ = mcp_client

    result = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )

    assert result.is_error is False
    assert result.structured_content is not None

    application_id = UUID(result.structured_content["application_id"])

    assert result.structured_content["company_name"] == "Monzo"
    assert result.structured_content["status"] == "saved"

    stored = await applications.get(
        user_id="USER-001",
        application_id=application_id,
    )

    assert stored is not None
    assert len(events.all()) == 1


@pytest.mark.anyio
async def test_get_application_tool_reads_created_application(
    mcp_client,
) -> None:
    client, _, _, _ = mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )

    assert created.structured_content is not None

    result = await client.call_tool(
        "get_application",
        {
            "application_id": created.structured_content["application_id"],
        },
    )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["company_name"] == "Monzo"


@pytest.mark.anyio
async def test_update_status_tool_uses_domain_lifecycle_policy(
    mcp_client,
) -> None:
    client, _, events, _ = mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )

    assert created.structured_content is not None
    application_id = created.structured_content["application_id"]

    result = await client.call_tool(
        "update_application_status",
        {
            "application_id": application_id,
            "target_status": "preparing",
        },
    )

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["status"] == "preparing"

    assert len(events.all()) == 2


@pytest.mark.anyio
async def test_invalid_status_transition_returns_tool_error(
    mcp_client,
) -> None:
    client, _, events, _ = mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )

    assert created.structured_content is not None

    result = await client.call_tool(
        "update_application_status",
        {
            "application_id": created.structured_content["application_id"],
            "target_status": "offer",
        },
    )

    assert result.is_error is True

    # Only APPLICATION_CREATED exists because the invalid
    # transition never reached persistence.
    assert len(events.all()) == 1


@pytest.mark.anyio
async def test_list_applications_returns_structured_results(
    mcp_client,
) -> None:
    client, _, _, _ = mcp_client

    await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )
    await client.call_tool(
        "create_application",
        {
            "company_name": "Revolut",
            "role_title": "AI Engineer",
        },
    )

    result = await client.call_tool("list_applications", {})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["count"] == 2
    assert len(result.structured_content["applications"]) == 2


@pytest.mark.anyio
async def test_get_pending_actions_returns_user_scoped_actions(
    mcp_client,
) -> None:
    client, _, _, actions = mcp_client

    action = ActionItem.create(
        application_id=UUID("11111111-1111-1111-1111-111111111111"),
        user_id="USER-001",
        action_type=ActionItemType.FOLLOW_UP,
        description="Follow up with recruiter.",
        due_at=datetime(2026, 8, 20, 12, 0, tzinfo=UTC),
    )
    await actions.add(action)

    result = await client.call_tool("get_pending_actions", {})

    assert result.is_error is False
    assert result.structured_content is not None
    assert result.structured_content["count"] == 1
    assert result.structured_content["actions"][0]["action_type"] == "follow_up"


@pytest.mark.anyio
async def test_application_resource_returns_context(
    mcp_client,
) -> None:
    client, _, _, _ = mcp_client

    created = await client.call_tool(
        "create_application",
        {
            "company_name": "Monzo",
            "role_title": "Junior AI Engineer",
        },
    )

    assert created.structured_content is not None

    application_id = created.structured_content["application_id"]

    result = await client.read_resource(f"careerops://applications/{application_id}")

    assert len(result.contents) == 1

    content = result.contents[0]

    assert isinstance(content, TextResourceContents)
    assert "Junior AI Engineer" in content.text
    assert "Monzo" in content.text
    assert "saved" in content.text


@pytest.mark.anyio
async def test_pending_actions_resource_returns_context(
    mcp_client,
) -> None:
    client, _, _, actions = mcp_client

    action = ActionItem.create(
        application_id=UUID("11111111-1111-1111-1111-111111111111"),
        user_id="USER-001",
        action_type=ActionItemType.PREPARE_INTERVIEW,
        description="Prepare for technical interview.",
    )
    await actions.add(action)

    result = await client.read_resource("careerops://actions/pending")

    content = result.contents[0]

    assert isinstance(content, TextResourceContents)
    assert "Pending Actions" in content.text
    assert "prepare_interview" in content.text
    assert "Prepare for technical interview." in content.text
