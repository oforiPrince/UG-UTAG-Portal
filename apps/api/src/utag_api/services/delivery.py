from utag_api.config import Settings, get_settings
from utag_api.errors import ApiError


def email_delivery_enabled(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    # Host alone is not enough — require credentials so a placeholder SMTP_HOST
    # in production config does not pretend mail can be sent.
    if not cfg.smtp_host:
        return False
    username = (cfg.smtp_username or "").strip()
    password = cfg.smtp_password.get_secret_value().strip() if cfg.smtp_password else ""
    return bool(username and password)


def sms_delivery_enabled(settings: Settings | None = None) -> bool:
    # Reserved for a future SMS provider. Always off until configured.
    _ = settings or get_settings()
    return False


def delivery_available(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    return email_delivery_enabled(cfg) or sms_delivery_enabled(cfg)


def public_capabilities(settings: Settings | None = None) -> dict[str, bool]:
    cfg = settings or get_settings()
    return {
        "email_delivery": email_delivery_enabled(cfg),
        "sms_delivery": sms_delivery_enabled(cfg),
    }


def require_email_delivery() -> None:
    if not email_delivery_enabled():
        raise ApiError(
            503,
            "email_delivery_disabled",
            "Email delivery is not configured. Configure SMTP before using this action.",
        )
