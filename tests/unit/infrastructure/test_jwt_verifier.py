import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from jwt.algorithms import RSAAlgorithm

from careerops_automation_mcp_hub.infrastructure.auth.jwt_verifier import (
    JwtTokenVerifier,
)


class StaticJwkResolver:
    def __init__(self, signing_key: PyJWK) -> None:
        self._signing_key = signing_key

    def get_signing_key_from_jwt(
        self,
        token: str,
    ) -> PyJWK:
        return self._signing_key


@pytest.fixture
def jwt_key_pair() -> tuple[rsa.RSAPrivateKey, PyJWK]:
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    public_jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    public_jwk.update(
        {
            "kid": "careerops-test-key",
            "alg": "RS256",
            "use": "sig",
        }
    )

    return private_key, PyJWK.from_dict(public_jwk)


def build_token(
    private_key: rsa.RSAPrivateKey,
    **overrides: object,
) -> str:
    now = int(time.time())

    claims: dict[str, object] = {
        "iss": "https://auth.test/",
        "aud": "careerops-automation-mcp-hub",
        "sub": "USER-001",
        "client_id": "openclaw",
        "scope": "careerops:applications profile",
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)

    return jwt.encode(
        claims,
        private_key,
        algorithm="RS256",
        headers={"kid": "careerops-test-key"},
    )


def build_verifier(
    signing_key: PyJWK,
) -> JwtTokenVerifier:
    return JwtTokenVerifier(
        issuer="https://auth.test/",
        audience="careerops-automation-mcp-hub",
        jwks_url="https://auth.test/.well-known/jwks.json",
        jwk_resolver=StaticJwkResolver(signing_key),
    )


@pytest.mark.anyio
async def test_valid_jwt_maps_to_mcp_access_token(
    jwt_key_pair: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = jwt_key_pair

    token = build_token(private_key)
    verifier = build_verifier(signing_key)

    access_token = await verifier.verify_token(token)

    assert access_token is not None
    assert access_token.subject == "USER-001"
    assert access_token.client_id == "openclaw"
    assert access_token.scopes == [
        "careerops:applications",
        "profile",
    ]
    assert access_token.resource == "careerops-automation-mcp-hub"


@pytest.mark.anyio
async def test_verifier_supports_azp_and_scp_claims(
    jwt_key_pair: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = jwt_key_pair

    token = build_token(
        private_key,
        client_id=None,
        azp="openclaw",
        scope=None,
        scp=["careerops:applications"],
    )

    verifier = build_verifier(signing_key)

    access_token = await verifier.verify_token(token)

    assert access_token is not None
    assert access_token.client_id == "openclaw"
    assert access_token.scopes == ["careerops:applications"]


@pytest.mark.anyio
async def test_verifier_rejects_wrong_audience(
    jwt_key_pair: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = jwt_key_pair

    token = build_token(
        private_key,
        aud="another-service",
    )

    verifier = build_verifier(signing_key)

    assert await verifier.verify_token(token) is None


@pytest.mark.anyio
async def test_verifier_rejects_expired_token(
    jwt_key_pair: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = jwt_key_pair

    token = build_token(
        private_key,
        exp=int(time.time()) - 120,
    )

    verifier = build_verifier(signing_key)

    assert await verifier.verify_token(token) is None


@pytest.mark.anyio
async def test_verifier_requires_client_identity(
    jwt_key_pair: tuple[rsa.RSAPrivateKey, PyJWK],
) -> None:
    private_key, signing_key = jwt_key_pair

    token = build_token(
        private_key,
        client_id=None,
    )

    verifier = build_verifier(signing_key)

    assert await verifier.verify_token(token) is None


def test_verifier_rejects_insecure_remote_jwks_url() -> None:
    with pytest.raises(
        ValueError,
        match="JWKS URL must use HTTPS",
    ):
        JwtTokenVerifier(
            issuer="https://auth.test/",
            audience="careerops-automation-mcp-hub",
            jwks_url="http://auth.example.com/jwks.json",
        )
