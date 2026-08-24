# Review-pack HTML intentionally keeps long CSS and markup lines together.
# ruff: noqa: E501

import argparse
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from pathlib import Path

from utag_api.config import Settings
from utag_api.services.email import (
    contact_message,
    invitation_message,
    notification_message,
    password_reset_message,
)


@dataclass(frozen=True, slots=True)
class Sample:
    filename: str
    label: str
    description: str
    message: EmailMessage


def sample_settings() -> Settings:
    return Settings(
        _env_file=None,
        public_web_url="https://utag.ug.edu.gh",
        smtp_from_email="no-reply@utag.ug.edu.gh",
        smtp_from_name="UTAG UG Portal",
        smtp_reply_to_email="utagoffice@ug.edu.gh",
    )


def build_samples() -> list[Sample]:
    settings = sample_settings()
    recipient = "ama.mensah@ug.edu.gh"
    member_name = "Prof. Ama Mensah"
    return [
        Sample(
            filename="01-account-invitation",
            label="Account invitation",
            description="New-member activation and portal access.",
            message=invitation_message(
                user_name=member_name,
                recipient_email=recipient,
                invitation_url=(
                    "https://utag.ug.edu.gh/accept-invitation?token=sample-review-token"
                ),
                settings=settings,
            ),
        ),
        Sample(
            filename="02-password-reset",
            label="Password reset",
            description="Time-limited account-security message.",
            message=password_reset_message(
                user_name=member_name,
                recipient_email=recipient,
                reset_url="https://utag.ug.edu.gh/reset-password#token=sample-review-token",
                settings=settings,
            ),
        ),
        Sample(
            filename="03-official-announcement",
            label="Official announcement",
            description="High-priority, member-wide communication.",
            message=notification_message(
                user_name=member_name,
                recipient_email=recipient,
                category="announcement",
                priority="high",
                title="Notice of UTAG UG General Meeting",
                body_html=(
                    "<p>Members are respectfully invited to the next General Meeting of "
                    "UTAG UG.</p><table><tbody>"
                    "<tr><th scope='row'>Date</th><td>Thursday, 10 September 2026</td></tr>"
                    "<tr><th scope='row'>Time</th><td>2:00 p.m.</td></tr>"
                    "<tr><th scope='row'>Venue</th><td>Great Hall Committee Room 1</td></tr>"
                    "</tbody></table><p>The agenda and supporting documents are available "
                    "in the portal. Kindly make every effort to attend.</p>"
                ),
                deep_link="/dashboard/announcements",
                settings=settings,
            ),
        ),
        Sample(
            filename="04-event-notification",
            label="Event notification",
            description="Academic event notice with portal details.",
            message=notification_message(
                user_name=member_name,
                recipient_email=recipient,
                category="event",
                priority="normal",
                title="Academic Freedom Public Lecture",
                body_html=(
                    "<p>The UTAG UG Academic Affairs Committee invites you to a public lecture "
                    "on <strong>Academic Freedom and the Future of Higher Education</strong>.</p>"
                    "<ul><li>Tuesday, 22 September 2026</li><li>3:00 p.m.</li>"
                    "<li>ISSER Conference Facility</li></ul>"
                    "<p>Registration and the full programme are available through the portal.</p>"
                ),
                deep_link="/dashboard/events",
                settings=settings,
            ),
        ),
        Sample(
            filename="05-administrative-notice",
            label="Administrative notice",
            description="Records and membership administration.",
            message=notification_message(
                user_name=member_name,
                recipient_email=recipient,
                category="administrative",
                priority="normal",
                title="Membership Records Verification",
                body_html=(
                    "<p>As part of the annual membership audit, please review your staff ID, "
                    "academic rank, department and contact details in the portal.</p>"
                    "<p>Kindly submit any corrections to the Secretariat by "
                    "<strong>30 September 2026</strong>.</p>"
                ),
                deep_link="/dashboard/profile",
                settings=settings,
            ),
        ),
        Sample(
            filename="06-secretariat-update",
            label="Secretariat update",
            description="Formal update issued by the UTAG UG Secretariat.",
            message=notification_message(
                user_name=member_name,
                recipient_email=recipient,
                category="secretariat",
                priority="normal",
                title="Update from the UTAG UG Secretariat",
                body_html=(
                    "<p>The Secretariat is pleased to inform members that the approved minutes "
                    "of the August General Meeting are now available in the document library.</p>"
                    "<p>Members may also submit matters for the next Executive Committee meeting "
                    "through the Secretariat office.</p>"
                ),
                deep_link="/dashboard/documents",
                settings=settings,
            ),
        ),
        Sample(
            filename="07-member-communication",
            label="Member communication",
            description="Selected-member or committee-specific notice.",
            message=notification_message(
                user_name=member_name,
                recipient_email=recipient,
                category="direct",
                priority="normal",
                title="Committee Assignment Confirmation",
                body_html=(
                    "<p>Your appointment to the Welfare Committee has been confirmed for the "
                    "2026/2027 academic year.</p><p>The Committee Secretary will share the first "
                    "meeting date and relevant working documents through the portal.</p>"
                ),
                deep_link="/dashboard/notifications",
                settings=settings,
            ),
        ),
        Sample(
            filename="08-contact-form-enquiry",
            label="Contact-form enquiry",
            description="Message delivered internally to the Secretariat.",
            message=contact_message(
                recipient_email="utagoffice@ug.edu.gh",
                sender_name="Dr. Kwame Asare",
                sender_email="kwame.asare@ug.edu.gh",
                subject="Membership status enquiry",
                message_text=(
                    "Good afternoon. Please confirm whether my membership records have been "
                    "updated following my transfer to the School of Engineering.\n\nThank you."
                ),
                settings=settings,
            ),
        ),
    ]


