# UG UTAG Portal

This repository contains the complete replacement platform for the University of Ghana branch of the University Teachers Association of Ghana. The production path is now Next.js + TypeScript on the web, FastAPI on the server, PostgreSQL for durable data, Redis and WebSockets for live state, RabbitMQ and Celery for background work, and S3-compatible object storage for files.

The earlier Django application remains under `utag_ug_archiver/` only as a read-only migration source. It is not imported, started, or required by the new stack. Do not delete it until the retention and decommission gates in the modernization blueprint have been signed off.

The complete product, architecture, security, delivery, migration, and acceptance blueprint is in [docs/UG_UTAG_END_TO_END_MODERNIZATION_BLUEPRINT.md](docs/UG_UTAG_END_TO_END_MODERNIZATION_BLUEPRINT.md). The executable production and zero-loss runbook is in [docs/IMPLEMENTATION_AND_ZERO_LOSS_RUNBOOK.md](docs/IMPLEMENTATION_AND_ZERO_LOSS_RUNBOOK.md).

## What is implemented

- Responsive public site: home, mandate, leadership, news, events, resources, gallery, search, contact, SEO metadata, PWA shell, and constrained-connectivity fallback.
- Secure account journeys: invitations, login, logout, session management, CSRF protection, password changes and reset links.
- Branded multipart email for invitations, password resets, portal enquiries, announcements, event notices, administrative notices, and Secretariat updates, with private batched member delivery and tracked failures.
- Bulk member onboarding: downloadable Excel template, row-by-row preview, staff-ID temporary passwords, mandatory first-login password change, and automatic UTAG, school, and department chats.
- Role-aware dashboard: Association Pulse, member and executive management, organization structure, editorial workflows, announcements, events and registration, documents, media, galleries, notifications, encrypted direct/group chat, advertising, analytics, audit, settings, and background jobs.
- Live data across dashboard pages through authenticated WebSockets, Redis Pub/Sub, transactional outbox events, query invalidation, reconnect backoff, and full resync after reconnect.
- File security: presigned quarantine uploads, declared and actual checksum validation, ClamAV streaming scan, private delivery links, image verification, and generated WebP variants.
- Production controls: versioned Alembic migrations, seed data, validated configuration, health/readiness, Prometheus metrics, JSON logs, Caddy TLS edge, Docker health checks, CI quality gates, backup scripts, and cutover gates.
- Zero-loss migration: source inventory, canonical row serialization, SHA-256 checksums, durable archive rows, explicit per-row dispositions, versioned domain promotion, media manifests, repeatable reconciliation, and immutable legacy retention.

## Repository layout

```text
apps/
  api/                 FastAPI service, workers, models, routes, migrations, tests
  web/                 Next.js public portal and member dashboard
docs/                  Blueprint, implementation notes, and operational runbooks
ops/                   Caddy, Prometheus, backup, reconciliation, and cutover tools
utag_ug_archiver/      Read-only legacy source retained for migration evidence
docker-compose.yml     Complete local/on-prem service topology
```

## Start the complete stack

1. Copy `.env.example` to `.env`.
2. Replace every value marked `change-me`, `replace-me`, or `replace-with…`.
3. Set `BOOTSTRAP_ADMIN_EMAIL` and a strong `BOOTSTRAP_ADMIN_PASSWORD` for the first start only.
4. Leave `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` empty when Caddy serves the web and API on one domain. Set them before building only when the browser must use a separate API origin.
5. Start the services:

```bash
docker compose --profile local up --build
```

The web portal is available at `http://localhost:3000`, the API at `http://localhost:8000`, and development API documentation at `http://localhost:8000/docs`.

After the administrator can sign in, remove the two bootstrap administrator values and restart the API. Seeding is idempotent and never resets an existing password.

For a public TLS edge, set `SITE_DOMAIN` and `ACME_EMAIL`, then run:

Production deliberately does not start the bundled development MinIO or ClamAV
containers. Configure a maintained S3-compatible object store in
`S3_ENDPOINT_URL` and a maintained malware scanner in `CLAMAV_HOST` first.

```bash
docker compose --profile production up -d
```

The bundled Prometheus profile is for local observability only. Use a maintained
managed or separately patched metrics platform in production.

## Local engineering workflow

Backend:

```bash
cp apps/api/.env.example apps/api/.env
docker compose --profile local up -d postgres redis rabbitmq minio minio-init clamav
make api-install
make migrate
cd apps/api && .venv/bin/python -m utag_api.cli seed
make api-check
```

The native API example uses loopback service addresses; keep its database,
RabbitMQ, and object-store credentials aligned with the root Docker `.env`.
The container stack uses internal service names instead.

Frontend:

