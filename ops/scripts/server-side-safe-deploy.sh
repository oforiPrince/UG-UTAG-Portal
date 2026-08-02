#!/usr/bin/env bash
# Safe parallel deploy of the modern UG UTAG stack on the live host.
#
# Guarantees:
#   - Does NOT drop, rewrite, or migrate-away the current production DB
#   - Does NOT stop Nginx / bind ports 80 or 443 (legacy site stays live)
#   - Takes a checksummed legacy DB dump BEFORE any modern stack work
#   - Checks out deploy_v2 into a sibling worktree so running Django code is untouched
#
# Run ON the server as utagadmin:
#   bash ops/scripts/server-side-safe-deploy.sh
# or, if deploy_v2 is not checked out yet:
#   curl is not required — paste the bootstrap block from the README section below.
#
# After this succeeds, the modern stack is reachable on loopback:
#   http://127.0.0.1:3000  (web)
#   http://127.0.0.1:8000  (api)
# Legacy public site remains on :80/:443 until a later explicit cutover.

set -euo pipefail

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }

LIVE_ROOT="${LIVE_ROOT:-/opt/utag_ug_website/UG-UTAG-Portal}"
LEGACY_DIR="${LEGACY_DIR:-${LIVE_ROOT}/utag_ug_archiver}"
MODERN_ROOT="${MODERN_ROOT:-/opt/utag_ug_website/UG-UTAG-Portal-modern}"
BRANCH="${BRANCH:-deploy_v2}"
ARTIFACT_ROOT="${ARTIFACT_ROOT:-/opt/utag_ug_website/cutover-artifacts}"
BATCH_ID="${MIGRATION_BATCH_ID:-safe-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${ARTIFACT_ROOT}/${BATCH_ID}"

require_cmd docker
require_cmd git
require_cmd curl
require_cmd python3

[[ -d "${LIVE_ROOT}/.git" ]] || die "Expected git repo at ${LIVE_ROOT}"
[[ -d "${LEGACY_DIR}" ]] || die "Expected legacy app at ${LEGACY_DIR}"

mkdir -p "${EVIDENCE_DIR}/legacy-backups"
log "Artifact directory: ${EVIDENCE_DIR}"

log "=== 1) Inventory (read-only) ==="
{
  echo "host=$(hostname)"
  echo "date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "live_root=${LIVE_ROOT}"
  echo "branch=$(git -C "${LIVE_ROOT}" branch --show-current 2>/dev/null || true)"
  echo "--- docker ps ---"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true
  echo "--- listening sockets ---"
  ss -tlnp 2>/dev/null | awk 'NR==1 || /:(80|443|3000|8000|5432)\s/' || netstat -tlnp 2>/dev/null | head -40 || true
} | tee "${EVIDENCE_DIR}/inventory.txt"

log "=== 2) Backup the CURRENT production database (source left intact) ==="
cd "${LEGACY_DIR}"

# Discover compose + env files used by the live Django stack.
DB_COMPOSE=""
for candidate in docker-compose.db.yml compose.db.yml docker-compose.yml; do
  if [[ -f "${LEGACY_DIR}/${candidate}" ]]; then
    DB_COMPOSE="${LEGACY_DIR}/${candidate}"
    break
  fi
done
[[ -n "${DB_COMPOSE}" ]] || die "Could not find a DB compose file under ${LEGACY_DIR}"

APP_ENV=""
for candidate in .env .env.prod .env.production; do
  if [[ -f "${LEGACY_DIR}/${candidate}" ]]; then
    APP_ENV="${LEGACY_DIR}/${candidate}"
    break
  fi
done
DB_ENV=""
for candidate in .env.db .env; do
  if [[ -f "${LEGACY_DIR}/${candidate}" ]]; then
    DB_ENV="${LEGACY_DIR}/${candidate}"
    break
  fi
done

