#!/usr/bin/env bash
# Ship the modern UG UTAG portal (Next.js + FastAPI) while preserving every
# production Django row and media object.
#
# This script never deletes the legacy database. It:
#   1. Preflights production configuration
#   2. Takes a checksummed legacy database dump (and optional media snapshot)
#   3. Starts the modern Compose stack
#   4. Captures / promotes / reconciles legacy data into the new schema
#   5. Runs automated cutover gates
#   6. Backs up the new database
#   7. Optionally brings up the Caddy production edge after explicit confirmation
#
# Default mode is rehearsal (safe). Production traffic switch requires cutover
# mode plus explicit confirmation flags.
#
# Usage examples:
#   # Safe rehearsal against a read-only legacy snapshot
#   export LEGACY_DATABASE_URL='postgresql://readonly:...@legacy/db'
#   export LEGACY_MEDIA_ROOT='/snapshots/legacy-media'
#   ops/scripts/ship-production.sh --mode rehearsal
#
#   # Final cutover after write-freeze + signed archive approval
#   export LEGACY_DATABASE_URL='postgresql://readonly:...@legacy/db'
#   export LEGACY_MEDIA_ROOT='/snapshots/legacy-media'
#   export ARCHIVE_ONLY_APPROVAL_FILE='migration-evidence/final/archive-only-approval.json'
#   ops/scripts/ship-production.sh --mode cutover \
#     --confirm-write-freeze \
#     --confirm-go-live \
#     --freeze-legacy-writers
#
# Resume from a later phase:
#   ops/scripts/ship-production.sh --mode rehearsal --from migrate
#
# Run one phase only:
#   ops/scripts/ship-production.sh --mode cutover --only backup-legacy

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

MODE="rehearsal"
FROM_PHASE="preflight"
ONLY_PHASE=""
CONFIRM_WRITE_FREEZE=0
CONFIRM_GO_LIVE=0
FREEZE_LEGACY_WRITERS=0
SKIP_MEDIA=0
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

PHASES=(
  preflight
  backup-legacy
  start-stack
  migrate
  gates
  backup-modern
  go-live
  verify
)

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

usage() {
  cat <<'EOF'
Usage:
  ops/scripts/ship-production.sh [options]

Options:
  --mode rehearsal|cutover     Default: rehearsal
  --from PHASE                 Start at PHASE (default: preflight)
  --only PHASE                 Run a single PHASE
  --confirm-write-freeze       Required for cutover (acknowledges legacy write freeze)
  --confirm-go-live            Required for cutover go-live / Caddy edge start
  --freeze-legacy-writers      Stop legacy Django writers via SSH before final dump
  --skip-media                 Skip LEGACY_MEDIA_ROOT / media gate requirements
  -h, --help                   Show this help

Required environment (cutover and rehearsal):
  LEGACY_DATABASE_URL          Read-only Postgres URL for the live/legacy DB

Recommended environment:
  LEGACY_MEDIA_ROOT            Read-only snapshot/path of legacy media files
  ARCHIVE_ONLY_APPROVAL_FILE   Signed archive-only approval JSON (required if
                               reconciliation lists archive_approval_required)
  MIGRATION_BATCH_ID           Stable batch id (default: ship-<timestamp>)
  MIGRATION_EVIDENCE_DIRECTORY Evidence output dir (default: migration-evidence/<batch>)
  BACKUP_DIRECTORY             Modern backup dir (default: <evidence>/modern-backups)
  PUBLIC_HEALTH_BASE_URL       Final HTTPS origin for verify (cutover)

Legacy writer freeze (optional, with --freeze-legacy-writers):
  LEGACY_SSH_HOST              e.g. utagadmin@197.255.126.246
  LEGACY_APP_DIR               e.g. /opt/utag_ug_website/UG-UTAG-Portal/utag_ug_archiver
  LEGACY_APP_COMPOSE           default: <LEGACY_APP_DIR>/docker-compose.app.yml

The script loads ./.env when present (without exporting secrets into the shell
history). It never drops or rewrites the legacy database.
EOF
}

