from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
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

    agent_engine_base_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8000")
    agent_engine_service_key: SecretStr = SecretStr("")

    agent_engine_connect_timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
    )
    agent_engine_read_timeout_seconds: float = Field(
        default=180.0,
        gt=0.0,
    )
    agent_engine_write_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
    )
    agent_engine_pool_timeout_seconds: float = Field(
        default=5.0,
        gt=0.0,
    )

    @field_validator("agent_engine_service_key")
    @classmethod
    def validate_agent_engine_service_key(
        cls,
        value: SecretStr,
    ) -> SecretStr:
        """Reject an Agent Engine service credential that Module 1 cannot use."""
        secret = value.get_secret_value()

        if len(secret) < 32:
            raise ValueError(
                "agent_engine_service_key must contain at least 32 characters."
            )

        if secret != secret.strip():
            raise ValueError(
                "agent_engine_service_key must not contain "
                "leading or trailing whitespace."
            )

        return value

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