# Load DB credentials without printing secrets.
set +u
set -a
# shellcheck disable=SC1090
[[ -n "${DB_ENV}" ]] && source "${DB_ENV}"
# shellcheck disable=SC1090
[[ -n "${APP_ENV}" && "${APP_ENV}" != "${DB_ENV}" ]] && source "${APP_ENV}"
set +a
set -u

POSTGRES_DB_NAME="${POSTGRES_DB:-${DB_NAME:-app_database}}"
POSTGRES_DB_USER="${POSTGRES_USER:-${DB_USER:-db_user}}"
POSTGRES_CONTAINER="$(
  docker compose -f "${DB_COMPOSE}" ps -q db 2>/dev/null \
    || docker compose -f "${DB_COMPOSE}" ps -q postgres 2>/dev/null \
    || true
)"
if [[ -z "${POSTGRES_CONTAINER}" ]]; then
  # Fallback: find a running postgres container.
  POSTGRES_CONTAINER="$(docker ps --filter 'ancestor=postgres' --format '{{.ID}}' | head -1)"
fi
[[ -n "${POSTGRES_CONTAINER}" ]] || die "No running Postgres container found — refuse to continue without a backup"

DUMP_FILE="${EVIDENCE_DIR}/legacy-backups/prod-${BATCH_ID}.dump"
log "Dumping database '${POSTGRES_DB_NAME}' from container ${POSTGRES_CONTAINER}"
docker exec -e PGPASSWORD="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}" "${POSTGRES_CONTAINER}" \
  pg_dump -U "${POSTGRES_DB_USER}" -d "${POSTGRES_DB_NAME}" -Fc -f "/tmp/prod-${BATCH_ID}.dump"
docker cp "${POSTGRES_CONTAINER}:/tmp/prod-${BATCH_ID}.dump" "${DUMP_FILE}"
docker exec "${POSTGRES_CONTAINER}" rm -f "/tmp/prod-${BATCH_ID}.dump"
if command -v shasum >/dev/null 2>&1; then
  (cd "$(dirname "${DUMP_FILE}")" && shasum -a 256 "$(basename "${DUMP_FILE}")" > "$(basename "${DUMP_FILE}").sha256")
else
  (cd "$(dirname "${DUMP_FILE}")" && sha256sum "$(basename "${DUMP_FILE}")" > "$(basename "${DUMP_FILE}").sha256")
fi
log "Legacy DB backup written to ${DUMP_FILE}"
log "Checksum: $(cat "${DUMP_FILE}.sha256")"

# Build a LEGACY_DATABASE_URL for the migration tool (read from the live DB).
# Prefer connecting through the Docker network / published port rather than stopping anything.
DB_HOST_FOR_URL="${DB_HOST:-127.0.0.1}"
DB_PORT_FOR_URL="${DB_PORT:-5432}"
# If DB_HOST points at a docker service name, use localhost published port instead.
if [[ "${DB_HOST_FOR_URL}" == "db" || "${DB_HOST_FOR_URL}" == "postgres" ]]; then
  DB_HOST_FOR_URL="127.0.0.1"
fi
LEGACY_PASSWORD_RAW="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}"
[[ -n "${LEGACY_PASSWORD_RAW}" ]] || die "Could not resolve DB password from ${DB_ENV:-unknown}"
LEGACY_DATABASE_URL="$(
  python3 - <<PY
from urllib.parse import quote
user = quote("""${POSTGRES_DB_USER}""", safe="")
password = quote("""${LEGACY_PASSWORD_RAW}""", safe="")
host = """${DB_HOST_FOR_URL}"""
port = """${DB_PORT_FOR_URL}"""
db = quote("""${POSTGRES_DB_NAME}""", safe="")
print(f"postgresql://{user}:{password}@{host}:{port}/{db}")
PY
)"
export LEGACY_DATABASE_URL

MEDIA_CANDIDATES=(
  "${LEGACY_DIR}/media"
  "${LEGACY_DIR}/utag_ug_archiver/media"
  "/var/www/utag/media"
)
LEGACY_MEDIA_ROOT=""
for candidate in "${MEDIA_CANDIDATES[@]}"; do
  if [[ -d "${candidate}" ]]; then
    LEGACY_MEDIA_ROOT="${candidate}"
    break
  fi
