"""Runtime configuration loaded from environment variables."""

from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)

LlmProviderMode = Literal["fake", "openai_compatible", "openrouter"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    jwt_secret: str = Field(validation_alias="JWT_SECRET")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        validation_alias="CORS_ORIGINS"
    )
    cookie_secure: bool = Field(validation_alias="COOKIE_SECURE")
    cookie_path: str = Field(validation_alias="COOKIE_PATH")
    llm_provider: LlmProviderMode = Field(
        default="fake",
        validation_alias="LLM_PROVIDER",
    )
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default=None, validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(
        default=60.0,
        validation_alias="LLM_TIMEOUT_SECONDS",
    )
    log_json: bool = Field(default=False, validation_alias="LOG_JSON")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("cookie_secure", mode="before")
    @classmethod
    def parse_cookie_secure(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower() == "true"
        return value

    @field_validator("log_json", mode="before")
    @classmethod
    def parse_log_json(cls, value: object) -> object:
        if isinstance(value, str):
            return value.lower() == "true"
        return value

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in valid_levels:
            msg = f"LOG_LEVEL must be one of {sorted(valid_levels)}"
            raise ValueError(msg)
        return normalized

    @property
    def async_database_url(self) -> str:
        return normalize_runtime_database_url(self.database_url)


def load_settings() -> Settings:
    """Load settings from environment variables and optional `.env` file."""
    return Settings()  # ty: ignore[missing-argument]
