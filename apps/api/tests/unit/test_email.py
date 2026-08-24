import smtplib
from collections.abc import Iterator
from contextlib import contextmanager
from email.message import EmailMessage

from pydantic import SecretStr

from utag_api.config import Settings
from utag_api.services import email as email_service


def email_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "smtp_host": "smtp.example.edu.gh",
        "smtp_username": "portal@example.edu.gh",
        "smtp_password": SecretStr("application-password"),
        "smtp_from_email": "no-reply@utag.ug.edu.gh",
        "smtp_from_name": "UTAG UG Portal",
        "public_web_url": "https://utag.ug.edu.gh",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_notification_template_is_branded_multipart_and_sanitized() -> None:
    message = email_service.notification_message(
        user_name="Prof. Ama Mensah",
        recipient_email="ama@ug.edu.gh",
        category="secretariat",
        priority="urgent",
        title="Council update\nAugust",
        body_html=(
            "<p>Please review the <strong>academic update</strong>.</p>"
            "<script>alert('unsafe')</script>"
        ),
        deep_link="/dashboard/notifications",
        settings=email_settings(),
    )

    assert message.is_multipart()
    assert str(message["From"]) == "UTAG UG Portal <no-reply@utag.ug.edu.gh>"
    assert str(message["Subject"]) == "Council update August | UTAG UG"
    assert message["Precedence"] == "bulk"
    plain = message.get_body(preferencelist=("plain",))
    html = message.get_body(preferencelist=("html",))
    assert plain is not None
    assert html is not None
    assert "academic update" in plain.get_content()
    html_content = html.get_content()
    assert "Secretariat update" in html_content
    assert "https://utag.ug.edu.gh/dashboard/notifications" in html_content
    assert "script" not in html_content.casefold()


def test_password_reset_template_keeps_security_guidance_and_plain_fallback() -> None:
    message = email_service.password_reset_message(
        user_name="Dr. Kojo Asare",
        recipient_email="kojo@ug.edu.gh",
        reset_url="https://utag.ug.edu.gh/reset-password?token=secure-token",
        settings=email_settings(),
    )

    assert message["Auto-Submitted"] == "auto-generated"
    assert message["X-Auto-Response-Suppress"] == "All"
    plain = message.get_body(preferencelist=("plain",))
    assert plain is not None
    assert "within 30 minutes" in plain.get_content()
    assert "secure-token" in plain.get_content()


def test_rich_text_tables_have_readable_plain_text_labels() -> None:
    plain = email_service.html_to_text(
        "<table><tbody><tr><th>Date</th><td>10 September 2026</td></tr>"
        "<tr><th>Venue</th><td>Great Hall</td></tr></tbody></table>"
    )

    assert plain == "Date: 10 September 2026\n\nVenue: Great Hall"


def test_starttls_transport_authenticates_and_sends(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, host: str, port: int, *, timeout: int) -> None:
            calls.append(f"connect:{host}:{port}:{timeout}")

        def ehlo(self) -> None:
            calls.append("ehlo")

        def starttls(self, *, context: object) -> None:
            assert context is not None
            calls.append("starttls")

        def login(self, username: str, password: str) -> None:
            calls.append(f"login:{username}:{password}")

        def send_message(self, message: EmailMessage) -> None:
            calls.append(f"send:{message['To']}")

        def quit(self) -> None:
            calls.append("quit")

        def close(self) -> None:
            calls.append("close")

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    settings = email_settings(smtp_security="starttls")
    message = email_service.invitation_message(
        user_name="Prof. Akua Owusu",
        recipient_email="akua@ug.edu.gh",
        invitation_url="https://utag.ug.edu.gh/accept-invitation?token=secure-token",
        settings=settings,
    )

    email_service.send_message(message, settings)

    assert calls == [
        "connect:smtp.example.edu.gh:587:30",
        "ehlo",
        "starttls",
        "ehlo",
        "login:portal@example.edu.gh:application-password",
        "send:akua@ug.edu.gh",
        "quit",
    ]


def test_bulk_delivery_reports_failed_message_indexes(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    class FakeClient:
        calls = 0

        def send_message(self, message: EmailMessage) -> None:
            del message
            self.calls += 1
            if self.calls == 2:
                raise smtplib.SMTPRecipientsRefused({"rejected@ug.edu.gh": (550, b"rejected")})

    client = FakeClient()

    @contextmanager
    def fake_client(settings: Settings) -> Iterator[FakeClient]:
        del settings
        yield client

    monkeypatch.setattr(email_service, "smtp_client", fake_client)
    settings = email_settings(email_bulk_batch_size=5)
    messages = [EmailMessage(), EmailMessage(), EmailMessage()]

    result = email_service.send_messages(messages, settings)

    assert result.sent == 2
    assert result.failed == 1
    assert result.failed_indexes == (1,)
    assert result.errors[0].startswith("SMTPRecipientsRefused:")