done
if [[ -n "${LEGACY_MEDIA_ROOT}" ]]; then
  export LEGACY_MEDIA_ROOT
  log "Using LEGACY_MEDIA_ROOT=${LEGACY_MEDIA_ROOT}"
else
  log "WARNING: No media directory found; migration will skip file upload (--skip-media equivalent)"
fi

log "=== 3) Prepare modern code worktree (Django tree left on its current branch) ==="
cd "${LIVE_ROOT}"
git fetch origin "${BRANCH}"
if [[ -d "${MODERN_ROOT}/.git" || -f "${MODERN_ROOT}/.git" ]]; then
  log "Modern worktree already exists at ${MODERN_ROOT}"
  git -C "${MODERN_ROOT}" fetch origin "${BRANCH}"
  git -C "${MODERN_ROOT}" checkout "${BRANCH}"
  git -C "${MODERN_ROOT}" pull --ff-only origin "${BRANCH}" || true
else
  # Prefer worktree so we do not disturb the live checkout serving Django.
  if git worktree list | grep -q "${MODERN_ROOT}"; then
    log "Worktree already registered"
  else
    git worktree add -B "${BRANCH}" "${MODERN_ROOT}" "origin/${BRANCH}"
  fi
fi
[[ -f "${MODERN_ROOT}/docker-compose.yml" ]] || die "Modern worktree missing docker-compose.yml"
[[ -f "${MODERN_ROOT}/ops/scripts/ship-production.sh" ]] || die "Modern worktree missing ship-production.sh"

log "=== 4) Create modern .env if missing (does not overwrite an existing one) ==="
cd "${MODERN_ROOT}"
if [[ ! -f .env ]]; then
  cp .env.example .env
  python3 - <<'PY'
from pathlib import Path
import secrets
import re

path = Path(".env")
text = path.read_text()

