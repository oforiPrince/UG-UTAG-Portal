# Email markup intentionally keeps long inline-style lines for broad client support.
# ruff: noqa: E501

import re
import smtplib
import ssl
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr
from html import escape
from html.parser import HTMLParser
from time import sleep
from typing import ClassVar

from utag_api.config import Settings, get_settings
from utag_api.services.content import sanitize_html


@dataclass(frozen=True, slots=True)
class EmailTemplate:
    subject: str
    preheader: str
    eyebrow: str
    title: str
    greeting: str
    body_html: str
    body_text: str
    action_label: str | None = None
    action_url: str | None = None
    callout_title: str | None = None
    callout_text: str | None = None
    priority: str = "normal"
    closing: str = "UTAG UG Secretariat"


@dataclass(frozen=True, slots=True)
class BulkEmailResult:
    sent: int
    failed: int
    errors: tuple[str, ...]
    failed_indexes: tuple[int, ...] = ()


class _PlainTextParser(HTMLParser):
    block_tags: ClassVar[set[str]] = {
        "blockquote",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "ol",
        "p",
        "table",
        "tr",
        "ul",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "li":
            self.parts.append("\n• ")
        elif tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "th":
            self.parts.append(": ")
        elif tag == "td" or tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _PlainTextParser()
    parser.feed(sanitize_html(value))
    text = "".join(parser.parts).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def portal_url(path: str, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    base = cfg.public_web_url.rstrip("/")
    safe_path = path if path.startswith("/") and not path.startswith("//") else "/dashboard"
    return f"{base}{safe_path}"


def _priority_colour(priority: str) -> str:
    return {
        "urgent": "#b42318",
        "high": "#b54708",
        "low": "#2d74b5",
    }.get(priority, "#c79a2b")


def _safe_header(value: str, fallback: str) -> str:
    cleaned = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return cleaned or fallback


def _render_html(
    template: EmailTemplate,
    *,
    recipient_email: str,
    settings: Settings,
) -> str:
    action = ""
    if template.action_label and template.action_url:
        action = f"""
        <table role="presentation" cellpadding="0" cellspacing="0" style="margin:30px 0 8px">
          <tr><td style="border-radius:8px;background:#1f5f99">
            <a href="{escape(template.action_url, quote=True)}" style="display:inline-block;padding:14px 22px;color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;line-height:20px">{escape(template.action_label)}</a>
          </td></tr>
        </table>"""
    callout = ""
    if template.callout_text:
        callout = f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:26px 0;background:#f6f8fb;border:1px solid #dbe3ec;border-radius:10px">
          <tr><td style="padding:18px 20px">
            {f'<p style="margin:0 0 5px;color:#172b45;font-size:13px;font-weight:700">{escape(template.callout_title)}</p>' if template.callout_title else ""}
            <p style="margin:0;color:#5f6f82;font-size:13px;line-height:20px">{escape(template.callout_text)}</p>
          </td></tr>
        </table>"""
    logo_url = f"{settings.public_web_url.rstrip('/')}/brand/logo-blue.png"
    accent = _priority_colour(template.priority)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <title>{escape(template.subject)}</title>
  <style>
    body,table,td,a{{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%}}
    table,td{{mso-table-lspace:0;mso-table-rspace:0}}
    img{{-ms-interpolation-mode:bicubic;border:0;display:block;height:auto;line-height:100%;outline:none;text-decoration:none}}
    .mail-content p{{margin:0 0 16px}} .mail-content h2,.mail-content h3,.mail-content h4{{color:#172b45;line-height:1.3;margin:24px 0 10px}}
    .mail-content a{{color:#1f5f99}} .mail-content li{{margin:6px 0}} .mail-content blockquote{{border-left:3px solid #c79a2b;margin:20px 0;padding:4px 0 4px 16px;color:#5f6f82}}
    .mail-content table{{border-collapse:collapse;margin:20px 0;width:100%}} .mail-content th,.mail-content td{{border:1px solid #dbe3ec;padding:10px 12px;text-align:left;vertical-align:top}}
    .mail-content th{{background:#f6f8fb;color:#172b45;font-size:13px;font-weight:700;width:28%}}
    @media only screen and (max-width:620px){{.mail-shell{{width:100%!important}}.mail-pad{{padding-left:22px!important;padding-right:22px!important}}}}
  </style>
</head>
<body style="margin:0;padding:0;background:#eef2f6;color:#172b45;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{escape(template.preheader)}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#eef2f6">
    <tr><td align="center" style="padding:30px 12px">
      <table role="presentation" width="600" class="mail-shell" cellpadding="0" cellspacing="0" style="width:600px;max-width:600px;background:#ffffff;border:1px solid #dbe3ec;border-radius:14px;overflow:hidden;box-shadow:0 8px 28px rgba(23,43,69,.08)">
        <tr><td style="height:5px;background:{accent};font-size:0;line-height:0">&nbsp;</td></tr>
        <tr><td class="mail-pad" style="padding:28px 42px 24px;border-bottom:1px solid #dbe3ec">
          <img src="{escape(logo_url, quote=True)}" width="255" alt="University Teachers Association of Ghana, University of Ghana Branch" style="width:255px;max-width:100%">
        </td></tr>
        <tr><td class="mail-pad" style="padding:38px 42px 34px">
          <p style="margin:0 0 13px;color:{accent};font-size:11px;font-weight:800;letter-spacing:1.5px;text-transform:uppercase">{escape(template.eyebrow)}</p>
          <h1 style="margin:0 0 23px;color:#172b45;font-size:29px;line-height:37px;letter-spacing:-.5px">{escape(template.title)}</h1>
          <p style="margin:0 0 17px;color:#172b45;font-size:16px;line-height:25px">{escape(template.greeting)}</p>
          <div class="mail-content" style="color:#34465b;font-size:15px;line-height:24px">{sanitize_html(template.body_html)}</div>
          {action}
          {callout}
          <p style="margin:28px 0 0;color:#34465b;font-size:14px;line-height:22px">Yours faithfully,<br><strong style="color:#172b45">{escape(template.closing)}</strong></p>
        </td></tr>
        <tr><td class="mail-pad" style="padding:24px 42px;background:#172b45;color:#dbe3ec">
          <p style="margin:0 0 8px;font-size:12px;font-weight:700;line-height:18px">{escape(settings.email_footer_address)}</p>
          <p style="margin:0;color:#b9c5d2;font-size:11px;line-height:18px">This official message was sent to {escape(recipient_email)}. Please do not share account access links. Visit <a href="{escape(settings.public_web_url, quote=True)}" style="color:#ffffff">the UTAG UG Portal</a> for current information.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def build_message(
    template: EmailTemplate,
    *,
    recipient_email: str,
    reply_to: str | None = None,
    bulk: bool = False,
    settings: Settings | None = None,
) -> EmailMessage:
    cfg = settings or get_settings()
    message = EmailMessage()
    message["Subject"] = _safe_header(template.subject, "UTAG UG Portal message")
    message["From"] = cfg.smtp_sender
    message["To"] = recipient_email
    configured_reply_to = reply_to or cfg.smtp_reply_to_email
    if configured_reply_to:
        message["Reply-To"] = configured_reply_to
    sender_address = parseaddr(cfg.smtp_from_email)[1]
    sender_domain = sender_address.rsplit("@", 1)[-1] if "@" in sender_address else None
    message["Message-ID"] = make_msgid(domain=sender_domain)
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    if bulk:
        message["Precedence"] = "bulk"

    plain_parts = [template.greeting, "", template.body_text]
    if template.action_label and template.action_url:
        plain_parts.extend(["", f"{template.action_label}: {template.action_url}"])
    if template.callout_text:
        plain_parts.extend(
            [
                "",
                f"{template.callout_title}:" if template.callout_title else "",
                template.callout_text,
            ]
        )
    plain_parts.extend(["", "Yours faithfully,", template.closing, "", cfg.email_footer_address])
    message.set_content("\n".join(plain_parts))
    message.add_alternative(
        _render_html(template, recipient_email=recipient_email, settings=cfg), subtype="html"
    )
    return message


def password_reset_message(
    *, user_name: str, recipient_email: str, reset_url: str, settings: Settings | None = None
) -> EmailMessage:
    template = EmailTemplate(
        subject="Reset your UTAG UG Portal password",
        preheader="Use this secure link within 30 minutes to reset your portal password.",
        eyebrow="Account security",
        title="Reset your portal password",
        greeting=f"Dear {user_name},",
        body_html=(
            "<p>We received a request to reset the password for your UTAG UG Portal "
            "account.</p><p>Use the secure link below within <strong>30 minutes</strong>. "
            "After your password is changed, existing sessions will no longer be valid.</p>"
        ),
        body_text=(
            "We received a request to reset the password for your UTAG UG Portal account. "
            "Use the secure link below within 30 minutes. Existing sessions will no longer "
            "be valid after the password is changed."
        ),
        action_label="Reset password",
        action_url=reset_url,
        callout_title="Did not request this?",
        callout_text=(
            "You can safely ignore this email. Your password will remain unchanged unless "
            "the secure link is used."
        ),
        priority="high",
        closing="UTAG UG Portal Administration",
    )
    return build_message(template, recipient_email=recipient_email, settings=settings)


def invitation_message(
    *, user_name: str, recipient_email: str, invitation_url: str, settings: Settings | None = None
) -> EmailMessage:
    template = EmailTemplate(
        subject="Your invitation to the UTAG UG Portal",
        preheader="Activate your UTAG UG membership account within seven days.",
        eyebrow="Membership access",
        title="Welcome to the UTAG UG Portal",
        greeting=f"Dear {user_name},",
        body_html=(
            "<p>Your membership account has been prepared for the University of Ghana branch "
            "of UTAG.</p><p>Please activate your account and choose a secure password within "
            "<strong>seven days</strong>. The portal provides access to official notices, "
            "events, documents and member services.</p>"
        ),
        body_text=(
            "Your membership account has been prepared for the University of Ghana branch "
            "of UTAG. Activate your account and choose a secure password within seven days."
        ),
        action_label="Activate account",
        action_url=invitation_url,
        callout_title="For your security",
        callout_text=(
            "This invitation is personal to you. Do not forward the email or share the "
            "activation link."
        ),
        closing="UTAG UG Portal Administration",
    )
    return build_message(template, recipient_email=recipient_email, settings=settings)


def notification_message(
    *,
    user_name: str,
    recipient_email: str,
    category: str,
    priority: str,
    title: str,
    body_html: str,
    deep_link: str | None = None,
    settings: Settings | None = None,
) -> EmailMessage:
    cfg = settings or get_settings()
    category_key = category.strip().casefold()
    labels = {
        "announcement": ("Official announcement", "Read announcement"),
        "event": ("Event notification", "View event details"),
        "administrative": ("Administrative notice", "Open portal"),
        "secretariat": ("Secretariat update", "Open portal"),
        "direct": ("Member communication", "Open notification"),
    }
    eyebrow, action_label = labels.get(category_key, ("UTAG UG notice", "Open portal"))
    action_url = portal_url(deep_link or "/dashboard/notifications", cfg)
    clean_body = sanitize_html(body_html)
    safe_title = _safe_header(title, "Official portal message")
    template = EmailTemplate(
        subject=f"{safe_title} | UTAG UG",
        preheader=html_to_text(clean_body)[:150] or "A new official message is available.",
        eyebrow=eyebrow,
        title=safe_title,
        greeting=f"Dear {user_name},",
        body_html=clean_body or "<p>A new official message is available in your portal.</p>",
        body_text=html_to_text(clean_body) or "A new official message is available in your portal.",
        action_label=action_label,
        action_url=action_url,
        priority=priority,
    )
    return build_message(template, recipient_email=recipient_email, bulk=True, settings=cfg)


def contact_message(
    *,
    recipient_email: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    message_text: str,
    settings: Settings | None = None,
) -> EmailMessage:
    safe_subject = _safe_header(subject, "New message")
    safe_message = escape(message_text).replace("\n", "<br>")
    template = EmailTemplate(
        subject=f"Portal contact: {safe_subject}",
        preheader=f"New portal enquiry from {sender_name}.",
        eyebrow="Portal enquiry",
        title=safe_subject,
        greeting="Dear Secretariat colleague,",
        body_html=(
            f"<p>A message was submitted through the UTAG UG Portal contact form.</p>"
            f"<p><strong>From:</strong> {escape(sender_name)}<br>"
            f"<strong>Email:</strong> {escape(sender_email or 'Not provided')}</p>"
            f"<blockquote>{safe_message}</blockquote>"
        ),
        body_text=(
            "A message was submitted through the UTAG UG Portal contact form.\n\n"
            f"From: {sender_name}\nEmail: {sender_email or 'Not provided'}\n\n{message_text}"
        ),
        action_label="Open administration portal",
        action_url=portal_url("/dashboard", settings),
        callout_title="Replying to the member",
        callout_text="Use Reply to respond directly to the email address supplied in the form.",
        closing="UTAG UG Portal",
    )
    return build_message(
        template,
        recipient_email=recipient_email,
        reply_to=sender_email or None,
        settings=settings,
    )


def _smtp_security(settings: Settings) -> str:
    return settings.effective_smtp_security


@contextmanager
def smtp_client(settings: Settings | None = None) -> Iterator[smtplib.SMTP]:
    cfg = settings or get_settings()
    if not cfg.smtp_host:
        raise RuntimeError("SMTP is not configured")
    if cfg.smtp_auth_required and not (cfg.smtp_username and cfg.smtp_password):
        raise RuntimeError("SMTP authentication credentials are not configured")
    security = _smtp_security(cfg)
    tls_context = ssl.create_default_context()
    if security == "tls":
        client: smtplib.SMTP = smtplib.SMTP_SSL(
            cfg.smtp_host,
            cfg.smtp_port,
            timeout=cfg.smtp_timeout_seconds,
            context=tls_context,
        )
    else:
        client = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=cfg.smtp_timeout_seconds)
    try:
        client.ehlo()
        if security == "starttls":
            client.starttls(context=tls_context)
            client.ehlo()
        if cfg.smtp_auth_required and cfg.smtp_username and cfg.smtp_password:
            client.login(cfg.smtp_username, cfg.smtp_password.get_secret_value())
        yield client
    finally:
        try:
            client.quit()
        except (OSError, smtplib.SMTPException):
            client.close()


def send_message(message: EmailMessage, settings: Settings | None = None) -> None:
    with smtp_client(settings) as client:
        client.send_message(message)


def send_messages(
    messages: Sequence[EmailMessage], settings: Settings | None = None
) -> BulkEmailResult:
    cfg = settings or get_settings()
    sent = 0
    errors: list[str] = []
    failed_indexes: list[int] = []
    batch_size = cfg.email_bulk_batch_size
    for start in range(0, len(messages), batch_size):
        batch = messages[start : start + batch_size]
        try:
            with smtp_client(cfg) as client:
                for offset, message in enumerate(batch):
                    try:
                        client.send_message(message)
                        sent += 1
                    except (OSError, smtplib.SMTPException) as exc:
                        failed_indexes.append(start + offset)
                        errors.append(f"{type(exc).__name__}: {str(exc)[:240]}")
        except (OSError, smtplib.SMTPException) as exc:
            failed_indexes.extend(range(start, start + len(batch)))
            errors.extend(f"{type(exc).__name__}: {str(exc)[:240]}" for _message in batch)
        if start + batch_size < len(messages) and cfg.email_bulk_pause_seconds:
            sleep(cfg.email_bulk_pause_seconds)
    return BulkEmailResult(
        sent=sent,
        failed=len(messages) - sent,
        errors=tuple(errors[:20]),
        failed_indexes=tuple(sorted(set(failed_indexes))),
    )
