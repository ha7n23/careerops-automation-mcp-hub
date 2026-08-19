from fastapi import FastAPI

from careerops_automation_mcp_hub.api.app import create_app
from careerops_automation_mcp_hub.core.config import get_settings
from careerops_automation_mcp_hub.infrastructure.auth.jwt_verifier import (
    JwtTokenVerifier,
)


def create_production_app() -> FastAPI:
    """Create the runnable authenticated CareerOps service."""
    settings = get_settings()

    token_verifier = JwtTokenVerifier(
        issuer=str(settings.auth_issuer_url),
        audience=settings.auth_audience,
        jwks_url=str(settings.auth_jwks_url),
        algorithm=settings.auth_jwt_algorithm,
    )

    return create_app(
        token_verifier=token_verifier,
        settings=settings,
    )