phase_index() {
  local target="$1"
  local i
  for i in "${!PHASES[@]}"; do
    if [[ "${PHASES[$i]}" == "${target}" ]]; then
      printf '%s\n' "$i"
      return 0
    fi
  done
  return 1
}

should_run_phase() {
  local phase="$1"
  if [[ -n "${ONLY_PHASE}" ]]; then
    [[ "${phase}" == "${ONLY_PHASE}" ]]
    return
  fi
  local current from
  current="$(phase_index "${phase}")" || die "Unknown phase: ${phase}"
  from="$(phase_index "${FROM_PHASE}")" || die "Unknown --from phase: ${FROM_PHASE}"
  (( current >= from ))
}

load_dotenv() {
  if [[ -f "${ROOT_DIR}/.env" ]]; then
    log "Loading ${ROOT_DIR}/.env"
    set -a
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/.env"
    set +a
  fi
}

compose() {
  docker compose -f "${COMPOSE_FILE}" "$@"
}

wait_for_http() {
  local url="$1"
  local attempts="${2:-60}"
  local i
  for ((i = 1; i <= attempts; i++)); do
    if curl --fail --silent --show-error --max-time 5 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "Timed out waiting for ${url}"
}

sha_file() {
  local path="$1"
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${path}" > "${path}.sha256"
  else
    sha256sum "${path}" > "${path}.sha256"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --mode) MODE="$2"; shift 2 ;;
    --from) FROM_PHASE="$2"; shift 2 ;;
    --only) ONLY_PHASE="$2"; shift 2 ;;
    --confirm-write-freeze) CONFIRM_WRITE_FREEZE=1; shift ;;
    --confirm-go-live) CONFIRM_GO_LIVE=1; shift ;;
    --freeze-legacy-writers) FREEZE_LEGACY_WRITERS=1; shift ;;
    --skip-media) SKIP_MEDIA=1; shift ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "${MODE}" == "rehearsal" || "${MODE}" == "cutover" ]] || die "--mode must be rehearsal or cutover"

require_cmd docker
require_cmd curl
require_cmd python3
require_cmd pg_dump

load_dotenv

BATCH_ID="${MIGRATION_BATCH_ID:-ship-$(date -u +%Y%m%dT%H%M%SZ)}"
EVIDENCE_DIR="${MIGRATION_EVIDENCE_DIRECTORY:-migration-evidence/${BATCH_ID}}"
mkdir -p "${EVIDENCE_DIR}"
EVIDENCE_DIR="$(cd "${EVIDENCE_DIR}" && pwd)"
BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-${EVIDENCE_DIR}/modern-backups}"
LEGACY_BACKUP_DIR="${EVIDENCE_DIR}/legacy-backups"
mkdir -p "${BACKUP_DIRECTORY}" "${LEGACY_BACKUP_DIR}"

export MIGRATION_BATCH_ID="${BATCH_ID}"
export MIGRATION_EVIDENCE_DIRECTORY="${EVIDENCE_DIR}"
export BACKUP_DIRECTORY
export REQUIRE_MEDIA_MANIFEST="${REQUIRE_MEDIA_MANIFEST:-true}"
if [[ "${SKIP_MEDIA}" -eq 1 ]]; then
  unset LEGACY_MEDIA_ROOT || true
  export REQUIRE_MEDIA_MANIFEST=false
fi

if [[ "${MODE}" == "cutover" ]]; then
  [[ "${CONFIRM_WRITE_FREEZE}" -eq 1 ]] || die "Cutover requires --confirm-write-freeze"
  [[ "${ENVIRONMENT:-}" == "production" ]] || die "Cutover requires ENVIRONMENT=production in .env"
  [[ "${SESSION_COOKIE_SECURE:-}" == "true" ]] || die "Cutover requires SESSION_COOKIE_SECURE=true"
  [[ "${MALWARE_SCAN_REQUIRED:-}" == "true" ]] || die "Cutover requires MALWARE_SCAN_REQUIRED=true"
fi

log "Mode=${MODE} batch=${BATCH_ID}"
log "Evidence directory: ${EVIDENCE_DIR}"

