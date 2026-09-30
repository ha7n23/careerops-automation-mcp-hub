import json
from pathlib import Path
from typing import Any, cast

POLICY_PATH = Path("openclaw/config/careerops.patch.json")
COMPOSE_PATH = Path("openclaw/compose.yaml")

PRIMARY_MODEL = "openrouter/nvidia/nemotron-3.5-lightning:free"
FALLBACK_MODEL = "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"

APPROVED_MCP_TOOLS = {
    "archive_registry_evidence",
    "create_application",
    "create_text_evidence_source",
    "edit_registry_evidence",
    "generate_final_cv",
    "get_application",
    "get_application_analysis",
    "get_evidence_review",
    "get_final_cv",
    "get_job_analysis",
    "get_pending_actions",
    "get_registry_evidence",
    "list_applications",
    "list_evidence_documents",
    "list_evidence_reviews",
    "prepare_application",
    "restore_registry_evidence",
    "review_application",
    "review_job_analysis",
    "search_evidence_registry",
    "start_evidence_review",
    "start_job_analysis",
    "submit_evidence_review",
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
    assert defaults["thinkingDefault"] == "low"


def test_openclaw_uses_only_careerops_skill_and_minimal_tools() -> None:
    policy = load_policy()

    assert policy["agents"]["defaults"]["skills"] == ["careerops"]
    assert policy["tools"] == {
        "profile": "minimal",
        "alsoAllow": ["careerops__*"],
    }


def test_openclaw_configures_a_bounded_text_assistant_endpoint() -> None:
    policy = load_policy()

    endpoints = policy["gateway"]["http"]["endpoints"]

    assert endpoints == {
        "chatCompletions": {
            "enabled": True,
            "maxBodyBytes": 32768,
            "maxImageParts": 0,
        }
    }


def test_openclaw_mcp_server_is_least_privilege() -> None:
    policy = load_policy()

    server = policy["mcp"]["servers"]["careerops"]

    assert server["transport"] == "streamable-http"
    assert server["url"] == "http://host.docker.internal:8001/mcp"
    assert server["connectTimeout"] == 5
    assert server["timeout"] == 660
    assert server["headers"] == {
        "Authorization": "Bearer ${CAREEROPS_DEV_ACCESS_TOKEN}"
    }

    exposed_tools = set(server["toolFilter"]["include"])

    assert exposed_tools == APPROVED_MCP_TOOLS
    assert "update_application_status" not in exposed_tools


def test_openclaw_services_load_the_module_environment_without_shadowing() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert compose.count("path: ../.env") == 2
    assert "OPENCLAW_GATEWAY_TOKEN:" not in compose
    assert "OPENROUTER_API_KEY:" not in compose
