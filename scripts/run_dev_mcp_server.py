"""Development-only full REST and MCP gateway for local Module 3 work."""

import os

import uvicorn
from fastapi import FastAPI
from pydantic import AnyHttpUrl

from careerops_automation_mcp_hub.api.app import create_app
from careerops_automation_mcp_hub.core.config import get_settings
from careerops_automation_mcp_hub.infrastructure.auth.development import (
    DEFAULT_DEVELOPMENT_ACCESS_TOKEN,
    DevelopmentTokenVerifier,
)


def create_development_app() -> FastAPI:
    """Create the authenticated production surface with a local-only principal."""
    access_token = os.getenv(
        "CAREEROPS_DEV_ACCESS_TOKEN",
        DEFAULT_DEVELOPMENT_ACCESS_TOKEN,
    )

    if not access_token:
        raise ValueError("CAREEROPS_DEV_ACCESS_TOKEN must not be empty.")

    settings = get_settings().model_copy(
        update={
            "mcp_host": "0.0.0.0",
            "mcp_resource_url": AnyHttpUrl("http://127.0.0.1:8001/mcp"),
        }
    )

    return create_app(
        token_verifier=DevelopmentTokenVerifier(
            access_token=access_token,
            user_id=os.getenv("CAREEROPS_DEV_MCP_USER_ID", "USER-DEMO-001"),
            actor_id=os.getenv("CAREEROPS_DEV_MCP_ACTOR_ID", "LOCAL-DEV"),
        ),
        settings=settings,
    )


if __name__ == "__main__":
    uvicorn.run(
        create_development_app(),
        host="0.0.0.0",
        port=8001,
    )