def set_var(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    return content + ("\n" if not content.endswith("\n") else "") + line + "\n"

# Rehearsal-safe defaults: modern stack on loopback only; do NOT claim production edge yet.
replacements = {
    "ENVIRONMENT": "development",
    "PUBLIC_WEB_URL": "http://127.0.0.1:3000",
    "API_URL": "http://127.0.0.1:8000",
    "SESSION_COOKIE_SECURE": "false",
    "ALLOWED_ORIGINS": '["http://127.0.0.1:3000","http://localhost:3000"]',
    "ALLOWED_HOSTS": '["localhost","127.0.0.1","api"]',
    "SITE_DOMAIN": "localhost",
    "MALWARE_SCAN_REQUIRED": "false",
    "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
    "RABBITMQ_DEFAULT_PASS": secrets.token_urlsafe(24),
    "APP_SECRET_KEY": secrets.token_urlsafe(48),
    "FIELD_ENCRYPTION_KEYS": '{"v1":"%s"}' % secrets.token_urlsafe(32)[:32],
    "S3_SECRET_KEY": secrets.token_urlsafe(24),
    "BOOTSTRAP_ADMIN_EMAIL": "bootstrap-admin@utag.local",
    "BOOTSTRAP_ADMIN_PASSWORD": secrets.token_urlsafe(18) + "Aa1",
}
content = text
for key, value in replacements.items():
    content = set_var(content, key, value)
path.write_text(content)
print("Wrote initial modern .env with generated secrets")
PY
  log "Generated ${MODERN_ROOT}/.env — store bootstrap admin password securely:"
  grep -E '^(BOOTSTRAP_ADMIN_EMAIL|BOOTSTRAP_ADMIN_PASSWORD)=' .env || true
else
  log "Keeping existing ${MODERN_ROOT}/.env"
fi

# Persist migration pointers for later ship runs (do not echo password URL into files that get logged).
umask 077
printf '%s\n' "${LEGACY_DATABASE_URL}" > "${EVIDENCE_DIR}/legacy-database.url"
if [[ -n "${LEGACY_MEDIA_ROOT}" ]]; then
  printf '%s\n' "${LEGACY_MEDIA_ROOT}" > "${EVIDENCE_DIR}/legacy-media-root.txt"
fi
chmod 600 "${EVIDENCE_DIR}/legacy-database.url"

log "=== 5) Start modern stack ALONGSIDE legacy (no Caddy / no :80/:443) ==="
cd "${MODERN_ROOT}"
docker compose --profile local up -d --build

log "Waiting for modern API/web health on loopback"
for i in $(seq 1 90); do
  if curl --fail --silent --show-error http://127.0.0.1:8000/health/ready >/dev/null 2>&1 \
    && curl --fail --silent --show-error http://127.0.0.1:3000/api/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ "${i}" -eq 90 ]]; then
    die "Modern stack did not become healthy — legacy site was not modified"
  fi
done
docker compose ps | tee "${EVIDENCE_DIR}/modern-compose-ps.txt"

log "=== 6) Migrate data into the NEW database (legacy DB remains the source of truth) ==="
cd "${MODERN_ROOT}"
export MIGRATION_BATCH_ID="${BATCH_ID}"
export MIGRATION_EVIDENCE_DIRECTORY="${EVIDENCE_DIR}/migration-evidence"
mkdir -p "${MIGRATION_EVIDENCE_DIRECTORY}"
export LEGACY_DATABASE_URL
if [[ -n "${LEGACY_MEDIA_ROOT}" ]]; then
  export LEGACY_MEDIA_ROOT
  ops/scripts/reconcile-legacy.sh | tee "${EVIDENCE_DIR}/migrate.log"
else
  # Temporary: allow gates later with REQUIRE_MEDIA_MANIFEST=false if needed
  ops/scripts/reconcile-legacy.sh | tee "${EVIDENCE_DIR}/migrate.log" || true
  log "WARNING: media root missing; review migrate.log"
fi

log "=== 7) Backup the NEW modern database ==="
MODERN_DUMP="${EVIDENCE_DIR}/legacy-backups/modern-${BATCH_ID}.dump"
docker compose exec -T postgres pg_dump \
  --username "${POSTGRES_USER:-utag}" \
  --dbname "${POSTGRES_DB:-utag_portal}" \
  --format custom \
  --no-owner \
  --file "/tmp/modern-${BATCH_ID}.dump"
docker compose cp "postgres:/tmp/modern-${BATCH_ID}.dump" "${MODERN_DUMP}"
docker compose exec -T postgres rm -f "/tmp/modern-${BATCH_ID}.dump"
if command -v shasum >/dev/null 2>&1; then
  (cd "$(dirname "${MODERN_DUMP}")" && shasum -a 256 "$(basename "${MODERN_DUMP}")" > "$(basename "${MODERN_DUMP}").sha256")
else
  (cd "$(dirname "${MODERN_DUMP}")" && sha256sum "$(basename "${MODERN_DUMP}")" > "$(basename "${MODERN_DUMP}").sha256")
fi

log "=== DONE (safe parallel deploy) ==="
cat <<EOF

Legacy production site: still on :80/:443 (untouched edge)
Legacy production DB:   intact; dump at ${DUMP_FILE}
Modern stack worktree:  ${MODERN_ROOT}
Modern web (local):     http://127.0.0.1:3000
Modern API (local):     http://127.0.0.1:8000
Evidence:               ${EVIDENCE_DIR}

NEXT (only when you are ready to cut public traffic):
  1. Review ${EVIDENCE_DIR}/migration-evidence/reconciliation.json
  2. Fill archive-only approval if required
  3. Configure real S3 + ClamAV + ENVIRONMENT=production in ${MODERN_ROOT}/.env
  4. Run: cd ${MODERN_ROOT} && ops/scripts/ship-production.sh --mode cutover \\
        --confirm-write-freeze --confirm-go-live

EOF
