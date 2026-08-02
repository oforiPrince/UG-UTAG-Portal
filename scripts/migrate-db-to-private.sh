#!/usr/bin/env bash
set -euo pipefail

# End-to-end Postgres migration:
# - Source: Dockerized postgres on public server
# - Dest:   Host-installed postgres on private server (reachable via VPN)
#
# What it does:
# - Stops Django writers on the source (brief downtime)
# - Creates a pg_dump custom-format backup from the source DB container
# - Installs/configures PostgreSQL 16 on the private server (Debian/Ubuntu)
# - Creates the DB/user on the private server (if missing)
# - Restores the dump
# - Updates the source server .env to point DB_HOST/DB_PORT at the private DB
# - Restarts the app services
#
# Safety:
# - Writes backups into ./_db_migration_artifacts/
# - Makes a timestamped backup of the source .env before editing

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ARTIFACT_DIR="${SCRIPT_DIR}/../_db_migration_artifacts"
mkdir -p "${ARTIFACT_DIR}"

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

require() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

require ssh
require scp
require awk
require sed

usage() {
  cat <<'EOF'
Usage:
  migrate-db-to-private.sh [options]

Options (can also be set via environment variables):
  --src-host            Source SSH host (default: utagadmin@197.255.126.246)
  --src-dir             Source project dir (default: /opt/utag_ug_website/UG-UTAG-Portal/utag_ug_archiver)
  --src-env-file        Source env file to update (default: <src-dir>/.env)
  --src-db-compose      Source db compose file (default: <src-dir>/docker-compose.db.yml)
  --src-app-compose     Source app compose file (default: <src-dir>/docker-compose.app.yml)

  --dest-host           Destination SSH host (default: utagadmin@10.2.2.129)
  --dest-db-host        Destination DB listen address for app to use (default: 10.2.2.129)
  --dest-db-port        Destination DB port (default: 5432)

  --db-name             DB name (default: read from source .env.db POSTGRES_DB or app_database)
  --db-user             DB user (default: read from source .env.db POSTGRES_USER or db_user)
  --db-password         DB password to set on destination (default: read from source .env.db POSTGRES_PASSWORD)

  --allow-src-cidr      CIDR allowed to connect to destination DB (default: 197.255.126.246/32)

Notes:
  - This script assumes the destination server is Debian/Ubuntu (apt-based).
  - You must have VPN access to 10.2.2.129 from the machine running this script.
  - Downtime window: web/worker/beat will be stopped on the source during dump.

EOF
}

SRC_HOST="${SRC_HOST:-utagadmin@197.255.126.246}"
SRC_DIR="${SRC_DIR:-/opt/utag_ug_website/UG-UTAG-Portal/utag_ug_archiver}"
SRC_ENV_FILE="${SRC_ENV_FILE:-${SRC_DIR}/.env}"
SRC_DB_COMPOSE="${SRC_DB_COMPOSE:-${SRC_DIR}/docker-compose.db.yml}"
SRC_APP_COMPOSE="${SRC_APP_COMPOSE:-${SRC_DIR}/docker-compose.app.yml}"

DEST_HOST="${DEST_HOST:-utagadmin@10.2.2.129}"
DEST_DB_HOST="${DEST_DB_HOST:-10.2.2.129}"
DEST_DB_PORT="${DEST_DB_PORT:-5432}"

ALLOW_SRC_CIDR="${ALLOW_SRC_CIDR:-197.255.126.246/32}"

