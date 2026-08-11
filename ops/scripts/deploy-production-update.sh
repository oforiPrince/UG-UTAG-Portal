#!/usr/bin/env bash
# Deploy one immutable commit of the modern UG UTAG portal on the production host.
#
# This is for routine updates after the modern platform is already live. The
# first migration/cutover remains the responsibility of ship-production.sh.
#
# Data-safety contract:
#   - a verified PostgreSQL dump is created before migrations;
#   - object storage is mirrored to a separate backup filesystem by default;
#   - named Docker volumes are never removed or pruned;
#   - no `docker compose down`, `docker system prune`, or volume prune is used;
#   - cleanup is limited to stopped containers from this Compose project,
#     dangling images, old rollback tags, old release worktrees, and aged build
#     cache.

set -Eeuo pipefail
umask 077

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

usage() {
  cat <<'EOF'
Usage:
  RELEASE_COMMIT=<40-char-sha> BACKUP_DIRECTORY=/mounted/backup/path \
    ops/scripts/deploy-production-update.sh [--dry-run]

Required:
  RELEASE_COMMIT             Exact commit to deploy.
  BACKUP_DIRECTORY           Existing backup directory on a separate filesystem.

Common configuration:
  PRODUCTION_BRANCH          Remote branch containing RELEASE_COMMIT (deploy_v2).
  SOURCE_REPO                Existing server Git checkout.
  SHARED_ENV_FILE            Existing production .env; it is never overwritten.
  RELEASE_ROOT               Immutable release worktrees.
  DEPLOY_STATE_ROOT          Deployment logs/evidence/lock.
  PUBLIC_HEALTH_BASE_URL     Final HTTPS origin.
  OBJECT_BACKUP_MODE         mirror (default) or external.
  OBJECT_BACKUP_SENTINEL     Fresh success marker required for external mode.
  REQUIRE_GOOGLE_DRIVE       Require secure Drive OAuth configuration (true).
  ALLOWED_PUBLIC_TCP_PORTS   Host TCP allowlist (22,80,443).
  ALLOWED_PUBLIC_UDP_PORTS   Host UDP allowlist (443).
  ALLOW_SAME_FILESYSTEM_BACKUP=true
                             Emergency override; weakens disaster recovery.
  MIN_FREE_GB_BEFORE_BUILD   Required release filesystem headroom (10).
  MIN_FREE_GB_BACKUP         Required backup-filesystem headroom (5).
  KEEP_RELEASES              Successful release worktrees retained (3).
  KEEP_ROLLBACK_IMAGES       Previous image tags retained (2).
  BUILDER_CACHE_MAX_AGE      Docker build-cache age retained (168h).

The script intentionally has no option that deletes Docker volumes.
EOF
}

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

RELEASE_COMMIT="${RELEASE_COMMIT:-}"
PRODUCTION_BRANCH="${PRODUCTION_BRANCH:-deploy_v2}"
SOURCE_REPO="${SOURCE_REPO:-/opt/utag_ug_website/UG-UTAG-Portal-modern}"
SHARED_ENV_FILE="${SHARED_ENV_FILE:-${SOURCE_REPO}/.env}"
RELEASE_ROOT="${RELEASE_ROOT:-/opt/utag_ug_website/releases}"
DEPLOY_STATE_ROOT="${DEPLOY_STATE_ROOT:-/opt/utag_ug_website/deploy-state}"
BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-}"
PUBLIC_HEALTH_BASE_URL="${PUBLIC_HEALTH_BASE_URL:-https://utag.ug.edu.gh}"
OBJECT_BACKUP_MODE="${OBJECT_BACKUP_MODE:-mirror}"
OBJECT_BACKUP_SENTINEL="${OBJECT_BACKUP_SENTINEL:-}"
MAX_OBJECT_BACKUP_AGE_HOURS="${MAX_OBJECT_BACKUP_AGE_HOURS:-24}"
REQUIRE_GOOGLE_DRIVE="${REQUIRE_GOOGLE_DRIVE:-true}"
ALLOWED_PUBLIC_TCP_PORTS="${ALLOWED_PUBLIC_TCP_PORTS:-22,80,443}"
ALLOWED_PUBLIC_UDP_PORTS="${ALLOWED_PUBLIC_UDP_PORTS:-443}"
ALLOW_SAME_FILESYSTEM_BACKUP="${ALLOW_SAME_FILESYSTEM_BACKUP:-false}"
MIN_FREE_GB_BEFORE_BUILD="${MIN_FREE_GB_BEFORE_BUILD:-10}"
MIN_FREE_GB_AFTER_DEPLOY="${MIN_FREE_GB_AFTER_DEPLOY:-5}"
MIN_FREE_GB_BACKUP="${MIN_FREE_GB_BACKUP:-5}"
KEEP_RELEASES="${KEEP_RELEASES:-3}"
KEEP_ROLLBACK_IMAGES="${KEEP_ROLLBACK_IMAGES:-2}"
BUILDER_CACHE_MAX_AGE="${BUILDER_CACHE_MAX_AGE:-168h}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-ug-utag-portal}"

