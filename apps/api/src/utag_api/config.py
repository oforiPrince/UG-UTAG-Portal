from functools import lru_cache
from ipaddress import ip_network
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_MARKERS = ("change-me", "replace-me", "replace-with", "development-only")


def contains_placeholder(value: str) -> bool:
    normalized = value.casefold()
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


class Settings(BaseSettings):
    """Validated application configuration loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "UG UTAG API"
    environment: Literal["development", "test", "staging", "production"] = "development"
    api_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = "postgresql+psycopg://utag:change-me@127.0.0.1:5433/utag_portal"
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
    trusted_proxy_cidrs: list[str] = ["127.0.0.1/32", "::1/128"]

    public_web_url: str = "http://localhost:3000"
    media_bucket: str = "utag-media"
    s3_endpoint_url: str | None = None
    s3_access_key: SecretStr | None = None
    s3_secret_key: SecretStr | None = None
    s3_region: str = "us-east-1"
    s3_server_side_encryption: Literal["AES256", "aws:kms"] | None = None
    s3_kms_key_id: str | None = None
    upload_max_bytes: int = Field(default=25_000_000, ge=1_000_000, le=250_000_000)
    presigned_url_ttl_seconds: int = Field(default=900, ge=60, le=3_600)
    field_encryption_key_version: str = "v1"
    field_encryption_keys: dict[str, SecretStr] = Field(default_factory=dict)
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

    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/api/v1/integrations/google-drive/callback"
    )

    @field_validator("app_secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET_KEY must contain at least 32 characters")
        return value

    @field_validator("trusted_proxy_cidrs")
    @classmethod
    def validate_proxy_networks(cls, values: list[str]) -> list[str]:
        for value in values:
            ip_network(value)
        return values

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if any(
            len(secret.get_secret_value()) < 32 for secret in self.field_encryption_keys.values()
        ):
            raise ValueError("Every field encryption key must contain at least 32 characters")
        has_google_client_id = bool(
            self.google_oauth_client_id and self.google_oauth_client_id.strip()
        )
        has_google_client_secret = bool(
            self.google_oauth_client_secret
            and self.google_oauth_client_secret.get_secret_value().strip()
        )
        if has_google_client_id != has_google_client_secret:
            raise ValueError(
                "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be configured together"
            )
        if has_google_client_id:
            redirect_url = urlsplit(self.google_oauth_redirect_uri)
            if redirect_url.scheme not in {"http", "https"} or not redirect_url.hostname:
                raise ValueError("GOOGLE_OAUTH_REDIRECT_URI must be an absolute HTTP(S) URL")
            if self.field_encryption_key_version not in self.field_encryption_keys:
                raise ValueError(
                    "Google Drive OAuth token storage requires the active field encryption key"
                )
        if self.environment != "production":
            return self
        if self.database_url.startswith("sqlite"):
            raise ValueError("Production must use PostgreSQL, not SQLite")
        placeholder_values = {
            "APP_SECRET_KEY": self.app_secret_key.get_secret_value(),
            "DATABASE_URL": self.database_url,
            "CELERY_BROKER_URL": self.celery_broker_url,
            **{
                f"FIELD_ENCRYPTION_KEYS[{version}]": secret.get_secret_value()
                for version, secret in self.field_encryption_keys.items()
            },
        }
        for name, secret in (
            ("S3_SECRET_KEY", self.s3_secret_key),
            ("SMTP_PASSWORD", self.smtp_password),
            ("BOOTSTRAP_ADMIN_PASSWORD", self.bootstrap_admin_password),
            ("METRICS_BEARER_TOKEN", self.metrics_bearer_token),
            ("GOOGLE_OAUTH_CLIENT_SECRET", self.google_oauth_client_secret),
        ):
            if secret is not None:
                placeholder_values[name] = secret.get_secret_value()
        unsafe_names = sorted(
            name for name, value in placeholder_values.items() if contains_placeholder(value)
        )
        if unsafe_names:
            raise ValueError(
                "Production configuration contains placeholder credentials: "
                + ", ".join(unsafe_names)
            )
        if "*" in self.allowed_origins or "*" in self.allowed_hosts:
            raise ValueError("Production origins and hosts must be explicit")
        public_url = urlsplit(self.public_web_url)
        if public_url.scheme != "https" or not public_url.hostname:
            raise ValueError("Production PUBLIC_WEB_URL must be an absolute HTTPS URL")
        if public_url.hostname not in self.allowed_hosts:
            raise ValueError("Production ALLOWED_HOSTS must include the PUBLIC_WEB_URL host")
        public_origin = f"{public_url.scheme}://{public_url.netloc}"
        if public_origin not in self.allowed_origins:
            raise ValueError("Production ALLOWED_ORIGINS must include the PUBLIC_WEB_URL origin")
        if not self.session_cookie_secure:
            raise ValueError("Production session cookies must be secure")
        if not self.trusted_proxy_cidrs:
            raise ValueError("Production must configure at least one trusted proxy network")
        if self.field_encryption_key_version not in self.field_encryption_keys:
            raise ValueError(
                "Production FIELD_ENCRYPTION_KEYS must contain FIELD_ENCRYPTION_KEY_VERSION"
            )
        if not self.malware_scan_required or not self.clamav_host:
            raise ValueError("Production uploads require a configured malware scanner")
        if not self.smtp_host:
            raise ValueError("Production account and contact workflows require SMTP")
        if not self.s3_server_side_encryption:
            raise ValueError("Production object storage must enable server-side encryption")
        if self.s3_server_side_encryption == "aws:kms" and not self.s3_kms_key_id:
            raise ValueError("S3_KMS_KEY_ID is required when using aws:kms encryption")
        if self.metrics_enabled and not self.metrics_bearer_token:
            raise ValueError("Production metrics require a bearer token")
        if self.demo_data_password:
            raise ValueError("Production must not configure DEMO_DATA_PASSWORD")
        if has_google_client_id and urlsplit(self.google_oauth_redirect_uri).scheme != "https":
            raise ValueError("Production GOOGLE_OAUTH_REDIRECT_URI must use HTTPS")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def google_drive_configured(self) -> bool:
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_id.strip()
            and self.google_oauth_client_secret
            and self.google_oauth_client_secret.get_secret_value().strip()
            and self.field_encryption_key_version in self.field_encryption_keys
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
