from functools import lru_cache

from pydantic import SecretStr
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


@lru_cache
def get_settings() -> Settings:
    """Return cached application configuration."""
    return Settings()
