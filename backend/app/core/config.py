"""Application settings loaded from environment variables / .env files."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "change-me-generate-a-random-48-byte-secret"


class Settings(BaseSettings):
    """Runtime configuration.

    Every value can be overridden with an ``HCCP_`` prefixed environment
    variable, e.g. ``HCCP_PROVIDER=aws`` or ``HCCP_LOG_LEVEL=DEBUG``.
    """

    model_config = SettingsConfigDict(
        env_prefix="HCCP_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Application ------------------------------------------------------
    app_name: str = "Hybrid Cloud Control Plane"
    version: str = "1.0.0"
    environment: Literal["local", "dev", "prod"] = "local"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # ---- Security ---------------------------------------------------------
    secret_key: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "hybrid-cloud-control-plane"
    jwt_audience: str = "hybrid-cloud-dashboard"
    access_token_ttl_minutes: int = Field(default=60, ge=5, le=1440)
    refresh_token_ttl_days: int = Field(default=7, ge=1, le=30)
    login_max_attempts: int = Field(default=5, ge=3, le=20)
    login_lockout_seconds: int = Field(default=300, ge=30, le=3600)
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
    ]

    # ---- Cloud provider ---------------------------------------------------
    provider: Literal["mock", "aws"] = "mock"
    aws_region: str = "ap-south-1"
    aws_profile: str | None = None

    # ---- Behaviour --------------------------------------------------------
    seed_demo_data: bool = True
    drift_interval_seconds: int = Field(default=0, ge=0, le=86400)
    demo_admin_password: str = "Admin#2026"
    demo_operator_password: str = "Operator#2026"
    demo_approver_password: str = "Approver#2026"
    demo_viewer_password: str = "Viewer#2026"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma separated string as well as a JSON list."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        level = value.upper()
        if level not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return level

    @model_validator(mode="after")
    def _enforce_production_hardening(self) -> Settings:
        if self.environment == "prod":
            if self.secret_key == INSECURE_DEFAULT_SECRET or len(self.secret_key) < 32:
                raise ValueError(
                    "HCCP_SECRET_KEY must be set to a strong value (>=32 chars) in prod"
                )
            if self.seed_demo_data:
                raise ValueError("HCCP_SEED_DEMO_DATA must be false in prod")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"

    def demo_password(self, role: str) -> str:
        return {
            "admin": self.demo_admin_password,
            "operator": self.demo_operator_password,
            "approver": self.demo_approver_password,
            "viewer": self.demo_viewer_password,
        }[role]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor (also used as a FastAPI dependency)."""
    return Settings()


def generate_secret_key() -> str:
    """Helper for operators rotating the signing key."""
    return secrets.token_urlsafe(48)
