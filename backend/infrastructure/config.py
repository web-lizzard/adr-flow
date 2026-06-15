"""Runtime configuration loaded from environment variables."""

from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from infrastructure.adapters.persistence.database_url import (
    normalize_runtime_database_url,
)


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


def load_settings() -> Settings:
    """Load settings from environment variables and optional `.env` file."""
    return Settings()  # ty: ignore[missing-argument]
