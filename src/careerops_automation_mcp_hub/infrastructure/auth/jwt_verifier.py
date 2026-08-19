import asyncio
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import urlparse

import jwt
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from mcp.server.auth.provider import AccessToken


class JwkResolver(Protocol):
    """Resolve the trusted signing key for a JWT."""

    def get_signing_key_from_jwt(
        self,
        token: str,
    ) -> PyJWK:
        """Return the signing key identified by the JWT header."""
        ...


class JwtTokenVerifier:
    """Verify OAuth JWT access tokens against a trusted JWKS endpoint."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str,
        algorithm: str = "RS256",
        jwk_resolver: JwkResolver | None = None,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._algorithm = algorithm

        self._validate_jwks_url(jwks_url)

        self._jwk_resolver = (
            jwk_resolver
            if jwk_resolver is not None
            else PyJWKClient(
                jwks_url,
                cache_jwk_set=True,
                lifespan=300,
                timeout=5,
            )
        )

    async def verify_token(
        self,
        token: str,
    ) -> AccessToken | None:
        """Verify a JWT and convert its claims to an MCP access token."""
        try:
            signing_key = await asyncio.to_thread(
                self._jwk_resolver.get_signing_key_from_jwt,
                token,
            )

            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[self._algorithm],
                audience=self._audience,
                issuer=self._issuer,
                leeway=30,
                options={
                    "require": [
                        "exp",
                        "iss",
                        "aud",
                        "sub",
                    ]
                },
            )
        except (InvalidTokenError, PyJWKClientError, ValueError, TypeError):
            return None

        subject = claims.get("sub")

        if not isinstance(subject, str) or not subject.strip():
            return None

        client_id = self._extract_client_id(claims)

        if client_id is None:
            return None

        expires_at = claims.get("exp")

        if not isinstance(expires_at, (int, float)):
            return None

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=self._extract_scopes(claims),
            expires_at=int(expires_at),
            resource=self._audience,
            subject=subject.strip(),
            claims=dict(claims),
        )

    @staticmethod
    def _extract_client_id(
        claims: Mapping[str, Any],
    ) -> str | None:
        raw_client_id = claims.get("client_id")

        if raw_client_id is None:
            raw_client_id = claims.get("azp")

        if not isinstance(raw_client_id, str):
            return None

        client_id = raw_client_id.strip()

        return client_id or None

    @staticmethod
    def _extract_scopes(
        claims: Mapping[str, Any],
    ) -> list[str]:
        raw_scopes = claims.get("scope")

        if raw_scopes is None:
            raw_scopes = claims.get("scp")

        if isinstance(raw_scopes, str):
            return [scope for scope in raw_scopes.split() if scope]

        if isinstance(raw_scopes, list):
            return [scope for scope in raw_scopes if isinstance(scope, str) and scope]

        return []

    @staticmethod
    def _validate_jwks_url(jwks_url: str) -> None:
        parsed = urlparse(jwks_url)

        is_https = parsed.scheme == "https"
        is_local_http = parsed.scheme == "http" and parsed.hostname in {
            "localhost",
            "127.0.0.1",
            "::1",
        }

        if not is_https and not is_local_http:
            raise ValueError("JWKS URL must use HTTPS except for local development.")