```bash
pnpm install --frozen-lockfile
pnpm --filter @utag/web dev
pnpm --filter @utag/web check
pnpm --filter @utag/web build
```

To load fictional role and executive accounts for local acceptance testing:

```bash
DEMO_DATA_PASSWORD='choose-a-strong-test-password' make seed-demo
```

The command is blocked outside development and test environments. See
[docs/DEMO_TEST_ACCOUNTS.md](docs/DEMO_TEST_ACCOUNTS.md) for the login emails
and expected role experiences.

The application never creates database tables at runtime. Every schema change must be an Alembic migration and must be tested both forward and backward in a non-production environment.

Email service handoff, DNS requirements, bulk limits, bounce handling, and the SMTP acceptance test are documented in [docs/EMAIL_SERVICE_CONFIGURATION.md](docs/EMAIL_SERVICE_CONFIGURATION.md).

## Zero-loss migration sequence

Never point migration tools at the only copy of production data. Take and verify a database dump and media snapshot first. The legacy application remains authoritative during rehearsals.

```bash
export LEGACY_DATABASE_URL='postgresql://read_only_user:...@legacy-db/legacy'
export LEGACY_MEDIA_ROOT='/verified/read-only/media-snapshot'
export MIGRATION_BATCH_ID='rehearsal-01'
ops/scripts/reconcile-legacy.sh
```

The process performs these phases:

1. inventories every source table and row count;
2. serializes every source row canonically, including binary and temporal values;
3. calculates a SHA-256 checksum for every record;
4. writes each record to the immutable evidence set and the new `legacy_archive_records` table;
5. writes exactly one `migration_dispositions` row for every source record;
6. promotes supported records into their new domain tables without deleting the archive copy;
7. hashes and optionally copies every legacy media object;
8. reads every uploaded object back through object-storage metadata and verifies its byte count and SHA-256 value;
9. reports operationally promoted, partially promoted, and archive-only tables separately;
10. blocks cutover if counts differ, media is unverified, or archive-only records lack named approval.

The final gate requires an explicit archive-only decision file. Start from
`docs/examples/archive-only-approval.example.json`, include every table named in
`archive_approval_required`, and record the real approver, decision, and time.
This is intentionally not generated by the migration code: accepting an
archive-only domain is a data-owner decision, not a software default.

Production cutover still requires the full go/no-go gates in the runbook, named technical and business approval, a tested rollback window, and verified backup restoration. A successful deploy is not by itself permission to remove the legacy system.

## Security rules

- Browser authentication uses opaque, rotated, server-side sessions in HttpOnly cookies.
- Every authenticated mutation requires a session-bound CSRF token.
- Authorization is enforced again at each data access and mutation boundary.
- Migrated Django PBKDF2 passwords remain valid and upgrade to Argon2 on successful login.
- Online-event credentials, conversation keys, and chat content are encrypted at rest.
- Public and private media are separate policy decisions; private files use short-lived signed URLs.
- Production configuration rejects SQLite, wildcard origins/hosts, insecure cookies, the development secret, and an absent malware scanner.
- Audit and outbox records are written in the same database transaction as the business change.

## Required production operations

Routine releases must use the guarded [production deployment runbook](docs/ROUTINE_PRODUCTION_DEPLOYMENT.md),
which verifies backups, security posture, health, and disk-safe Docker cleanup
before and after a release.

- Daily PostgreSQL backups plus point-in-time recovery where the hosting profile supports it.
- Object-store versioning and retention rules for media and migration evidence.
- Quarterly restore drills with recorded recovery time and recovery point evidence.
- Alerts for readiness failure, elevated error rate, queue growth, outbox lag, failed file scanning, failed backups, and abnormal authentication attempts.
- Key and secret rotation through the deployment platform, never through committed files.
- Dependency and container scanning before promotion to production.

`ops/scripts/backup-modern.sh` creates a matching PostgreSQL dump and object
snapshot with SHA-256 manifests:

```bash
BACKUP_DIRECTORY=/verified/ug-utag-backups ops/scripts/backup-modern.sh
```

Restore drills must use the dump and object directory from the same timestamp.
The restore command is deliberately guarded because it replaces the target
database and removes object-store files absent from the selected snapshot:

```bash
RESTORE_CONFIRM=restore-ug-utag \
DATABASE_BACKUP=/verified/ug-utag-backups/ug-utag-TIMESTAMP.dump \
OBJECT_BACKUP_DIRECTORY=/verified/ug-utag-backups/ug-utag-TIMESTAMP-objects \
ops/scripts/restore-modern.sh
```

The old Django containers and routes must not be added to the new production topology. All public traffic switches to the new edge only after reconciliation and acceptance pass.
