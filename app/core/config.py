"""Application settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REQUIRED_RUNTIME_SETTINGS = (
    "VERTEX_AI_PROJECT_ID",
    "VERTEX_AI_LOCATION",
    "FIRESTORE_DATABASE",
    "GCS_BUCKET_NAME",
    "GEMINI_MODEL_NAME",
    "EMBEDDING_MODEL_NAME",
)


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    app_name: str = Field(default="Insurance GenAI Agent API", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    environment: str = Field(default="local", alias="ENVIRONMENT")

    vertex_ai_project_id: str | None = Field(default=None, alias="VERTEX_AI_PROJECT_ID")
    vertex_ai_location: str | None = Field(default=None, alias="VERTEX_AI_LOCATION")
    firestore_database: str | None = Field(default=None, alias="FIRESTORE_DATABASE")
    gcs_bucket_name: str | None = Field(default=None, alias="GCS_BUCKET_NAME")
    gemini_model_name: str | None = Field(default=None, alias="GEMINI_MODEL_NAME")
    embedding_model_name: str | None = Field(default=None, alias="EMBEDDING_MODEL_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def missing_required_settings(self) -> list[str]:
        """Return missing runtime settings required for readiness."""
        missing: list[str] = []
        if not self.vertex_ai_project_id:
            missing.append("VERTEX_AI_PROJECT_ID")
        if not self.vertex_ai_location:
            missing.append("VERTEX_AI_LOCATION")
        if not self.firestore_database:
            missing.append("FIRESTORE_DATABASE")
        if not self.gcs_bucket_name:
            missing.append("GCS_BUCKET_NAME")
        if not self.gemini_model_name:
            missing.append("GEMINI_MODEL_NAME")
        if not self.embedding_model_name:
            missing.append("EMBEDDING_MODEL_NAME")
        return missing

    @property
    def is_ready(self) -> bool:
        """Return True when required runtime settings are present."""
        return not self.missing_required_settings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
