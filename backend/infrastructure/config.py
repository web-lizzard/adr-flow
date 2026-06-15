"""Runtime configuration loaded from environment variables."""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql://postgres:postgres@postgres:5432/adr_flow",
        validation_alias="DATABASE_URL",
    )
    jwt_secret: str = Field(
        default="dev-insecure-jwt-secret",
        validation_alias="JWT_SECRET",
    )
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias="CORS_ORIGINS",
    )
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")

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

    @property
    def async_database_url(self) -> str:
        return normalize_runtime_database_url(self.database_url)
