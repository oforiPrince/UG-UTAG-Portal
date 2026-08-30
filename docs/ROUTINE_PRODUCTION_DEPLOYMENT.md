# Routine production deployments without data loss

Use this runbook only after the modern Next.js/FastAPI platform is already the
live production system. The first legacy-to-modern cutover remains governed by
`ops/scripts/ship-production.sh` and the zero-loss migration runbook.

## Safety guarantees

`ops/scripts/push-production-update.sh` sends one exact Git commit to production.
The server-side `deploy-production-update.sh` then:

1. locks deployment so two releases cannot run concurrently;
2. verifies the commit is the production branch tip;
3. verifies the production `.env` permissions and mandatory security settings;
4. blocks unexpected non-loopback listeners (TCP 22/80/443 and UDP 443 are
   allowed by default);
5. validates the production Compose profile without changing running services;
6. requires backups to live on a separate mounted filesystem;
7. makes and validates a custom-format PostgreSQL dump;
8. incrementally mirrors object storage, or verifies a recent external backup;
9. keeps the running Git checkout untouched by creating an immutable worktree;
10. refreshes base images, builds the release, and runs Alembic migrations
    before service replacement;
11. recreates only what Compose needs and removes project orphans;
12. checks container health, loopback bindings, HTTPS, HSTS, and security headers;
13. removes stopped portal containers, dangling images, aged build cache, excess
    rollback tags, and old release worktrees;
14. never removes Docker volumes and never runs `docker compose down -v`,
    `docker volume prune`, or `docker system prune --volumes`.

Google Drive OAuth is required by default. The preflight checks that the client
ID and secret are present, encrypted token storage has a strong active key, and
the callback is exactly
`https://utag.ug.edu.gh/api/v1/integrations/google-drive/callback`. Set
`REQUIRE_GOOGLE_DRIVE=false` only when the integration is intentionally disabled.

Do not add a port to `ALLOWED_PUBLIC_TCP_PORTS` or
`ALLOWED_PUBLIC_UDP_PORTS` merely to make a failed gate pass. First bind the
service to loopback, place it on a private management network, or confirm a
default-deny firewall and documented operational need.

Database backups and the object mirror are not deleted by the deployment
script. Put retention and immutability on the backup platform itself.

## One-time server preparation

Provision encrypted backup storage that is not the server root filesystem. For
example, mount protected storage at `/mnt/utag-backups`, then create a directory
owned only by the deployment account:

```bash
sudo install -d -m 700 -o utagadmin -g utagadmin /mnt/utag-backups/production
```

The backup target should provide encryption at rest, access logs, immutable or
versioned retention, off-host replication, capacity alerts, and periodic restore
tests. A directory on the same root disk is not a disaster-recovery backup. The
emergency `ALLOW_SAME_FILESYSTEM_BACKUP=true` override exists only to avoid an
unplanned outage while protected storage is being repaired.

Keep `/opt/utag_ug_website/UG-UTAG-Portal-modern/.env` at mode `600`. Do not
commit, copy into release folders, print, or attach this file to tickets.

## Object backup modes

The default `OBJECT_BACKUP_MODE=mirror` incrementally copies the media bucket to
`BACKUP_DIRECTORY/object-mirror`. It never removes an object from the mirror,
which prevents normal source deletion from erasing the backup.

For managed object storage with separate versioning and backup, set
`OBJECT_BACKUP_MODE=external` and provide `OBJECT_BACKUP_SENTINEL` pointing to a
success marker updated by that backup job. The marker must be newer than 24
hours by default.

## Dry run

A dry run performs Git, environment, Compose, data-service, disk, and backup
mount checks without creating backups, building images, migrating, or restarting
services:

```bash
PRODUCTION_HOST=utagadmin@197.255.126.246 \
BACKUP_DIRECTORY=/mnt/utag-backups/production \
ops/scripts/push-production-update.sh --dry-run --no-push
```

Dry-run mode never pushes. It requires the local commit to already equal the
production branch tip; commit and push a candidate through the normal review
process before using production preflight.

## Deploy

The wrapper refuses an uncommitted working tree and a non-fast-forward update.
Commit and review the exact release first, then run:

```bash
PRODUCTION_HOST=utagadmin@197.255.126.246 \
PRODUCTION_BRANCH=deploy_v2 \
BACKUP_DIRECTORY=/mnt/utag-backups/production \
PUBLIC_HEALTH_BASE_URL=https://utag.ug.edu.gh \
ops/scripts/push-production-update.sh --deploy
```

The server stores deployment evidence under
`/opt/utag_ug_website/deploy-state/evidence/`. Failed deployments keep their
database backup and evidence. Database restoration is intentionally not
automatic: restoring over a live database after new writes requires an explicit
incident decision and reconciliation.

## Space policy

The deployer requires at least 10 GiB free before building and 5 GiB after
cleanup. It retains three release worktrees and two rollback image generations
by default. It prunes only:

- stopped containers belonging to the `ug-utag-portal` Compose project;
- dangling, unreferenced images;
- build cache older than seven days (or older than 24 hours in low-space mode);
- rollback tags beyond the configured retention;
- release worktrees beyond the configured retention.

It never prunes database, Redis, RabbitMQ, object-storage, Caddy, ClamAV, or
monitoring volumes.

## Security operations outside this script

A deployment script cannot keep the whole operating system secure by itself.
Production also requires:

- SSH keys only, disabled SSH password authentication, and disabled direct root
  login;
- a default-deny firewall exposing only required public ports (normally 80/443);
- automatic security updates with maintenance/reboot alerts;
- least-privilege deployment access and protected Git branches;
- container/dependency scanning before release approval;
- external monitoring for health, 5xx rates, authentication abuse, queue lag,
  malware scanning, backup failures, certificate expiry, disk, CPU, and memory;
- metrics exporters bound to loopback or a private management network, never an
  unrestricted public interface;
- daily database backups/PITR where supported, object-store versioning, and
  quarterly restore drills;
- documented secret, encryption-key, and OAuth credential rotation.

Treat any failed backup, failed restore drill, insecure bind, missing TLS header,
or unhealthy mandatory service as a production deployment blocker.
