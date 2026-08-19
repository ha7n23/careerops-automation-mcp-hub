import pytest
from mcp.server.auth.provider import AccessToken

from careerops_automation_mcp_hub.mcp.principal import (
    AccessTokenPrincipalProvider,
    Principal,
    PrincipalUnavailableError,
    StaticPrincipalProvider,
)


def test_principal_normalizes_identity_values() -> None:
    principal = Principal(
        user_id="  USER-001  ",
        actor_id="  MCP-TEST  ",
    )

    assert principal.user_id == "USER-001"
    assert principal.actor_id == "MCP-TEST"


@pytest.mark.parametrize(
    ("user_id", "actor_id"),
    [
        ("", "MCP-TEST"),
        ("USER-001", "   "),
    ],
)
def test_principal_rejects_blank_identity(
    user_id: str,
    actor_id: str,
) -> None:
    with pytest.raises(ValueError):
        Principal(
            user_id=user_id,
            actor_id=actor_id,
        )


def test_static_provider_returns_configured_principal() -> None:
    principal = Principal(
        user_id="USER-001",
        actor_id="MCP-TEST",
    )
    provider = StaticPrincipalProvider(principal)

    assert provider.get_principal() is principal


def test_access_token_provider_builds_principal() -> None:
    access_token = AccessToken(
        token="verified-token",
        client_id="openclaw",
        scopes=["careerops:applications"],
        subject="USER-001",
    )

    provider = AccessTokenPrincipalProvider(token_getter=lambda: access_token)

    principal = provider.get_principal()

    assert principal.user_id == "USER-001"
    assert principal.actor_id == "openclaw"


def test_access_token_provider_requires_authenticated_token() -> None:
    provider = AccessTokenPrincipalProvider(token_getter=lambda: None)

    with pytest.raises(
        PrincipalUnavailableError,
        match="No authenticated MCP access token",
    ):
        provider.get_principal()


def test_access_token_provider_requires_subject() -> None:
    access_token = AccessToken(
        token="verified-token",
        client_id="openclaw",
        scopes=["careerops:applications"],
        subject=None,
    )

    provider = AccessTokenPrincipalProvider(token_getter=lambda: access_token)

    with pytest.raises(
        PrincipalUnavailableError,
        match="does not identify a subject",
    ):
        provider.get_principal()


def test_access_token_provider_requires_client_id() -> None:
    access_token = AccessToken(
        token="verified-token",
        client_id="   ",
        scopes=["careerops:applications"],
        subject="USER-001",
    )

    provider = AccessTokenPrincipalProvider(token_getter=lambda: access_token)

    with pytest.raises(
        PrincipalUnavailableError,
        match="does not identify a client",
    ):
        provider.get_principal()
