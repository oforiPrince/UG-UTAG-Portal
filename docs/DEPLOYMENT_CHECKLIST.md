# UG UTAG production deployment checklist

This checklist covers the active Next.js, FastAPI, PostgreSQL, Redis, RabbitMQ,
Celery, Caddy, and external object-storage and malware-scanning services. The
Django application under `utag_ug_archiver/` is a read-only migration source
and must not be deployed as the live portal.

The authoritative zero-loss data procedure remains
`docs/IMPLEMENTATION_AND_ZERO_LOSS_RUNBOOK.md`.

## 1. Release candidate gates

- [ ] Review `git status` and the final diff; every release file is intentional.
- [ ] Install exactly the locked frontend dependencies:

  ```bash
  pnpm install --frozen-lockfile
  ```

- [ ] Run the frontend quality, security, build, and browser gates:

  ```bash
  pnpm lint
  pnpm typecheck
  pnpm test
  pnpm build
  pnpm audit --prod --audit-level=moderate
  pnpm test:e2e
  ```

- [ ] Install and verify the API in a clean Python 3.14 environment:

  ```bash
  cd apps/api
  python3.14 -m venv .venv
  .venv/bin/pip install -e '.[dev]'
  .venv/bin/ruff check .
  .venv/bin/mypy src
  .venv/bin/pytest --cov-fail-under=55
  .venv/bin/pip-audit --local --skip-editable
  cd ../..
  ```

- [ ] Validate and build the deployment topology:

  ```bash
  docker compose --profile local config --quiet
  docker compose --profile production config --quiet
  docker compose build api web postgres proxy
  ```

- [ ] CI is green for backend, frontend, database migration, and container jobs.

## 2. Production configuration

Create production secrets in the deployment platform; never commit `.env`.
Start from `.env.example`, replace every placeholder, and verify at least:

- [ ] `ENVIRONMENT=production`.
- [ ] `PUBLIC_WEB_URL` is the final HTTPS origin.
- [ ] `ALLOWED_ORIGINS` contains that exact origin and `ALLOWED_HOSTS` contains
      its hostname.
- [ ] `SESSION_COOKIE_SECURE=true`; set `SESSION_COOKIE_DOMAIN` only when
      cross-subdomain cookies are deliberately required.
- [ ] `POSTGRES_PASSWORD`, `RABBITMQ_DEFAULT_PASS`, `APP_SECRET_KEY`, and
      `S3_SECRET_KEY` are independent random secrets.
- [ ] `FIELD_ENCRYPTION_KEYS` contains the active
      `FIELD_ENCRYPTION_KEY_VERSION`; record key custody and rotation procedure.
- [ ] `S3_ENDPOINT_URL` points to maintained external object storage; the
      local-development MinIO endpoint is rejected by the production profile.
- [ ] `S3_SERVER_SIDE_ENCRYPTION=AES256`, or `aws:kms` with `S3_KMS_KEY_ID`.
- [ ] `MALWARE_SCAN_REQUIRED=true` and `CLAMAV_HOST` points to a maintained
      external scanner; the local-development scanner is rejected in production.
- [ ] SMTP host, credentials, sender, and contact recipient are configured and
      verified from staging.
- [ ] `METRICS_BEARER_TOKEN` is set when metrics are enabled.
- [ ] Bootstrap and demo passwords are absent after the first administrator is
      created.
- [ ] Object-store versioning/retention, PostgreSQL backups/PITR, monitoring,
      and alert destinations are enabled outside the application stack.

The API deliberately refuses to start in production when mandatory security
settings are missing, insecure, or still contain documented placeholders.

## 3. Data and rollback readiness

- [ ] A current legacy database dump and read-only media snapshot exist.
- [ ] Reconciliation passes with exact row counts, checksums, media verification,
      and named archive-only approvals:

  ```bash
  ops/scripts/reconcile-legacy.sh
  ops/scripts/cutover-gates.sh \
    migration-evidence/REHEARSAL/reconciliation.json \
    migration-evidence/REHEARSAL/archive-approval.json
  ```

- [ ] A matching modern database/object backup is created:

  ```bash
  BACKUP_DIRECTORY=/verified/ug-utag-backups ops/scripts/backup-modern.sh
  ```

### Organization hierarchy reconciliation

After changing the canonical college, school, or department reference data—or
after importing legacy Django organization rows—preview the reconciliation
against a current backup:

```bash
docker compose exec api \
  python -m utag_api.cli reconcile-organization --prune-unlinked
```

The command is a dry run unless `--apply` is present. Review the counts and any
member UUIDs requiring manual correction. It normalizes only known harmless
legacy spelling differences, relinks only unambiguous member affiliations and
announcement/document audiences, and never prunes administrator-created custom
units.

When the dry run is accepted and a verified backup exists, apply the same plan:

