"""Development-only authentication for the local full gateway launcher."""

import secrets

from mcp.server.auth.provider import AccessToken, TokenVerifier

DEFAULT_DEVELOPMENT_ACCESS_TOKEN = "careerops-local-dev-token"


class DevelopmentTokenVerifier(TokenVerifier):
    """Accept one explicit local token and derive a fixed development principal."""

    def __init__(
        self,
        *,
        access_token: str,
        user_id: str,
        actor_id: str,
    ) -> None:
        self._access_token = access_token
        self._user_id = user_id
        self._actor_id = actor_id

    async def verify_token(self, token: str) -> AccessToken | None:
        if not secrets.compare_digest(token, self._access_token):
            return None

        return AccessToken(
            token=token,
            client_id=self._actor_id,
            scopes=["careerops:applications"],
            expires_at=4_102_444_800,
            resource="careerops-automation-mcp-hub",
            subject=self._user_id,
            claims={"development_only": True},
        )
