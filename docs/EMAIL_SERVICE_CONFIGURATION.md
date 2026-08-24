# UTAG UG Portal email service configuration

The portal is ready to use an approved UG SMTP service when the configuration is supplied. No credential belongs in this repository; production values must be stored in the deployment environment or secret manager and made available to both the API and worker services.

## Information required from UG

Record the approved values for:

| Requirement | Portal setting or owner |
| --- | --- |
| SMTP hostname and port | `SMTP_HOST`, `SMTP_PORT` |
| Sender address | `SMTP_FROM_EMAIL` (proposed `no-reply@utag.ug.edu.gh`) |
| Sender display name | `SMTP_FROM_NAME` (proposed `UTAG UG Portal`) |
| Replies, if permitted | `SMTP_REPLY_TO_EMAIL` (normally the Secretariat inbox) |
| Transport security | `SMTP_SECURITY=starttls`, `tls`, or an explicitly approved `none` relay |
| Username and app password | `SMTP_USERNAME`, `SMTP_PASSWORD` |
| IP-allowlisted relay without authentication | `SMTP_AUTH_REQUIRED=false`; leave username and password empty |
| Per-connection or time-window sending limit | `EMAIL_BULK_BATCH_SIZE`, `EMAIL_BULK_PAUSE_SECONDS` |
| UG and external recipients | Must be authorized in the server-side relay policy |
| Source-IP restrictions | UG ICT must allowlist the production worker's stable outbound IP |
| Contact-form destination | `CONTACT_RECIPIENT_EMAIL` |

The current transport supports password-authenticated SMTP and IP-allowlisted SMTP relay. If UG requires OAuth, Microsoft Graph, Gmail API, or another provider API, obtain the tenant/provider details and scopes first; an adapter can then replace the transport without changing the templates or portal workflows.

`SMTP_USE_TLS` remains a compatibility setting for older deployments. New environments should use `SMTP_SECURITY`.

## Supported communications

All messages contain a plain-text alternative and a responsive, University-oriented HTML template using the portal's established navy, blue, and gold identity. The current categories are:

- membership invitation and account activation;
- password reset and account security;
- official member and role-wide announcements;
- event notifications;
- administrative notices;
- Secretariat updates;
- selected-member communications; and
- public contact-form messages routed to the Secretariat.

Announcements and selected-member notices create in-portal notifications first, then queue a background email job in the same database transaction. Every recipient receives a separate message; recipient addresses are never exposed through a shared `To`, `Cc`, or `Bcc` list. The configured batch size controls how many messages reuse one SMTP connection, and the optional pause controls pacing between connections.

## Self-service password recovery

The login page displays **Forgot password?** only when the public capability endpoint confirms that email delivery is configured. A member can then enter their email address and receives the same privacy-preserving response whether or not an active account exists.

For an active account, the portal queues a single-use reset link that expires after 30 minutes. Requesting another link invalidates every earlier reset link. The token is hashed in the account-token table, encrypted in the transactional task outbox, placed in the URL fragment so it is not sent to the web server, and removed from the browser address bar when the reset page reads it. Completing a reset invalidates the token and revokes every existing session for that member.

## SPF, DKIM and DMARC

UG ICT or the DNS administrator must make these changes because the application cannot publish institutional DNS records:

1. Authorize the chosen SMTP relay in the SPF record for the exact sender domain.
2. Enable DKIM signing in the mail service and publish the provider-issued selector record.
3. Confirm DMARC alignment between the visible `From` domain, SPF envelope sender, and DKIM signing domain.
4. Begin with the institution's approved DMARC policy and reporting addresses; do not weaken an existing policy for the portal.
5. Verify the final message headers with an internal UG mailbox and at least one external mailbox before member-wide use.

The portal should not send production mail until SPF, DKIM, and DMARC checks pass for `SMTP_FROM_EMAIL`.

## Failures, bounces and bulk policy

Immediate connection, authentication, TLS, and recipient-rejection failures are recorded in **Dashboard → Background jobs**. A batch with any rejected message is marked failed and reports attempted, accepted, and failed counts. The worker does not automatically retry a partially accepted batch because doing so could duplicate messages already accepted by the SMTP server.

Asynchronous bounces occur after SMTP acceptance and require provider-specific support. UG should provide one of:

- a monitored return-path/bounce mailbox and an agreed operating procedure; or
- a signed provider webhook/API with documented event types and retention rules.

Once that mechanism is known, add automated bounce classification and member-address suppression. Until then, the Secretariat/ICT process must review provider delivery reports before and after large announcements. Do not place SMTP credentials, reset links, member lists, or full email bodies in logs.

Before enabling member-wide delivery, confirm the approved daily/hourly limits, external-recipient policy, maximum recipients per connection, permitted attachment policy, and whether official membership communications require an opt-out or retention notice.

## Activation and verification

1. Add the approved values from `.env.example` to the production secret environment for both `api` and `worker`.
2. Restart those services and confirm the public capability endpoint reports `email_delivery: true`.
3. Send one branded acceptance message to an authorized internal test mailbox:

   ```bash
   docker compose exec api python -m utag_api.cli email-test --to approved.tester@ug.edu.gh
   ```

4. Confirm the visible sender, reply behavior, layout, links, SPF, DKIM, DMARC, and provider message trace.
5. Repeat with one approved external mailbox.
6. Use **Forgot password?** on the login page with an authorized test member, confirm the link arrives, reset the password, and verify the old password and existing sessions no longer work.
7. Publish a small, explicitly authorized test announcement and verify the background-job accepted/failed counts.
8. Set `EMAIL_BULK_BATCH_SIZE` and `EMAIL_BULK_PAUSE_SECONDS` to the limits supplied by UG before enabling member-wide announcements.

An SMTP acceptance response proves that the service accepted the message; it does not by itself prove inbox delivery. Provider traces and recipient checks complete the verification.
