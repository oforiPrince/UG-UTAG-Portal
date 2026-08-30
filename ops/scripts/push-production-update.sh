#!/usr/bin/env bash
# Push the current immutable commit and invoke deploy-production-update.sh on
# the production host. This wrapper refuses dirty or non-fast-forward releases.

set -Eeuo pipefail
umask 077

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

usage() {
  cat <<'EOF'
Usage:
  PRODUCTION_HOST=utagadmin@server \
  BACKUP_DIRECTORY=/mounted/backup/path \
  ops/scripts/push-production-update.sh --deploy

Options:
  --deploy       Required acknowledgement for a real push and deployment.
  --dry-run      Preflight; never pushes, backs up, builds, migrates, or restarts.
  --no-push      Deploy a commit already present at the production branch tip.
  -h, --help     Show this help.

Environment:
  PRODUCTION_HOST            Required SSH destination.
  PRODUCTION_BRANCH          Destination branch (deploy_v2).
  BACKUP_DIRECTORY           Required path as seen on the production host.
  REMOTE_SOURCE_REPO         Server Git checkout.
  REMOTE_SHARED_ENV_FILE     Server production .env.
  PUBLIC_HEALTH_BASE_URL     Final HTTPS origin.
  OBJECT_BACKUP_MODE         mirror (default) or external.
  OBJECT_BACKUP_SENTINEL     Required in external mode.
  REQUIRE_GOOGLE_DRIVE       Require secure Drive OAuth configuration (true).
  ALLOWED_PUBLIC_TCP_PORTS   Host TCP allowlist (22,80,443).
  ALLOWED_PUBLIC_UDP_PORTS   Host UDP allowlist (443).
  ALLOW_SAME_FILESYSTEM_BACKUP=true
                              Explicit emergency override only.
EOF
}

CONFIRM_DEPLOY=0
DRY_RUN=0
NO_PUSH=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy) CONFIRM_DEPLOY=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-push) NO_PUSH=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "${CONFIRM_DEPLOY}" -eq 1 || "${DRY_RUN}" -eq 1 ]] || die "Pass --deploy for a real production update or --dry-run for preflight"
if [[ "${DRY_RUN}" -eq 1 ]]; then
  NO_PUSH=1
fi

for cmd in bash git scp ssh; do
  require_cmd "${cmd}"
done

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
cd "${ROOT_DIR}"

PRODUCTION_HOST="${PRODUCTION_HOST:-}"
PRODUCTION_BRANCH="${PRODUCTION_BRANCH:-deploy_v2}"
BACKUP_DIRECTORY="${BACKUP_DIRECTORY:-}"
REMOTE_SOURCE_REPO="${REMOTE_SOURCE_REPO:-/opt/utag_ug_website/UG-UTAG-Portal-modern}"
REMOTE_SHARED_ENV_FILE="${REMOTE_SHARED_ENV_FILE:-${REMOTE_SOURCE_REPO}/.env}"
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

[[ -n "${PRODUCTION_HOST}" && "${PRODUCTION_HOST}" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9._:-]+$ ]] || \
  die "PRODUCTION_HOST must be an explicit user@host SSH destination"