[[ "${RELEASE_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || die "RELEASE_COMMIT must be a full lowercase 40-character Git SHA"
[[ "${PRODUCTION_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]] || die "Invalid PRODUCTION_BRANCH"
[[ "${PUBLIC_HEALTH_BASE_URL}" =~ ^https://[^/]+/?$ ]] || die "PUBLIC_HEALTH_BASE_URL must be an HTTPS origin"
[[ "${MIN_FREE_GB_BEFORE_BUILD}" =~ ^[0-9]+$ ]] || die "MIN_FREE_GB_BEFORE_BUILD must be an integer"
[[ "${MIN_FREE_GB_AFTER_DEPLOY}" =~ ^[0-9]+$ ]] || die "MIN_FREE_GB_AFTER_DEPLOY must be an integer"
[[ "${MIN_FREE_GB_BACKUP}" =~ ^[0-9]+$ ]] || die "MIN_FREE_GB_BACKUP must be an integer"
[[ "${KEEP_RELEASES}" =~ ^[1-9][0-9]*$ ]] || die "KEEP_RELEASES must be positive"
[[ "${KEEP_ROLLBACK_IMAGES}" =~ ^[1-9][0-9]*$ ]] || die "KEEP_ROLLBACK_IMAGES must be positive"
[[ "${OBJECT_BACKUP_MODE}" == "mirror" || "${OBJECT_BACKUP_MODE}" == "external" ]] || \
  die "OBJECT_BACKUP_MODE must be mirror or external"
[[ "${REQUIRE_GOOGLE_DRIVE}" == "true" || "${REQUIRE_GOOGLE_DRIVE}" == "false" ]] || \
  die "REQUIRE_GOOGLE_DRIVE must be true or false"
[[ "${ALLOWED_PUBLIC_TCP_PORTS}" =~ ^[0-9]+(,[0-9]+)*$ ]] || \
  die "ALLOWED_PUBLIC_TCP_PORTS must be a comma-separated list of port numbers"
[[ "${ALLOWED_PUBLIC_UDP_PORTS}" =~ ^[0-9]+(,[0-9]+)*$ ]] || \
  die "ALLOWED_PUBLIC_UDP_PORTS must be a comma-separated list of port numbers"

for cmd in bash curl df docker findmnt flock git python3 sha256sum ss stat tee; do
  require_cmd "${cmd}"
done

[[ -d "${SOURCE_REPO}" ]] || die "SOURCE_REPO does not exist: ${SOURCE_REPO}"
[[ -f "${SHARED_ENV_FILE}" ]] || die "Production environment file is missing: ${SHARED_ENV_FILE}"
[[ -n "${BACKUP_DIRECTORY}" && -d "${BACKUP_DIRECTORY}" ]] || \
  die "BACKUP_DIRECTORY must already exist on a protected backup filesystem"

mkdir -p "${RELEASE_ROOT}" "${DEPLOY_STATE_ROOT}/evidence"
chmod 700 "${DEPLOY_STATE_ROOT}" "${DEPLOY_STATE_ROOT}/evidence" "${BACKUP_DIRECTORY}"
exec 9>"${DEPLOY_STATE_ROOT}/production-deploy.lock"
flock -n 9 || die "Another production deployment is already running"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
short_commit="${RELEASE_COMMIT:0:12}"
deploy_id="${timestamp}-${short_commit}"
evidence_directory="${DEPLOY_STATE_ROOT}/evidence/${deploy_id}"
release_directory="${RELEASE_ROOT}/${deploy_id}"
mkdir -p "${evidence_directory}"
chmod 700 "${evidence_directory}"
exec > >(tee -a "${evidence_directory}/deploy.log") 2>&1

release_prepared=0
compose_ready=0
services_replaced=0
on_error() {
  local status=$?
  set +e
  log "Deployment failed with status ${status}. Persistent volumes and backups were not removed."
  if [[ "${compose_ready}" -eq 1 ]]; then
    compose ps > "${evidence_directory}/compose-ps-failure.txt" 2>&1
    compose logs --no-color --tail=200 api web worker scheduler > \
      "${evidence_directory}/service-logs-failure.txt" 2>&1
  fi
  if [[ "${release_prepared}" -eq 1 && "${services_replaced}" -eq 0 ]]; then
    git -C "${SOURCE_REPO}" worktree remove --force "${release_directory}" >/dev/null 2>&1 || true
    git -C "${SOURCE_REPO}" worktree prune >/dev/null 2>&1 || true
    log "Removed the unused failed release worktree; deployment evidence was retained."
  fi
  log "Failure evidence: ${evidence_directory}"
  exit "${status}"
}
trap on_error ERR

env_value() {
  local key="$1"
  python3 - "${SHARED_ENV_FILE}" "${key}" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
key = sys.argv[2]
result = ""
for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    if name.strip() != key:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    result = value
print(result)
PY
}

free_gb() {
  df -Pk "$1" | awk 'NR==2 {print int($4 / 1024 / 1024)}'
}

assert_host_network_exposure() {
  local tcp_file="${evidence_directory}/host-tcp-listeners.txt"
  local udp_file="${evidence_directory}/host-udp-listeners.txt"
  ss -H -lnt > "${tcp_file}"
  ss -H -lnu > "${udp_file}"
  python3 - \
    "${tcp_file}" "${ALLOWED_PUBLIC_TCP_PORTS}" \
    "${udp_file}" "${ALLOWED_PUBLIC_UDP_PORTS}" <<'PY'
from ipaddress import ip_address
from pathlib import Path
import sys

unexpected: list[str] = []
for protocol, path_arg, allowed_arg in (
    ("TCP", sys.argv[1], sys.argv[2]),
    ("UDP", sys.argv[3], sys.argv[4]),
):
    allowed = {int(value) for value in allowed_arg.split(",")}
    for line in Path(path_arg).read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        endpoint = fields[3]
        address, raw_port = endpoint.rsplit(":", 1)
        if not raw_port.isdigit():
            continue
        address = address.strip("[]")
        try:
            is_loopback = ip_address(address).is_loopback
        except ValueError:
            is_loopback = False
        port = int(raw_port)
        finding = f"{protocol}/{port}"
        if not is_loopback and port not in allowed and finding not in unexpected:
            unexpected.append(finding)
if unexpected:
    listeners = ", ".join(sorted(unexpected))
    raise SystemExit(
        f"Unexpected non-loopback listeners: {listeners}. Bind them to loopback, "
        "protect them on a private network, or explicitly review the allowlist."
    )
PY
}

compose() {
  docker compose \
    --project-name "${COMPOSE_PROJECT_NAME}" \
    --env-file "${SHARED_ENV_FILE}" \
    -f "${release_directory}/docker-compose.yml" \
    --profile production \
    "$@"
}

wait_for_http() {
  local url="$1" attempts="${2:-90}" i
  for ((i = 1; i <= attempts; i++)); do
    if curl --fail --silent --show-error --max-time 8 "${url}" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "Timed out waiting for ${url}"
}

wait_for_service() {
  local service="$1" attempts="${2:-90}" id status i
  for ((i = 1; i <= attempts; i++)); do
    id="$(compose ps -q "${service}" 2>/dev/null || true)"
    if [[ -n "${id}" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${id}" 2>/dev/null || true)"
      if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
        return 0
      fi
      [[ "${status}" != "unhealthy" && "${status}" != "exited" && "${status}" != "dead" ]] || \
        die "Service ${service} entered state ${status}"
    fi
    sleep 2
  done
  die "Timed out waiting for service ${service}"
}

tag_current_image() {
  local repository="$1" source_tag="$2"
  if docker image inspect "${repository}:${source_tag}" >/dev/null 2>&1; then
    docker image tag "${repository}:${source_tag}" "${repository}:rollback-${deploy_id}"
    log "Retained rollback image ${repository}:rollback-${deploy_id}"
  fi
}

prune_old_rollback_tags() {
  local repository="$1" tag index=0
  while IFS= read -r tag; do
    [[ -n "${tag}" ]] || continue
    index=$((index + 1))
    if (( index > KEEP_ROLLBACK_IMAGES )); then
      docker image rm "${repository}:${tag}" >/dev/null 2>&1 || true
    fi
  done < <(docker image ls "${repository}" --format '{{.Tag}}' | grep '^rollback-' | LC_ALL=C sort -r)
}

log "Starting production update ${deploy_id}"
log "Release commit: ${RELEASE_COMMIT}"

env_mode="$(stat -c '%a' "${SHARED_ENV_FILE}")"
(( (8#${env_mode} & 077) == 0 )) || die "${SHARED_ENV_FILE} must not be readable by group or others (use chmod 600)"
python3 - "${SHARED_ENV_FILE}" "${PUBLIC_HEALTH_BASE_URL%/}" "${REQUIRE_GOOGLE_DRIVE}" <<'PY'
from ipaddress import ip_network
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

path = Path(sys.argv[1])
public_origin = sys.argv[2]
require_google_drive = sys.argv[3] == "true"
values: dict[str, str] = {}
for raw in path.read_text(encoding="utf-8", errors="strict").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    name, value = line.split("=", 1)
    name = name.strip()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    values[name] = value

def need(name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} must be configured in production")
    return value

def require_value(name: str, expected: str) -> None:
    if values.get(name, "").casefold() != expected.casefold():
        raise SystemExit(f"{name} must equal {expected} in production")

def secret(name: str, minimum: int) -> str:
    value = need(name)
    lowered = value.casefold()
    if len(value) < minimum:
        raise SystemExit(f"{name} must contain at least {minimum} characters")
    if any(marker in lowered for marker in ("change-me", "replace-me", "replace-with", "development-only")):
        raise SystemExit(f"{name} contains a placeholder")
    return value

require_value("ENVIRONMENT", "production")
require_value("SESSION_COOKIE_SECURE", "true")
require_value("MALWARE_SCAN_REQUIRED", "true")
if values.get("DEBUG", "false").casefold() != "false":
    raise SystemExit("DEBUG must be false in production")

secret("APP_SECRET_KEY", 32)
secret("POSTGRES_PASSWORD", 24)
secret("RABBITMQ_DEFAULT_PASS", 24)
secret("S3_SECRET_KEY", 24)

parsed_public = urlsplit(public_origin)
if parsed_public.scheme != "https" or not parsed_public.hostname:
    raise SystemExit("The public health origin must be absolute HTTPS")
if need("PUBLIC_WEB_URL").rstrip("/") != public_origin:
    raise SystemExit("PUBLIC_WEB_URL must match PUBLIC_HEALTH_BASE_URL")
if need("SITE_DOMAIN") != parsed_public.hostname:
    raise SystemExit("SITE_DOMAIN must match the production public hostname")

origins = json.loads(need("ALLOWED_ORIGINS"))
hosts = json.loads(need("ALLOWED_HOSTS"))
if not origins or any(not value.startswith("https://") or "*" in value for value in origins):
    raise SystemExit("ALLOWED_ORIGINS must contain only explicit HTTPS origins")
if not hosts or any("*" in value for value in hosts):
    raise SystemExit("ALLOWED_HOSTS must not be empty or contain wildcards")
if public_origin not in origins or parsed_public.hostname not in hosts:
    raise SystemExit("The production public origin and hostname must be allowed")

trusted_proxies = json.loads(need("TRUSTED_PROXY_CIDRS"))
if not trusted_proxies:
    raise SystemExit("TRUSTED_PROXY_CIDRS must not be empty")
for network in trusted_proxies:
    ip_network(network)

field_key_version = need("FIELD_ENCRYPTION_KEY_VERSION")
field_keys = json.loads(need("FIELD_ENCRYPTION_KEYS"))
if field_key_version not in field_keys or len(field_keys[field_key_version]) < 32:
    raise SystemExit("The active field encryption key must contain at least 32 characters")
if any(
    marker in field_keys[field_key_version].casefold()
    for marker in ("change-me", "replace-me", "replace-with", "development-only")
):
    raise SystemExit("The active field encryption key contains a placeholder")

s3_endpoint = need("S3_ENDPOINT_URL")
if s3_endpoint == "http://minio:9000":
    raise SystemExit("Production must use the maintained S3 endpoint alias")
s3_encryption = need("S3_SERVER_SIDE_ENCRYPTION")
if s3_encryption not in {"AES256", "aws:kms"}:
    raise SystemExit("S3_SERVER_SIDE_ENCRYPTION must be AES256 or aws:kms")
if s3_encryption == "aws:kms":
    need("S3_KMS_KEY_ID")
if need("CLAMAV_HOST") == "clamav":
    raise SystemExit("Production must use the maintained malware scanner alias")
need("SMTP_HOST")

if values.get("METRICS_ENABLED", "true").casefold() == "true":
    secret("METRICS_BEARER_TOKEN", 32)
if values.get("DEMO_DATA_PASSWORD", "").strip():
    raise SystemExit("DEMO_DATA_PASSWORD must not be configured in production")

google_client_id = values.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
google_client_secret = values.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
if bool(google_client_id) != bool(google_client_secret):
    raise SystemExit("Google OAuth client ID and secret must be configured together")
if require_google_drive and not google_client_id:
    raise SystemExit("Google Drive OAuth is required for this production deployment")
if google_client_id:
    secret("GOOGLE_OAUTH_CLIENT_SECRET", 16)
    expected_redirect = f"{public_origin}/api/v1/integrations/google-drive/callback"
    if need("GOOGLE_OAUTH_REDIRECT_URI") != expected_redirect:
        raise SystemExit(f"GOOGLE_OAUTH_REDIRECT_URI must equal {expected_redirect}")
PY

assert_host_network_exposure

root_source="$(findmnt -n -o SOURCE -T /)"
backup_source="$(findmnt -n -o SOURCE -T "${BACKUP_DIRECTORY}")"
if [[ "${root_source}" == "${backup_source}" && "${ALLOW_SAME_FILESYSTEM_BACKUP}" != "true" ]]; then
  die "BACKUP_DIRECTORY is on the server root filesystem. Mount separate backup storage or explicitly set ALLOW_SAME_FILESYSTEM_BACKUP=true."
fi
backup_free="$(free_gb "${BACKUP_DIRECTORY}")"
(( backup_free >= MIN_FREE_GB_BACKUP )) || \
  die "Only ${backup_free} GiB is free on the backup filesystem; ${MIN_FREE_GB_BACKUP} GiB is required"

log "Fetching ${PRODUCTION_BRANCH} without changing the running checkout"
git -C "${SOURCE_REPO}" fetch --prune origin "${PRODUCTION_BRANCH}"
resolved_commit="$(git -C "${SOURCE_REPO}" rev-parse "${RELEASE_COMMIT}^{commit}")"
[[ "${resolved_commit}" == "${RELEASE_COMMIT}" ]] || die "Release commit could not be resolved exactly"
git -C "${SOURCE_REPO}" merge-base --is-ancestor "${RELEASE_COMMIT}" "origin/${PRODUCTION_BRANCH}" || \
  die "RELEASE_COMMIT is not on origin/${PRODUCTION_BRANCH}"
[[ "$(git -C "${SOURCE_REPO}" rev-parse "origin/${PRODUCTION_BRANCH}")" == "${RELEASE_COMMIT}" ]] || \
  die "RELEASE_COMMIT is not the current origin/${PRODUCTION_BRANCH} tip"

git -C "${SOURCE_REPO}" worktree add --detach "${release_directory}" "${RELEASE_COMMIT}"
release_prepared=1
# The script's restrictive umask protects deployment evidence and backups, but
# Git-created checkout files must remain readable inside non-root build images.
# Preserve executable bits while restoring normal read/search access to this
# immutable source-only worktree before Docker copies files into image layers.
chmod -R a+rX "${release_directory}"
ln -s "${SHARED_ENV_FILE}" "${release_directory}/.env"
compose_ready=1

compose config --quiet
compose run --rm --no-deps production-check

for service in postgres redis rabbitmq; do
  wait_for_service "${service}" 10
done

if [[ "${DRY_RUN}" -eq 1 ]]; then
  log "Dry run passed: commit, secure configuration, Compose configuration, data services, backup mount, and disk checks are valid."
  git -C "${SOURCE_REPO}" worktree remove --force "${release_directory}"
  git -C "${SOURCE_REPO}" worktree prune
  trap - ERR
  exit 0
fi

# Safe pre-build cleanup. This intentionally excludes every Docker volume.
docker container prune --force --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" >/dev/null
docker image prune --force >/dev/null
docker builder prune --force --filter "until=${BUILDER_CACHE_MAX_AGE}" >/dev/null

available_before="$(free_gb "${RELEASE_ROOT}")"
(( available_before >= MIN_FREE_GB_BEFORE_BUILD )) || \
  die "Only ${available_before} GiB is free; ${MIN_FREE_GB_BEFORE_BUILD} GiB is required before a build"

log "Creating verified pre-deployment PostgreSQL backup"
database_backup_directory="${BACKUP_DIRECTORY}/database"
mkdir -p "${database_backup_directory}"
chmod 700 "${database_backup_directory}"
database_name="ug-utag-predeploy-${deploy_id}.dump"
database_backup="${database_backup_directory}/${database_name}"
container_dump="/tmp/${database_name}"
compose exec -T postgres pg_dump \
  --username "$(env_value POSTGRES_USER)" \
  --dbname "$(env_value POSTGRES_DB)" \
  --format custom \
  --no-owner \
  --file "${container_dump}"
compose exec -T postgres test -s "${container_dump}"
compose exec -T postgres pg_restore --list "${container_dump}" >/dev/null
compose cp "postgres:${container_dump}" "${database_backup}.partial"
compose exec -T postgres rm -f "${container_dump}"
mv "${database_backup}.partial" "${database_backup}"
sha256sum "${database_backup}" > "${database_backup}.sha256"
log "Verified database backup: ${database_backup}"

if [[ "${OBJECT_BACKUP_MODE}" == "mirror" ]]; then
  log "Incrementally mirroring object storage to the protected backup filesystem"
  mkdir -p "${BACKUP_DIRECTORY}/object-mirror"
  compose run --rm --no-deps -T \
    -e BACKUP_S3_ENDPOINT="$(env_value S3_ENDPOINT_URL)" \
    -v "${BACKUP_DIRECTORY}:/backup" \
    --entrypoint /bin/sh \
    minio-init -ec '
      mc alias set source "$BACKUP_S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null
      mc mirror --overwrite "source/$MEDIA_BUCKET" /backup/object-mirror
    '
  date -u +'%Y-%m-%dT%H:%M:%SZ' > "${BACKUP_DIRECTORY}/objects-last-success"
  find "${BACKUP_DIRECTORY}/object-mirror" -type f -printf '%s\n' | \
    awk '{count += 1; bytes += $1} END {printf "file_count=%d\ntotal_bytes=%d\n", count, bytes}' > \
    "${evidence_directory}/object-backup-summary.txt"
else
  [[ -n "${OBJECT_BACKUP_SENTINEL}" && -f "${OBJECT_BACKUP_SENTINEL}" ]] || \
    die "External object backup mode requires OBJECT_BACKUP_SENTINEL"
  python3 - "${OBJECT_BACKUP_SENTINEL}" "${MAX_OBJECT_BACKUP_AGE_HOURS}" <<'PY'
from pathlib import Path
import sys
import time

path = Path(sys.argv[1])
max_age_seconds = int(sys.argv[2]) * 3600
age = time.time() - path.stat().st_mtime
if age < 0 or age > max_age_seconds:
    raise SystemExit(f"Object backup sentinel is stale ({age / 3600:.1f} hours old)")
PY
  log "Recent externally managed object backup was verified"
fi

{
  printf 'deploy_id=%s\n' "${deploy_id}"
  printf 'release_commit=%s\n' "${RELEASE_COMMIT}"
  printf 'database_backup=%s\n' "${database_backup}"
  printf 'database_backup_sha256=%s\n' "$(cut -d' ' -f1 "${database_backup}.sha256")"
  printf 'previous_api_image=%s\n' "$(docker image inspect --format '{{.Id}}' ug-utag-portal-api:latest 2>/dev/null || true)"
  printf 'previous_web_image=%s\n' "$(docker image inspect --format '{{.Id}}' ug-utag-portal-web:latest 2>/dev/null || true)"
} > "${evidence_directory}/release-metadata.txt"
compose ps > "${evidence_directory}/compose-ps-before.txt"

tag_current_image ug-utag-portal-api latest
tag_current_image ug-utag-portal-web latest
tag_current_image ug-utag-portal-caddy 2.11.4
tag_current_image ug-utag-portal-postgres 18.4

log "Building release images"
compose build --pull postgres api web proxy

log "Applying forward-only migrations before replacing application containers"
compose run --rm --no-deps api alembic upgrade head
compose run --rm --no-deps api alembic check

log "Starting the production profile without removing persistent volumes"
services_replaced=1
compose up -d --no-build --remove-orphans

for service in postgres redis rabbitmq api web worker; do
  wait_for_service "${service}" 90
done
wait_for_service scheduler 45
wait_for_service proxy 45

api_host_port="$(env_value API_HOST_PORT)"
web_host_port="$(env_value WEB_HOST_PORT)"
api_host_port="${api_host_port:-8000}"
web_host_port="${web_host_port:-3000}"
wait_for_http "http://127.0.0.1:${api_host_port}/health/ready" 90
wait_for_http "http://127.0.0.1:${web_host_port}/api/health" 90
public_base="${PUBLIC_HEALTH_BASE_URL%/}"
wait_for_http "${public_base}/health/ready" 90
wait_for_http "${public_base}/api/health" 90

for binding in \
  "postgres:5432" \
  "redis:6379" \
  "rabbitmq:5672" \
  "api:8000" \
  "web:3000" \
  "minio:9000"; do
  service="${binding%%:*}"
  port="${binding##*:}"
  published="$(compose port "${service}" "${port}" 2>/dev/null || true)"
  if [[ -n "${published}" && "${published}" != 127.0.0.1:* && "${published}" != '[::1]:'* ]]; then
    die "Sensitive service ${service}:${port} is not loopback-bound: ${published}"
  fi
done

headers_file="${evidence_directory}/public-headers.txt"
curl --fail --silent --show-error --dump-header "${headers_file}" --output /dev/null "${public_base}/"
grep -qi '^strict-transport-security:' "${headers_file}" || die "Public origin is missing HSTS"
grep -qi '^x-content-type-options:[[:space:]]*nosniff' "${headers_file}" || die "Public origin is missing X-Content-Type-Options: nosniff"
assert_host_network_exposure

temporary_link="${DEPLOY_STATE_ROOT}/current.new"
rm -f "${temporary_link}"
ln -s "${release_directory}" "${temporary_link}"
mv -Tf "${temporary_link}" "${DEPLOY_STATE_ROOT}/current"

compose ps > "${evidence_directory}/compose-ps-after.txt"
docker system df > "${evidence_directory}/docker-system-df-before-cleanup.txt"

# Cleanup is deliberately scoped and never includes volumes.
docker container prune --force --filter "label=com.docker.compose.project=${COMPOSE_PROJECT_NAME}" >/dev/null
docker image prune --force >/dev/null
docker builder prune --force --filter "until=${BUILDER_CACHE_MAX_AGE}" >/dev/null
for repository in ug-utag-portal-api ug-utag-portal-web ug-utag-portal-caddy ug-utag-portal-postgres; do
  prune_old_rollback_tags "${repository}"
done

mapfile -t release_directories < <(find "${RELEASE_ROOT}" -mindepth 1 -maxdepth 1 -type d -print | LC_ALL=C sort -r)
for ((index = KEEP_RELEASES; index < ${#release_directories[@]}; index++)); do
  old_release="${release_directories[$index]}"
  [[ "${old_release}" != "${release_directory}" ]] || continue
  git -C "${SOURCE_REPO}" worktree remove --force "${old_release}" || true
done
git -C "${SOURCE_REPO}" worktree prune

available_after="$(free_gb "${RELEASE_ROOT}")"
if (( available_after < MIN_FREE_GB_AFTER_DEPLOY )); then
  log "Disk headroom is low; pruning build cache older than 24 hours"
  docker builder prune --all --force --filter until=24h >/dev/null
  docker image prune --force >/dev/null
  available_after="$(free_gb "${RELEASE_ROOT}")"
fi
(( available_after >= MIN_FREE_GB_AFTER_DEPLOY )) || \
  die "Deployment is healthy, but disk headroom is only ${available_after} GiB"

docker system df > "${evidence_directory}/docker-system-df-after-cleanup.txt"
df -h "${RELEASE_ROOT}" "${BACKUP_DIRECTORY}" > "${evidence_directory}/filesystem-usage.txt"

trap - ERR
log "Production update ${deploy_id} completed successfully"
log "Release: ${release_directory}"
log "Evidence: ${evidence_directory}"
log "Database backup: ${database_backup}"
log "Persistent Docker volumes were not modified or pruned"
