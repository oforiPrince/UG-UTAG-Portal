#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${LEGACY_DATABASE_URL:-}" ]]; then
  echo "LEGACY_DATABASE_URL is required" >&2
  exit 1
fi

batch_id="${MIGRATION_BATCH_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
evidence_directory="${MIGRATION_EVIDENCE_DIRECTORY:-migration-evidence/${batch_id}}"
mkdir -p "${evidence_directory}"
evidence_directory="$(cd "${evidence_directory}" && pwd)"

run_migration() {
  docker compose run --rm --no-deps \
    --add-host=host.docker.internal:host-gateway \
    -e LEGACY_DATABASE_URL \
    -v "${evidence_directory}:/evidence" \
    api python /app/scripts/legacy_migration.py "$@"
}

run_migration inventory --output /evidence/inventory.json
run_migration capture --batch-id "${batch_id}" --archive-dir /evidence/rows
run_migration promote --batch-id "${batch_id}"
run_migration reconcile --output /evidence/reconciliation.json

if [[ -n "${LEGACY_MEDIA_ROOT:-}" ]]; then
  media_root="$(cd "${LEGACY_MEDIA_ROOT}" && pwd)"
  docker compose run --rm --no-deps \
    --add-host=host.docker.internal:host-gateway \
    -v "${evidence_directory}:/evidence" \
    -v "${media_root}:/legacy-media:ro" \
    api python /app/scripts/legacy_migration.py files \
      --media-root /legacy-media \
      --archive-dir /evidence \
      --upload
fi

echo "Reconciliation evidence: ${evidence_directory}"