[[ "${PRODUCTION_BRANCH}" =~ ^[A-Za-z0-9._/-]+$ ]] || die "Invalid PRODUCTION_BRANCH"
[[ "${BACKUP_DIRECTORY}" == /* ]] || die "BACKUP_DIRECTORY must be an absolute production-host path"
[[ "${REMOTE_SOURCE_REPO}" == /* && "${REMOTE_SHARED_ENV_FILE}" == /* ]] || die "Remote paths must be absolute"
[[ "${PUBLIC_HEALTH_BASE_URL}" =~ ^https://[^/]+/?$ ]] || die "PUBLIC_HEALTH_BASE_URL must be an HTTPS origin"
[[ "${OBJECT_BACKUP_MODE}" == "mirror" || "${OBJECT_BACKUP_MODE}" == "external" ]] || die "Invalid OBJECT_BACKUP_MODE"

bash -n ops/scripts/deploy-production-update.sh
bash -n ops/scripts/push-production-update.sh

status="$(git status --porcelain --untracked-files=normal)"
[[ -z "${status}" ]] || die "The working tree is not clean. Commit the exact release before production deployment."

release_commit="$(git rev-parse HEAD)"
[[ "${release_commit}" =~ ^[0-9a-f]{40}$ ]] || die "Could not resolve the current commit"
short_commit="${release_commit:0:12}"

git fetch origin "${PRODUCTION_BRANCH}"
if [[ "${NO_PUSH}" -eq 0 ]]; then
  git merge-base --is-ancestor "origin/${PRODUCTION_BRANCH}" "${release_commit}" || \
    die "Release is not a fast-forward from origin/${PRODUCTION_BRANCH}; merge/rebase first"
  log "Pushing ${release_commit} to origin/${PRODUCTION_BRANCH}"
  git push origin "${release_commit}:refs/heads/${PRODUCTION_BRANCH}"
else
  [[ "$(git rev-parse "origin/${PRODUCTION_BRANCH}")" == "${release_commit}" ]] || \
    die "--no-push requires HEAD to equal origin/${PRODUCTION_BRANCH}"
fi

remote_script="/tmp/ug-utag-deploy-${short_commit}.sh"
scp -q -o BatchMode=yes -o ConnectTimeout=15 \
  ops/scripts/deploy-production-update.sh "${PRODUCTION_HOST}:${remote_script}"

printf -v remote_command \
  'RELEASE_COMMIT=%q PRODUCTION_BRANCH=%q SOURCE_REPO=%q SHARED_ENV_FILE=%q BACKUP_DIRECTORY=%q PUBLIC_HEALTH_BASE_URL=%q OBJECT_BACKUP_MODE=%q OBJECT_BACKUP_SENTINEL=%q MAX_OBJECT_BACKUP_AGE_HOURS=%q REQUIRE_GOOGLE_DRIVE=%q ALLOWED_PUBLIC_TCP_PORTS=%q ALLOWED_PUBLIC_UDP_PORTS=%q ALLOW_SAME_FILESYSTEM_BACKUP=%q MIN_FREE_GB_BEFORE_BUILD=%q MIN_FREE_GB_AFTER_DEPLOY=%q MIN_FREE_GB_BACKUP=%q KEEP_RELEASES=%q KEEP_ROLLBACK_IMAGES=%q BUILDER_CACHE_MAX_AGE=%q bash %q%s; status=$?; rm -f %q; exit $status' \
  "${release_commit}" \
  "${PRODUCTION_BRANCH}" \
  "${REMOTE_SOURCE_REPO}" \
  "${REMOTE_SHARED_ENV_FILE}" \
  "${BACKUP_DIRECTORY}" \
  "${PUBLIC_HEALTH_BASE_URL}" \
  "${OBJECT_BACKUP_MODE}" \
  "${OBJECT_BACKUP_SENTINEL}" \
  "${MAX_OBJECT_BACKUP_AGE_HOURS}" \
  "${REQUIRE_GOOGLE_DRIVE}" \
  "${ALLOWED_PUBLIC_TCP_PORTS}" \
  "${ALLOWED_PUBLIC_UDP_PORTS}" \
  "${ALLOW_SAME_FILESYSTEM_BACKUP}" \
  "${MIN_FREE_GB_BEFORE_BUILD}" \
  "${MIN_FREE_GB_AFTER_DEPLOY}" \
  "${MIN_FREE_GB_BACKUP}" \
  "${KEEP_RELEASES}" \
  "${KEEP_ROLLBACK_IMAGES}" \
  "${BUILDER_CACHE_MAX_AGE}" \
  "${remote_script}" \
  "$([[ "${DRY_RUN}" -eq 1 ]] && printf ' --dry-run')" \
  "${remote_script}"

log "Running the production deployment on ${PRODUCTION_HOST}"
ssh -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=15 "${PRODUCTION_HOST}" "${remote_command}"
log "Production deployment finished for ${release_commit}"
