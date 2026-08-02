#!/usr/bin/env bash
set -euo pipefail

if [[ "${RESTORE_CONFIRM:-}" != "restore-ug-utag" ]]; then
  echo "Set RESTORE_CONFIRM=restore-ug-utag to acknowledge destructive restore" >&2
  exit 1
fi
if [[ -z "${DATABASE_BACKUP:-}" || ! -f "${DATABASE_BACKUP}" ]]; then
  echo "DATABASE_BACKUP must identify a pg_dump custom-format file" >&2
  exit 1
fi
if [[ -z "${OBJECT_BACKUP_DIRECTORY:-}" || ! -d "${OBJECT_BACKUP_DIRECTORY}" ]]; then
  echo "OBJECT_BACKUP_DIRECTORY must identify the matching object backup" >&2
  exit 1
fi

database_backup="$(cd "$(dirname "${DATABASE_BACKUP}")" && pwd)/$(basename "${DATABASE_BACKUP}")"
object_backup_directory="$(cd "${OBJECT_BACKUP_DIRECTORY}" && pwd)"
object_parent="$(dirname "${object_backup_directory}")"
object_name="$(basename "${object_backup_directory}")"
database_name="$(basename "${database_backup}")"
expected_object_name="${database_name%.dump}-objects"

if [[ "${database_name}" != ug-utag-*.dump || "${object_name}" != "${expected_object_name}" ]]; then
  echo "Database and object backups must come from the same ug-utag timestamp" >&2
  exit 1
fi
if [[ ! -f "${database_backup}.sha256" || ! -f "${object_backup_directory}.sha256" ]]; then
  echo "Both backup checksum manifests are required" >&2
  exit 1
fi

(
  cd "$(dirname "${database_backup}")"
  shasum -a 256 -c "${database_name}.sha256"
)
(
  cd "${object_backup_directory}"
  shasum -a 256 -c "${object_backup_directory}.sha256"
)

docker compose cp "${database_backup}" postgres:/tmp/portal-restore.dump
docker compose exec -T postgres pg_restore --list /tmp/portal-restore.dump >/dev/null
docker compose exec -T postgres pg_restore \
  --username "${POSTGRES_USER:-utag}" \
  --dbname "${POSTGRES_DB:-utag_portal}" \
  --clean \
  --if-exists \
  --no-owner \
  /tmp/portal-restore.dump
docker compose exec -T postgres rm -f /tmp/portal-restore.dump

docker compose run --rm --no-deps -T \
  -e OBJECT_BACKUP_NAME="${object_name}" \
  -v "${object_parent}:/backup:ro" \
  --entrypoint /bin/sh \
  minio-init -ec '
    mc alias set destination http://minio:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
    mc mirror --overwrite --remove "/backup/$OBJECT_BACKUP_NAME" "destination/$MEDIA_BUCKET"
  '

echo "Restored database and object storage from the matching backup set"
