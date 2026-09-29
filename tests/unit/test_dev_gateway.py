import pytest

from careerops_automation_mcp_hub.infrastructure.auth.development import (
    DEFAULT_DEVELOPMENT_ACCESS_TOKEN,
    DevelopmentTokenVerifier,
)


@pytest.mark.anyio
async def test_development_token_verifier_returns_fixed_local_principal() -> None:
    verifier = DevelopmentTokenVerifier(
        access_token=DEFAULT_DEVELOPMENT_ACCESS_TOKEN,
        user_id="USER-DEV-001",
        actor_id="MODULE-3-DEV",
    )

    access_token = await verifier.verify_token(DEFAULT_DEVELOPMENT_ACCESS_TOKEN)

    assert access_token is not None
    assert access_token.subject == "USER-DEV-001"
    assert access_token.client_id == "MODULE-3-DEV"
    assert access_token.scopes == ["careerops:applications"]


@pytest.mark.anyio
async def test_development_token_verifier_rejects_other_tokens() -> None:
    verifier = DevelopmentTokenVerifier(
        access_token=DEFAULT_DEVELOPMENT_ACCESS_TOKEN,
        user_id="USER-DEV-001",
        actor_id="MODULE-3-DEV",
    )

    assert await verifier.verify_token("wrong-token") is None
