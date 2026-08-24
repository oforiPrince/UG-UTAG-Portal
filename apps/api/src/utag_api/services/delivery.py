from utag_api.config import Settings, get_settings
from utag_api.errors import ApiError


def email_delivery_enabled(settings: Settings | None = None) -> bool:
    cfg = settings or get_settings()
    if not cfg.smtp_host or not str(cfg.smtp_host).strip():
        return False
    # UG may provide either authenticated SMTP or an IP-allowlisted relay.
    if not getattr(cfg, "smtp_auth_required", True):
        return True
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
