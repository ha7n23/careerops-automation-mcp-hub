from functools import lru_cache

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://careerops:careerops@localhost:5433/careerops"
    )

    auth_issuer_url: AnyHttpUrl = AnyHttpUrl("https://auth.example.com")
    auth_jwks_url: AnyHttpUrl = AnyHttpUrl(
        "https://auth.example.com/.well-known/jwks.json"
    )
    auth_audience: str = "careerops-automation-mcp-hub"
    auth_jwt_algorithm: str = "RS256"

    mcp_resource_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000/mcp")
    mcp_host: str = "127.0.0.1"
    mcp_required_scope: str = "careerops:applications"
    mcp_json_response: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return cached application configuration."""
    return Settings()
