# UG UTAG implementation and zero-loss production runbook

## Purpose

This runbook is the executable handoff for the new UG UTAG platform. It turns the modernization blueprint into exact environment, migration, validation, cutover, rollback, and decommission actions. The non-negotiable rule is simple: no legacy database row or media object may disappear merely because it does not fit a new screen or schema.

## Verified local release baseline — 23 July 2026

This repository now contains and locally runs the complete replacement path: the
Next.js public site and dashboard, FastAPI API, PostgreSQL, Redis, RabbitMQ,
Celery worker, MinIO-compatible object storage, ClamAV scanning, authenticated
WebSockets, audit/outbox events, and migration tooling. The old Django project
is not used by the running replacement services.

The following legacy-equivalent dashboard workflows were exercised against the
running Compose environment:

- administrator sign-in and required first-login password replacement;
- live overview, connection state, activity, notifications, and navigation;
- member search, invite, edit, role/status management, safe archive, CSV export,
  and CSV/XLSX import preview with validation and duplicate reporting;
- executive appointments and the public Executive Officers / Local Executive
  Council leadership presentation;
- schools, colleges, departments, and other organization records;
- news, announcements, events, documents and versions, galleries, media, and
  the managed homepage carousel;
- direct and group chat administration, notification broadcast, advertising
  slots/campaigns/plans/orders, audit, feature flags, settings, and jobs;
- secure upload, malware scan, private content retrieval, and retained archive;
- responsive dashboard behavior at a narrow mobile viewport.

The homepage carousel accepts only public image assets in `ready` scan state.
Administrators choose the image from the media library rather than entering an
internal identifier. Slides have explicit order and publication state, and
archive removes them from the public site without erasing administrative or
audit history. The public hero uses manual controls and does not force automatic
motion.

Release checks at this baseline:

- FastAPI: Ruff and MyPy passed; 20 tests passed with 57% aggregate coverage;
- Next.js: ESLint and TypeScript passed; 11 component tests passed; production
  build passed;
- Compose configuration validated and the API, web, PostgreSQL, Redis,
  RabbitMQ, ClamAV, MinIO, and worker services started successfully;
- a live member-import dry run validated one row and persisted zero rows;
- the verification database retained one administrator and zero test media;
- the administrator remains active with the forced password-change flag set.

This is engineering evidence, not permission to cut production traffic. A real
cutover still requires a production-data rehearsal, complete reconciliation,
verified backup restoration, signed archive-only decisions, security and
business acceptance, and the go/no-go sequence below.

## Replacement boundary

The target production runtime contains only the root `docker-compose.yml` services: Next.js, FastAPI, PostgreSQL, Redis, RabbitMQ, Celery, MinIO/S3, ClamAV, and optionally Caddy and Prometheus. The Django project is a read-only migration source. New writes must never be dual-written to ad-hoc Django and FastAPI code paths.

## Environments

Use distinct development, staging, migration-rehearsal, and production environments. Staging must use production-equivalent PostgreSQL, object storage, Redis, RabbitMQ, secure cookies, HTTPS, and the malware scanner. Test data must not contain copied personal information unless the environment has production-equivalent controls.

## Before the first rehearsal

- Assign named owners for database migration, files, identity, product acceptance, security, rollback, and final go/no-go.
- Create a read-only legacy database account and a read-only media snapshot.
- Record source database version, encoding, timezone, extensions, table counts, and media root size.
- Verify a legacy database backup can be restored to an isolated database.
- Provision the new stack and apply all Alembic migrations.
- Set a unique 32+ character `APP_SECRET_KEY`; this key protects sessions and wrapped field keys.
- Run `python -m utag_api.cli seed` and remove bootstrap administrator secrets after use.

## Rehearsal commands

```bash
cp .env.example .env
docker compose up -d postgres redis rabbitmq minio minio-init clamav
docker compose run --rm --no-deps api alembic upgrade head
docker compose run --rm --no-deps api python -m utag_api.cli seed

export LEGACY_DATABASE_URL='postgresql://read_only_user:...@legacy/legacy_database'
export LEGACY_MEDIA_ROOT='/snapshots/legacy-media'
export MIGRATION_BATCH_ID='rehearsal-01'
export MIGRATION_EVIDENCE_DIRECTORY='migration-evidence/rehearsal-01'
ops/scripts/reconcile-legacy.sh
```

The reconciliation wrapper executes the migration code from the versioned API
image on the Compose network. It passes the legacy URL by environment name
instead of printing the credential in the process arguments and mounts only the
evidence output plus an optional read-only media snapshot.

Never include connection strings in screenshots, tickets, logs, or evidence files. The migration tool does not print them.

## What capture guarantees

Every in-scope legacy row gets:

- a canonical JSON representation;
- a source table and complete primary-key identity;
- a SHA-256 checksum;
- one durable `legacy_archive_records` record;
- one durable `migration_dispositions` record;
- a JSONL evidence entry outside the new operational schema.

Known domain records are promoted after capture. Capture remains even after promotion, making transforms reproducible and preserving fields that the new domain model intentionally does not expose. Records that cannot yet be promoted remain classified as archived, not dropped.

