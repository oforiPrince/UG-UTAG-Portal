from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "UG UTAG API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = "sqlite+aiosqlite:///./utag-dev.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    app_secret_key: SecretStr = SecretStr("development-only-change-this-key")
    session_cookie_name: str = "utag_session"
    csrf_cookie_name: str = "utag_csrf"
    session_ttl_seconds: int = Field(default=43_200, ge=900, le=2_592_000)
    session_cookie_secure: bool = False
    session_cookie_domain: str | None = None
    allowed_origins: list[str] = ["http://localhost:3000"]
    allowed_hosts: list[str] = ["localhost", "127.0.0.1", "testserver"]

    public_web_url: str = "http://localhost:3000"
    media_bucket: str = "utag-media"
    s3_endpoint_url: str | None = None
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str = "us-east-1"
    upload_max_bytes: int = Field(default=25_000_000, ge=1_000_000, le=250_000_000)
    presigned_url_ttl_seconds: int = Field(default=900, ge=60, le=3_600)
    field_encryption_key_version: str = "v1"
    realtime_heartbeat_seconds: int = Field(default=25, ge=10, le=60)
    legacy_database_url: str | None = None
    legacy_media_root: str | None = None
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65_535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str = "UG UTAG Portal <no-reply@utag-ug.org>"
    smtp_use_tls: bool = True
    contact_recipient_email: str = "utagoffice@ug.edu.gh"
    clamav_host: str | None = None
    clamav_port: int = Field(default=3310, ge=1, le=65_535)
    malware_scan_required: bool = False
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: SecretStr | None = None
    demo_data_password: SecretStr | None = None
    metrics_enabled: bool = True
    metrics_bearer_token: SecretStr | None = None

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.database_url.startswith("sqlite"):
            raise ValueError("Production must use PostgreSQL, not SQLite")
        if self.app_secret_key.get_secret_value() == "development-only-change-this-key":
            raise ValueError("Production APP_SECRET_KEY must not use the development default")
        if "*" in self.allowed_origins or "*" in self.allowed_hosts:
            raise ValueError("Production origins and hosts must be explicit")
        if not self.session_cookie_secure:
            raise ValueError("Production session cookies must be secure")
        if not self.malware_scan_required or not self.clamav_host:
            raise ValueError("Production uploads require a configured malware scanner")
        if self.demo_data_password:
            raise ValueError("Production must not configure DEMO_DATA_PASSWORD")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
