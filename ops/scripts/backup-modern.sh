#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BACKUP_DIRECTORY:-}" ]]; then
  echo "BACKUP_DIRECTORY is required" >&2
  exit 1
fi

backup_directory="${BACKUP_DIRECTORY}"
mkdir -p "${backup_directory}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_directory}/ug-utag-${timestamp}.dump"

docker compose exec -T postgres pg_dump \
  --username "${POSTGRES_USER:-utag}" \
  --dbname "${POSTGRES_DB:-utag_portal}" \
  --format custom \
  --no-owner \
  --file /tmp/portal.dump
docker compose cp postgres:/tmp/portal.dump "${backup_file}"
shasum -a 256 "${backup_file}" > "${backup_file}.sha256"
docker compose exec -T postgres rm -f /tmp/portal.dump

echo "Created ${backup_file}"