phase_preflight() {
  log "=== PHASE: preflight ==="
  [[ -n "${LEGACY_DATABASE_URL:-}" ]] || die "LEGACY_DATABASE_URL is required"
  [[ -f "${ROOT_DIR}/.env" ]] || die "Create .env from .env.example before shipping"
  [[ -f "${ROOT_DIR}/${COMPOSE_FILE}" ]] || die "Missing ${COMPOSE_FILE}"

  if [[ -z "${PUBLIC_WEB_URL:-}" || "${PUBLIC_WEB_URL}" == *"localhost"* ]]; then
    if [[ "${MODE}" == "cutover" ]]; then
      die "Cutover requires PUBLIC_WEB_URL to be the final HTTPS origin"
    fi
    log "WARNING: PUBLIC_WEB_URL still looks local (${PUBLIC_WEB_URL:-unset})"
  fi

  if [[ "${MODE}" == "cutover" ]]; then
    [[ "${S3_ENDPOINT_URL:-}" != "http://minio:9000" ]] || die "Cutover rejects local MinIO endpoint"
    [[ "${CLAMAV_HOST:-}" != "clamav" ]] || die "Cutover rejects bundled ClamAV hostname"
    [[ -n "${SITE_DOMAIN:-}" && "${SITE_DOMAIN}" != "localhost" ]] || die "Cutover requires SITE_DOMAIN"
    [[ -n "${ACME_EMAIL:-}" ]] || die "Cutover requires ACME_EMAIL"
  fi

  if [[ -n "${LEGACY_MEDIA_ROOT:-}" ]]; then
    [[ -d "${LEGACY_MEDIA_ROOT}" ]] || die "LEGACY_MEDIA_ROOT does not exist: ${LEGACY_MEDIA_ROOT}"
  elif [[ "${REQUIRE_MEDIA_MANIFEST}" == "true" ]]; then
    die "LEGACY_MEDIA_ROOT is required unless you pass --skip-media"
  fi

  compose config --quiet
  log "Preflight passed"
}

phase_backup_legacy() {
  log "=== PHASE: backup-legacy ==="
  log "Creating checksummed dump of the legacy/production database (source is left intact)"

  if [[ "${FREEZE_LEGACY_WRITERS}" -eq 1 ]]; then
    [[ "${MODE}" == "cutover" ]] || die "--freeze-legacy-writers is only valid in cutover mode"
    [[ -n "${LEGACY_SSH_HOST:-}" ]] || die "LEGACY_SSH_HOST is required with --freeze-legacy-writers"
    local app_dir compose_file
    app_dir="${LEGACY_APP_DIR:-/opt/utag_ug_website/UG-UTAG-Portal/utag_ug_archiver}"
    compose_file="${LEGACY_APP_COMPOSE:-${app_dir}/docker-compose.app.yml}"
    require_cmd ssh
    log "Freezing legacy Django writers on ${LEGACY_SSH_HOST}"
    ssh "${LEGACY_SSH_HOST}" \
      "cd '${app_dir}' && docker compose -f '${compose_file}' stop web worker beat || docker compose -f '${compose_file}' stop web celery celery-beat || true"
    printf '%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" > "${EVIDENCE_DIR}/legacy-write-freeze.txt"
  fi

  local dump_file
  dump_file="${LEGACY_BACKUP_DIR}/legacy-${BATCH_ID}.dump"
  # Prefer custom format for restore drills; never touch the source DB schema.
  pg_dump \
    --dbname="${LEGACY_DATABASE_URL}" \
    --format=custom \
    --no-owner \
    --file="${dump_file}"
  sha_file "${dump_file}"
  log "Legacy database backup: ${dump_file}"

  if [[ -n "${LEGACY_MEDIA_ROOT:-}" ]]; then
    local media_list
    media_list="${LEGACY_BACKUP_DIR}/legacy-media-inventory-${BATCH_ID}.txt"
    (
      cd "${LEGACY_MEDIA_ROOT}"
      find . -type f | LC_ALL=C sort
    ) > "${media_list}"
    sha_file "${media_list}"
    log "Legacy media inventory: ${media_list}"
  fi
}