DB_NAME="${DB_NAME:-}"
DB_USER="${DB_USER:-}"
DB_PASSWORD="${DB_PASSWORD:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --src-host) SRC_HOST="$2"; shift 2 ;;
    --src-dir) SRC_DIR="$2"; shift 2 ;;
    --src-env-file) SRC_ENV_FILE="$2"; shift 2 ;;
    --src-db-compose) SRC_DB_COMPOSE="$2"; shift 2 ;;
    --src-app-compose) SRC_APP_COMPOSE="$2"; shift 2 ;;
    --dest-host) DEST_HOST="$2"; shift 2 ;;
    --dest-db-host) DEST_DB_HOST="$2"; shift 2 ;;
    --dest-db-port) DEST_DB_PORT="$2"; shift 2 ;;
    --db-name) DB_NAME="$2"; shift 2 ;;
    --db-user) DB_USER="$2"; shift 2 ;;
    --db-password) DB_PASSWORD="$2"; shift 2 ;;
    --allow-src-cidr) ALLOW_SRC_CIDR="$2"; shift 2 ;;
    *) die "Unknown arg: $1" ;;
  esac
done

remote_read_first_kv() {
  # Reads first matching KEY=value for KEY in a remote file.
  # Usage: remote_read_first_kv <host> <path> <key>
  local host="$1"
  local path="$2"
  local key="$3"
  ssh -o BatchMode=yes "$host" "test -f \"$path\" && awk -F= -v k=\"$key\" '
    \$0 ~ \"^\"k\"=\" {
      v=substr(\$0, index(\$0, \"=\")+1);
      print v;
      exit
    }
  ' \"$path\" || true"
}

log "Checking SSH connectivity."
ssh -o BatchMode=yes "$SRC_HOST" "echo ok" >/dev/null
ssh -o BatchMode=yes "$DEST_HOST" "echo ok" >/dev/null

log "Reading DB settings from source .env.db (if present)."
SRC_ENV_DB="${SRC_DIR}/.env.db"
if [[ -z "${DB_NAME}" ]]; then
  DB_NAME="$(remote_read_first_kv "$SRC_HOST" "$SRC_ENV_DB" "POSTGRES_DB" | tr -d '\r\n')"
fi
if [[ -z "${DB_USER}" ]]; then
  DB_USER="$(remote_read_first_kv "$SRC_HOST" "$SRC_ENV_DB" "POSTGRES_USER" | tr -d '\r\n')"
fi
if [[ -z "${DB_PASSWORD}" ]]; then
  DB_PASSWORD="$(remote_read_first_kv "$SRC_HOST" "$SRC_ENV_DB" "POSTGRES_PASSWORD" | tr -d '\r\n')"
fi

DB_NAME="${DB_NAME:-app_database}"
DB_USER="${DB_USER:-db_user}"
[[ -n "${DB_PASSWORD}" ]] || die "DB password is empty. Set --db-password or fix ${SRC_ENV_DB} on the source."

log "Using DB_NAME=${DB_NAME}, DB_USER=${DB_USER} (password not printed)."

ts="$(date -u +'%Y%m%dT%H%M%SZ')"
dump_file="${ARTIFACT_DIR}/pgdump_${DB_NAME}_${ts}.dump"

log "Stopping writers on source (web/worker/beat)."
ssh "$SRC_HOST" "cd \"$SRC_DIR\" && docker compose -f \"$SRC_APP_COMPOSE\" stop web worker beat" || {
  log "Warning: could not stop web/worker/beat via ${SRC_APP_COMPOSE}. Continuing anyway."
}

log "Creating pg_dump from source Docker DB service."
ssh "$SRC_HOST" "cd \"$SRC_DIR\" && docker compose -f \"$SRC_DB_COMPOSE\" exec -T db sh -lc 'pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" -Fc'" > "${dump_file}"

log "Dump saved to ${dump_file}."

log "Copying dump to destination server."
scp "${dump_file}" "${DEST_HOST}:/tmp/utag_pg_migrate.dump"

log "Installing PostgreSQL 16 on destination (apt-based)."
ssh "$DEST_HOST" "set -euo pipefail
  if ! command -v apt-get >/dev/null 2>&1; then
    echo 'Destination OS is not apt-based (Debian/Ubuntu). Install PostgreSQL 16 manually and re-run.' >&2
    exit 2
  fi
  sudo apt-get update -y
  sudo apt-get install -y curl ca-certificates gnupg lsb-release
  sudo install -d -m 0755 /etc/apt/keyrings
  if [ ! -f /etc/apt/keyrings/postgresql.gpg ]; then
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg
  fi
  if [ ! -f /etc/apt/sources.list.d/pgdg.list ]; then
    echo \"deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt \$(lsb_release -cs)-pgdg main\" | sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
  fi
  sudo apt-get update -y
  sudo apt-get install -y postgresql-16 postgresql-client-16
"

log "Configuring Postgres to listen and allow ${ALLOW_SRC_CIDR}."
ssh "$DEST_HOST" "set -euo pipefail
  conf=/etc/postgresql/16/main/postgresql.conf
  hba=/etc/postgresql/16/main/pg_hba.conf

  sudo cp -n \"\$conf\" \"\$conf.bak\" || true
  sudo cp -n \"\$hba\" \"\$hba.bak\" || true

  # Listen on all interfaces (restrict access via pg_hba + firewall).
  sudo sed -i \"s/^#\\?listen_addresses\\s*=.*/listen_addresses = '*' /\" \"\$conf\"

  # Ensure SCRAM is used when possible.
  if ! grep -q '^password_encryption' \"\$conf\"; then
    echo \"password_encryption = 'scram-sha-256'\" | sudo tee -a \"\$conf\" >/dev/null
  fi

  rule=\"host  ${DB_NAME}  ${DB_USER}  ${ALLOW_SRC_CIDR}  scram-sha-256\"
  if ! sudo grep -Fq \"\$rule\" \"\$hba\"; then
    echo \"\$rule\" | sudo tee -a \"\$hba\" >/dev/null
  fi

  sudo systemctl restart postgresql
"

log "Creating destination role/db if missing."
ssh "$DEST_HOST" "set -euo pipefail
  sudo -u postgres psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'\" | grep -q 1 || \
    sudo -u postgres psql -c \"CREATE USER \\\"${DB_USER}\\\" WITH PASSWORD '${DB_PASSWORD}';\"

  sudo -u postgres psql -tAc \"SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'\" | grep -q 1 || \
    sudo -u postgres psql -c \"CREATE DATABASE \\\"${DB_NAME}\\\" OWNER \\\"${DB_USER}\\\";\"
"

log "Restoring dump into destination DB."
ssh "$DEST_HOST" "set -euo pipefail
  pg_restore --no-owner --no-privileges --role=\"${DB_USER}\" -d \"${DB_NAME}\" /tmp/utag_pg_migrate.dump
"

log "Updating source env to point to private DB."
ssh "$SRC_HOST" "set -euo pipefail
  envfile=\"${SRC_ENV_FILE}\"
  if [ ! -f \"\$envfile\" ]; then
    echo \"Source env file not found: \$envfile\" >&2
    exit 3
  fi
  sudo cp \"\$envfile\" \"\$envfile.bak.${ts}\"

  # Upsert DB_HOST and DB_PORT (container uses 5432 when remote).
  if grep -q '^DB_HOST=' \"\$envfile\"; then
    sudo sed -i \"s/^DB_HOST=.*/DB_HOST=${DEST_DB_HOST}/\" \"\$envfile\"
  else
    echo \"DB_HOST=${DEST_DB_HOST}\" | sudo tee -a \"\$envfile\" >/dev/null
  fi

  if grep -q '^DB_PORT=' \"\$envfile\"; then
    sudo sed -i \"s/^DB_PORT=.*/DB_PORT=${DEST_DB_PORT}/\" \"\$envfile\"
  else
    echo \"DB_PORT=${DEST_DB_PORT}\" | sudo tee -a \"\$envfile\" >/dev/null
  fi
"

log "Restarting app services on source."
ssh "$SRC_HOST" "cd \"$SRC_DIR\" && docker compose -f \"$SRC_APP_COMPOSE\" up -d"

log "Done."
log "Next: validate the portal, then consider stopping/removing the old DB container once you're confident."