def render_index(samples: list[Sample]) -> str:
    cards = "\n".join(
        f"""
        <article class="sample" id="{escape(sample.filename)}">
          <header>
            <div><span aria-hidden="true">{escape(sample.filename[:2])}</span><h2>{escape(sample.label)}</h2></div>
            <p>{escape(sample.description)}</p>
            <nav aria-label="{escape(sample.label)} sample files"><a href="{escape(sample.filename)}.html">Open HTML</a><a href="{escape(sample.filename)}.eml">Download .eml</a></nav>
          </header>
          <img class="preview" src="{escape(sample.filename)}.png" alt="Rendered preview of the {escape(sample.label)} email">
        </article>"""
        for sample in samples
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>UTAG UG Portal email samples</title>
  <style>
    *{{box-sizing:border-box}} body{{margin:0;background:#eef2f6;color:#172b45;font:15px/1.6 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
    main{{width:min(1120px,calc(100% - 32px));margin:0 auto;padding:56px 0 80px}} .intro{{max-width:760px;margin-bottom:38px}}
    .eyebrow{{color:#1f5f99;font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase}} h1{{margin:8px 0 12px;font-size:clamp(32px,5vw,54px);line-height:1.08;letter-spacing:-.04em}} .intro p{{color:#5f6f82;font-size:17px}}
    .grid{{display:grid;gap:32px}} .sample{{overflow:hidden;border:1px solid #dbe3ec;border-radius:18px;background:#fff;box-shadow:0 14px 40px rgba(23,43,69,.08)}}
    .sample header{{display:grid;grid-template-columns:1fr auto;gap:8px 24px;padding:24px 28px;border-bottom:1px solid #dbe3ec}} .sample header div{{display:flex;align-items:center;gap:12px}}
    .sample header span{{display:grid;width:34px;height:34px;place-items:center;border-radius:50%;background:#172b45;color:#fff;font-size:12px;font-weight:800}} h2{{margin:0;font-size:20px}} .sample header p{{grid-column:1;margin:0;color:#5f6f82}}
    nav{{grid-column:2;grid-row:1/3;display:flex;align-items:center;gap:9px}} nav a{{border:1px solid #dbe3ec;border-radius:8px;padding:8px 12px;color:#1f5f99;font-size:12px;font-weight:750;text-decoration:none}} nav a:hover{{background:#f6f8fb}} nav a:focus-visible{{outline:3px solid rgba(31,95,153,.3);outline-offset:2px}}
    .preview{{display:block;width:min(100%,800px);height:auto;margin:0 auto;background:#eef2f6}} @media(max-width:700px){{.sample header{{grid-template-columns:1fr}}nav{{grid-column:1;grid-row:auto}}}}
  </style>
</head>
<body><main><section class="intro"><div class="eyebrow">Communications review pack</div><h1>UTAG UG Portal email samples</h1><p>These previews are generated directly from the production templates. Names, dates, links and tokens are fictional review data.</p></section><section class="grid">{cards}</section></main></body>
</html>"""


def generate(output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=True)
    samples = build_samples()
    for sample in samples:
        html_part = sample.message.get_body(preferencelist=("html",))
        if html_part is None:
            raise RuntimeError(f"HTML body missing for {sample.label}")
        clean_html = "\n".join(
            line.rstrip() for line in html_part.get_content().splitlines()
        )
        (output_directory / f"{sample.filename}.html").write_text(
            f"{clean_html}\n", encoding="utf-8"
        )
        (output_directory / f"{sample.filename}.eml").write_bytes(sample.message.as_bytes())
    (output_directory / "index.html").write_text(render_index(samples), encoding="utf-8")
    print(f"Generated {len(samples)} email samples in {output_directory.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate review samples for portal emails")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/email-samples"),
        help="Directory for HTML and EML samples",
    )
    args = parser.parse_args()
    generate(args.output)


if __name__ == "__main__":
    main()