phase_start_stack() {
  log "=== PHASE: start-stack ==="
  if [[ "${MODE}" == "cutover" ]]; then
    log "Building and starting modern stack with production profile (Caddy waits for later go-live unless already healthy)"
    # Start data plane first; proxy comes up in go-live after gates pass.
    compose --profile production up -d --build postgres redis rabbitmq api worker scheduler web
  else
    log "Building and starting modern stack with local profile for rehearsal"
    compose --profile local up -d --build
  fi

  log "Waiting for API readiness"
  wait_for_http "${API_HEALTH_URL:-http://127.0.0.1:8000/health/ready}" 90
  log "Waiting for web health"
  wait_for_http "${WEB_HEALTH_URL:-http://127.0.0.1:3000/api/health}" 90
  compose ps
}

phase_migrate() {
  log "=== PHASE: migrate ==="
  log "Capturing and promoting legacy rows into the modern schema (legacy DB stays read-only/source)"
  export LEGACY_DATABASE_URL
  if [[ -n "${LEGACY_MEDIA_ROOT:-}" ]]; then
    export LEGACY_MEDIA_ROOT
  fi
  "${SCRIPT_DIR}/reconcile-legacy.sh"
  [[ -f "${EVIDENCE_DIR}/reconciliation.json" ]] || die "Missing reconciliation.json after migrate"
  log "Migration evidence written under ${EVIDENCE_DIR}"
}

phase_gates() {
  log "=== PHASE: gates ==="
  local approval="${ARCHIVE_ONLY_APPROVAL_FILE:-}"
  if [[ -z "${approval}" && -f "${EVIDENCE_DIR}/archive-only-approval.json" ]]; then
    approval="${EVIDENCE_DIR}/archive-only-approval.json"
  fi
  if [[ -z "${approval}" ]]; then
    log "No archive approval file provided yet; cutover-gates will fail if archive-only tables exist"
    log "Copy docs/examples/archive-only-approval.example.json and fill it in if required"
  fi

  export API_HEALTH_URL="${API_HEALTH_URL:-http://127.0.0.1:8000/health/ready}"
  export WEB_HEALTH_URL="${WEB_HEALTH_URL:-http://127.0.0.1:3000/api/health}"
  export MEDIA_MANIFEST_FILE="${MEDIA_MANIFEST_FILE:-${EVIDENCE_DIR}/media-manifest.json}"

  if [[ -n "${approval}" ]]; then
    "${SCRIPT_DIR}/cutover-gates.sh" "${EVIDENCE_DIR}/reconciliation.json" "${approval}"
  else
    "${SCRIPT_DIR}/cutover-gates.sh" "${EVIDENCE_DIR}/reconciliation.json"
  fi
}

phase_backup_modern() {
  log "=== PHASE: backup-modern ==="
  local dump_file
  dump_file="${BACKUP_DIRECTORY}/ug-utag-${BATCH_ID}.dump"

  compose exec -T postgres pg_dump \
    --username "${POSTGRES_USER:-utag}" \
    --dbname "${POSTGRES_DB:-utag_portal}" \
    --format custom \
    --no-owner \
    --file /tmp/portal.dump
  compose cp postgres:/tmp/portal.dump "${dump_file}"
  compose exec -T postgres rm -f /tmp/portal.dump
  sha_file "${dump_file}"
  log "Modern database backup: ${dump_file}"

  if compose --profile local config --services 2>/dev/null | grep -qx minio-init; then
    if compose ps --status running --services 2>/dev/null | grep -qx minio; then
      log "Local MinIO detected; mirroring object backup via backup-modern.sh helpers"
      OBJECT_BACKUP_NAME="ug-utag-${BATCH_ID}-objects"
      mkdir -p "${BACKUP_DIRECTORY}/${OBJECT_BACKUP_NAME}"
      compose run --rm --no-deps -T \
        -e OBJECT_BACKUP_NAME="${OBJECT_BACKUP_NAME}" \
        -v "${BACKUP_DIRECTORY}:/backup" \
        --entrypoint /bin/sh \
        minio-init -ec '
          mc alias set source http://minio:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
          mc mirror --overwrite "source/$MEDIA_BUCKET" "/backup/$OBJECT_BACKUP_NAME"
        ' || log "WARNING: object mirror skipped/failed; database backup remains"
    else
      log "Object storage backup skipped (external S3 must be backed up by your platform process)"
    fi
  else
    log "Object storage backup skipped (external S3 must be backed up by your platform process)"
  fi
}

