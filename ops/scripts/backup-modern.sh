#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${BACKUP_DIRECTORY:-}" ]]; then
  echo "BACKUP_DIRECTORY is required" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIRECTORY}"
backup_directory="$(cd "${BACKUP_DIRECTORY}" && pwd)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_file="${backup_directory}/ug-utag-${timestamp}.dump"
object_directory_name="ug-utag-${timestamp}-objects"
object_directory="${backup_directory}/${object_directory_name}"

docker compose exec -T postgres pg_dump \
  --username "${POSTGRES_USER:-utag}" \
  --dbname "${POSTGRES_DB:-utag_portal}" \
  --format custom \
  --no-owner \
  --file /tmp/portal.dump
docker compose cp postgres:/tmp/portal.dump "${backup_file}"
(
  cd "${backup_directory}"
  shasum -a 256 "$(basename "${backup_file}")" > "$(basename "${backup_file}").sha256"
)
docker compose exec -T postgres rm -f /tmp/portal.dump

mkdir -p "${object_directory}"
docker compose run --rm --no-deps -T \
  -e OBJECT_BACKUP_NAME="${object_directory_name}" \
  -v "${backup_directory}:/backup" \
  --entrypoint /bin/sh \
  minio-init -ec '
    mc alias set source http://minio:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY"
    mc mirror --overwrite "source/$MEDIA_BUCKET" "/backup/$OBJECT_BACKUP_NAME"
  '

(
  cd "${object_directory}"
  while IFS= read -r -d '' object_file; do
    shasum -a 256 "${object_file}"
  done < <(find . -type f -print0)
) > "${object_directory}.sha256"

echo "Created database backup ${backup_file}"
echo "Created object backup ${object_directory}"