No database table is silently excluded. Django session rows and the Django
migration ledger are captured for forensic completeness but are never activated
as FastAPI sessions or treated as target schema state. Legacy groups are mapped
to the built-in Member, Executive, Secretary, Editor, Publisher, or
Administrator roles. Unrecognized groups are created with no permissions and
must be reviewed before anyone grants them capabilities. Legacy superusers are
assigned the Administrator role; ordinary `is_staff` alone does not escalate a
member.

Every legacy file gets a manifest path, exact byte count, SHA-256 checksum,
content type, and target object key. After upload, the migration reads the
object's stored size and checksum metadata and records `target_verified: true`
only when both match. Symlinks and paths that escape the verified media root are
rejected and require an explicit remediation decision.

Migration evidence contains personal and security-sensitive source data. The
tool restricts local evidence directories to the current operating-system user;
production evidence must additionally live on an encrypted volume or encrypted
object store with access logging, immutability/retention controls, backups, and
named key custody. Never attach raw JSONL evidence to a ticket.

## Mandatory reconciliation

`legacy_migration.py reconcile` compares source, capture, and disposition counts
per table and emits a machine-readable report. A table passes only when all
three counts are identical. It also reports `migrated`, `archived_only`, and a
coverage state (`operationally_promoted`, `partially_promoted`, `archive_only`,
or `empty`). Any table with archive-only rows appears in
`archive_approval_required`. Business-domain checks must also be recorded for:

- active users and executive appointments;
- role/group membership;
- published and draft articles;
- events and registration settings;
- announcements and notification recipients;
- document/file joins and visibility rules;
- galleries and image counts;
- advert slots, plans, campaigns, impressions, clicks, and orders;
- direct and group conversations, memberships, messages, reads, and attachments;
- total media object count and total bytes.

The automated row gate is necessary but not sufficient. Product owners must sample records from each domain and confirm content, dates, authors, visibility, links, and file readability.

### Archive-only approval

Copy `docs/examples/archive-only-approval.example.json` into the protected
migration evidence directory. Populate it with every table listed in the final
reconciliation report's `archive_approval_required` array. The decision must
state whether the data will remain accessible only through the restricted
archive, receive a later operational backfill, or is subject to a separate
retention action. Software operators must not sign on behalf of the data owner.

The gate deliberately fails when this file is missing, incomplete, anonymous,
or lacks a decision. It also fails when `media-manifest.json` is missing or any
object lacks successful target verification.

## Production cutover sequence

1. Confirm a successful rehearsal from a recent production-sized snapshot.
2. Announce the maintenance window and support route.
3. Verify new-stack backups and a restore drill.
4. Deploy the exact container images already accepted in staging.
5. Put the legacy application in read-only maintenance mode; do not stop its database.
6. Record the legacy write-freeze timestamp and highest identifiers per high-write table.
7. Take the final database dump and media snapshot; calculate and store checksums.
8. Run final capture, promotion, file copy, and reconciliation with a new batch identifier.
9. Run `ops/scripts/cutover-gates.sh` against the final reconciliation report
   and signed archive-only decision:

   ```bash
   ops/scripts/cutover-gates.sh \
     migration-evidence/final/reconciliation.json \
     migration-evidence/final/archive-only-approval.json
   ```
10. Execute smoke tests: public pages, sign-in, permissions, member search, document access, event registration, upload/scan, notification, chat send/read, adverts, audit, and live updates.
11. Obtain named technical, security, data, and business approval.
12. Switch edge traffic to the new Caddy/load-balancer target.
13. Keep the legacy application and database read-only and reachable only to the migration team.
14. Monitor errors, latency, sessions, outbox lag, queues, WebSockets, scans, database load, and support reports continuously through the rollback window.

## Rollback rule

Rollback must not discard writes accepted by the new platform. If rollback is triggered after traffic switches, first place the new platform in read-only mode, record the new write-stop timestamp, export all post-cutover audit/outbox/domain writes, and reconcile them into a recovery ledger. Only then may traffic return to the read-only legacy experience or a controlled maintenance page. Reopening legacy writes requires a separately approved reverse-migration procedure.

Rollback triggers include unexplained reconciliation variance, systemic authorization failure, missing/unreadable records, unbounded error rate, data corruption, unavailable backups, or a security incident.

## Post-cutover

- Compare live counts and sampled records at 1 hour, 24 hours, 7 days, and 30 days.
- Retain final legacy database dumps, media snapshot, manifests, reconciliation reports, mapping version, source code, and encryption-key custody evidence under the approved retention policy.
- Rotate temporary migration and bootstrap credentials.
- Continue restore drills and record the observed RTO/RPO.
- Decommission Django only after the retention period, zero unresolved migration issues, signed data-owner approval, and a final recoverability test.

## Verification commands

```bash
cd apps/api
.venv/bin/ruff check .
.venv/bin/python -m py_compile scripts/legacy_migration.py
.venv/bin/mypy src
.venv/bin/pytest --cov-fail-under=55

cd ../..
pnpm --filter @utag/web lint
pnpm --filter @utag/web typecheck
pnpm --filter @utag/web test
pnpm --filter @utag/web build
docker compose config --quiet
```

All commands must pass on the exact release revision before a production approval is valid.
