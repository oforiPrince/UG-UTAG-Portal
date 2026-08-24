import pytest
from pydantic import SecretStr, ValidationError

from utag_api.config import Settings


def production_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "database_url": "postgresql+psycopg://utag:database-secret@postgres:5432/utag_portal",
        "celery_broker_url": "amqp://utag:broker-secret@rabbitmq:5672/utag",
        "app_secret_key": "session-secret-with-more-than-32-characters",
        "field_encryption_key_version": "v1",
        "field_encryption_keys": {"v1": "field-secret-with-more-than-32-characters"},
        "public_web_url": "https://portal.utag-ug.org",
        "allowed_origins": ["https://portal.utag-ug.org"],
        "allowed_hosts": ["portal.utag-ug.org", "api"],
        "trusted_proxy_cidrs": ["172.16.0.0/12"],
        "session_cookie_secure": True,
        "s3_secret_key": "object-storage-secret",
        "s3_server_side_encryption": "AES256",
        "malware_scan_required": True,
        "clamav_host": "clamav",
        "smtp_host": "smtp.example.org",
        "metrics_enabled": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_safe_production_configuration_is_accepted() -> None:
    settings = production_settings()

    assert settings.is_production is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("app_secret_key", "replace-with-at-least-32-random-characters"),
        (
            "database_url",
            "postgresql+psycopg://utag:change-me@postgres:5432/utag_portal",
        ),
        ("celery_broker_url", "amqp://utag:change-me@rabbitmq:5672/utag"),
        ("s3_secret_key", "replace-me"),
    ],
)
def test_production_configuration_rejects_placeholder_credentials(
    field: str, value: str
) -> None:
    with pytest.raises(ValidationError, match="placeholder credentials"):
        production_settings(**{field: value})


def test_production_configuration_requires_public_origin_alignment() -> None:
    with pytest.raises(ValidationError, match="PUBLIC_WEB_URL origin"):
        production_settings(allowed_origins=["https://www.utag-ug.org"])


def test_smtp_sender_and_security_configuration_are_normalized() -> None:
    settings = Settings(
        _env_file=None,
        smtp_from_email="no-reply@utag.ug.edu.gh",
        smtp_from_name="UTAG UG Portal",
        smtp_security="tls",
    )

    assert settings.smtp_sender == "UTAG UG Portal <no-reply@utag.ug.edu.gh>"
    assert settings.effective_smtp_security == "tls"

    legacy = Settings(_env_file=None, smtp_security="tls", smtp_use_tls=True)
    assert legacy.effective_smtp_security == "starttls"


def test_smtp_credentials_must_be_configured_together() -> None:
    with pytest.raises(ValidationError, match="configured together"):
        Settings(_env_file=None, smtp_username="portal@ug.edu.gh")


def test_authenticated_smtp_cannot_send_credentials_without_tls() -> None:
    with pytest.raises(ValidationError, match="requires STARTTLS or implicit TLS"):
        Settings(
            _env_file=None,
            smtp_username="portal@ug.edu.gh",
            smtp_password=SecretStr("application-password"),
            smtp_security="none",
        )
