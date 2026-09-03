import json
from pathlib import Path
from typing import Any, cast

POLICY_PATH = Path("openclaw/config/careerops.patch.json")

PRIMARY_MODEL = "openrouter/nvidia/nemotron-3.5-lightning:free"
FALLBACK_MODEL = "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"

APPROVED_MCP_TOOLS = {
    "create_application",
    "get_application",
    "get_application_analysis",
    "get_pending_actions",
    "list_applications",
    "prepare_application",
    "review_application",
}


def load_policy() -> dict[str, Any]:
    data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    return cast(dict[str, Any], data)


def test_openclaw_models_are_explicitly_free_and_allowlisted() -> None:
    policy = load_policy()

    defaults = policy["agents"]["defaults"]
    model = defaults["model"]
    models = defaults["models"]

    assert model["primary"] == PRIMARY_MODEL
    assert model["fallbacks"] == [FALLBACK_MODEL]
    assert set(models) == {PRIMARY_MODEL, FALLBACK_MODEL}
    assert all(model_name.endswith(":free") for model_name in models)
    assert "openrouter/auto" not in models


def test_openclaw_uses_only_careerops_skill_and_minimal_tools() -> None:
    policy = load_policy()

    assert policy["agents"]["defaults"]["skills"] == ["careerops"]
    assert policy["tools"] == {
        "profile": "minimal",
        "alsoAllow": ["careerops__*"],
    }


def test_openclaw_mcp_server_is_least_privilege() -> None:
    policy = load_policy()

    server = policy["mcp"]["servers"]["careerops"]

    assert server["transport"] == "streamable-http"
    assert server["url"] == "http://host.docker.internal:8001/mcp"
    assert server["connectTimeout"] == 5
    assert server["timeout"] == 660

    exposed_tools = set(server["toolFilter"]["include"])

    assert exposed_tools == APPROVED_MCP_TOOLS
    assert "update_application_status" not in exposed_tools