```bash
docker compose exec api \
  python -m utag_api.cli reconcile-organization --apply --prune-unlinked
```

Only imported legacy units with no remaining member, announcement audience,
document audience, child-unit, or system-chat-history linkage are deleted.
Empty legacy system-chat shells are removed with their unit; groups containing
members, invitations, or messages retain the legacy unit. The command also
resynchronizes system-managed organization chat memberships after a committed
reconciliation.

- [ ] The matching backup set has been restored in isolation with
      `ops/scripts/restore-modern.sh`; record recovery time and recovery point.
- [ ] The previous application images/configuration and traffic rollback steps
      are recorded. Never improvise an Alembic downgrade in production; restore
      the verified backup when a backwards-incompatible data rollback is needed.

## 4. Staging rehearsal

- [ ] Staging uses production-equivalent HTTPS, secure cookies, PostgreSQL,
      Redis, RabbitMQ, object storage, worker, scheduler, malware scanning, and
      SMTP.
- [ ] Apply migrations and verify no pending model changes:

  ```bash
  cd apps/api
  .venv/bin/alembic upgrade head
  .venv/bin/alembic check
  ```

- [ ] Exercise administrator and ordinary-member journeys: login, mandatory
      password change, profile, member creation/edit/import/export, role and
      permission boundaries, content publication, documents, events,
      notifications, chat/attachments, media scanning, gallery, and logout.
- [ ] Verify `records.delete` is present for an administrator but absent for a
      secretary/publisher and from the individual permission-grant catalog.
- [ ] Verify permanent delete succeeds for an unreferenced staging record,
      returns a clear conflict for a linked record, and queues media-object
      cleanup only after the media database delete commits.
- [ ] Run the authenticated browser journey against staging:

  ```bash
  PLAYWRIGHT_BASE_URL=https://staging.example.org \
  E2E_MEMBER_EMAIL='release-test-member@example.org' \
  E2E_MEMBER_PASSWORD='from-the-secret-store' \
  pnpm test:e2e
  ```

- [ ] Verify responsive layouts and keyboard navigation on representative mobile
      and desktop widths; check browser console and failed network requests.
- [ ] Send a password reset, invitation, and contact message end to end; confirm
      delivery, links, sender identity, and recipient routing.
- [ ] Upload clean and malware test files; confirm clean files become `ready` and
      rejected files never become publicly retrievable.
- [ ] Run expected-traffic load tests and record API latency, error rate, worker
      queue depth, database connections, and resource headroom.

## 5. Production cutover

- [ ] Freeze legacy writes for the agreed window and take final matching backups.
- [ ] Run final reconciliation and cutover gates using production snapshots.
- [ ] Record named technical, data-owner, security, product, and go/no-go approval.
- [ ] Start the release:

  ```bash
  docker compose --profile production up -d --build
  ```

- [ ] Confirm the maintained external metrics/logging platform is receiving data
      and its launch alerts route to the named on-call owner.

- [ ] Confirm every required service is healthy and inspect startup/migration logs:

  ```bash
  docker compose ps
  docker compose logs --no-color --tail=200 api web worker scheduler proxy
  ```

- [ ] Verify the edge and readiness endpoints:

  ```bash
  curl --fail --show-error --silent https://YOUR_DOMAIN/health/live
  curl --fail --show-error --silent https://YOUR_DOMAIN/health/ready
  curl --fail --show-error --silent https://YOUR_DOMAIN/api/health
  ```

- [ ] Run the authenticated Playwright journey against the final origin.
- [ ] Verify public home, about, leadership, news, events, resources, gallery,
      search, contact, login, and member dashboard pages.
- [ ] Verify TLS, HSTS, CSP, framing protection, secure/HttpOnly session cookie,
      CSRF rejection, authorization failures, and non-public media access.
- [ ] Remove bootstrap credentials and the release test account, then restart the
      affected services if configuration changed.
- [ ] Switch traffic only after all preceding gates pass.

## 6. First 24 hours

- [ ] Watch readiness, 4xx/5xx rates, authentication failures, latency, database
      saturation, object-storage errors, worker failures, queue/outbox lag,
      malware-scan failures, disk capacity, and backup alerts.
- [ ] Confirm scheduled jobs, notifications, email, WebSockets, and media variants
      continue to work after the first scheduler cycles.
- [ ] Record the deployed commit/image digests, migration revision, approvers,
      backup identifiers, verification evidence, and any accepted risk.
- [ ] Keep the legacy source and final snapshots immutable until the retention and
      decommission approvals in the runbook are complete.

## Go/no-go rule

Go live only when all automated gates pass, the authenticated staging/production
journey passes, backups have been restored successfully, reconciliation is exact,
mandatory production services are healthy, and named business/security owners
approve the cutover. A successful build alone is not production approval.