phase_go_live() {
  log "=== PHASE: go-live ==="
  if [[ "${MODE}" != "cutover" ]]; then
    log "Rehearsal mode: skipping production edge / traffic switch"
    log "When ready: re-run with --mode cutover --confirm-write-freeze --confirm-go-live"
    return 0
  fi
  [[ "${CONFIRM_GO_LIVE}" -eq 1 ]] || die "go-live requires --confirm-go-live"

  log "Starting Caddy production edge"
  compose --profile production up -d --build proxy
  wait_for_http "https://${SITE_DOMAIN}/health/ready" 90 || \
    wait_for_http "${PUBLIC_HEALTH_BASE_URL:-https://${SITE_DOMAIN}}/health/ready" 90

  cat > "${EVIDENCE_DIR}/go-live.txt" <<EOF
go_live_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
site_domain=${SITE_DOMAIN}
public_web_url=${PUBLIC_WEB_URL}
batch_id=${BATCH_ID}
note=Legacy DB was not deleted. Keep Django read-only until decommission sign-off.
EOF
  log "Go-live recorded in ${EVIDENCE_DIR}/go-live.txt"
  log "IMPORTANT: Keep the legacy Django app read-only. Do not reopen writes."
}

phase_verify() {
  log "=== PHASE: verify ==="
  local api_url web_url public_base
  api_url="${API_HEALTH_URL:-http://127.0.0.1:8000/health/ready}"
  web_url="${WEB_HEALTH_URL:-http://127.0.0.1:3000/api/health}"
  public_base="${PUBLIC_HEALTH_BASE_URL:-}"

  curl --fail --silent --show-error "${api_url}" >/dev/null
  curl --fail --silent --show-error "${web_url}" >/dev/null
  log "Loopback API/web health checks passed"

  if [[ -n "${public_base}" ]]; then
    curl --fail --silent --show-error "${public_base}/health/live" >/dev/null
    curl --fail --silent --show-error "${public_base}/health/ready" >/dev/null
    curl --fail --silent --show-error "${public_base}/api/health" >/dev/null
    log "Public origin health checks passed for ${public_base}"
  elif [[ "${MODE}" == "cutover" && -n "${SITE_DOMAIN:-}" && "${SITE_DOMAIN}" != "localhost" ]]; then
    curl --fail --silent --show-error "https://${SITE_DOMAIN}/health/ready" >/dev/null || \
      log "WARNING: public https://${SITE_DOMAIN}/health/ready not reachable yet (DNS/TLS may still be propagating)"
  fi

  compose ps
  log "Ship complete for batch ${BATCH_ID}"
  log "Evidence: ${EVIDENCE_DIR}"
  log "Legacy dump: ${LEGACY_BACKUP_DIR}"
  log "Modern dump: ${BACKUP_DIRECTORY}"
  if [[ "${MODE}" == "rehearsal" ]]; then
    log "Next: review reconciliation.json, sign archive-only approval if needed, then run cutover mode."
  else
    log "Next: smoke-test public/dashboard journeys and keep legacy read-only through the confidence window."
  fi
}

run_phase() {
  local phase="$1"
  case "${phase}" in
    preflight) phase_preflight ;;
    backup-legacy) phase_backup_legacy ;;
    start-stack) phase_start_stack ;;
    migrate) phase_migrate ;;
    gates) phase_gates ;;
    backup-modern) phase_backup_modern ;;
    go-live) phase_go_live ;;
    verify) phase_verify ;;
    *) die "Unknown phase: ${phase}" ;;
  esac
}

for phase in "${PHASES[@]}"; do
  if should_run_phase "${phase}"; then
    run_phase "${phase}"
  else
    log "Skipping phase: ${phase}"
  fi
done
