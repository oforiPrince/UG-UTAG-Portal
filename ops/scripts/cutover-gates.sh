#!/usr/bin/env bash
set -euo pipefail

evidence_file="${1:-}"
if [[ -z "${evidence_file}" || ! -f "${evidence_file}" ]]; then
  echo "Usage: cutover-gates.sh path/to/reconciliation.json [archive-approval.json]" >&2
  exit 1
fi

approval_file="${2:-${ARCHIVE_ONLY_APPROVAL_FILE:-}}"
media_manifest="${MEDIA_MANIFEST_FILE:-$(dirname "${evidence_file}")/media-manifest.json}"

python3 - "${evidence_file}" "${approval_file}" <<'PY'
import json
import sys
from pathlib import Path

with open(sys.argv[1], encoding="utf-8") as stream:
    evidence = json.load(stream)
if evidence.get("passed") is not True:
    raise SystemExit("Cutover blocked: reconciliation did not pass")
failed = [name for name, row in evidence.get("tables", {}).items() if not row.get("passed")]
if failed:
    raise SystemExit("Cutover blocked for tables: " + ", ".join(failed))
required = set(evidence.get("archive_approval_required", []))
if required:
    approval_path = Path(sys.argv[2]) if sys.argv[2] else None
    if approval_path is None or not approval_path.is_file():
        raise SystemExit(
            "Cutover blocked: archive-only rows require a named approval file for: "
            + ", ".join(sorted(required))
        )
    with approval_path.open(encoding="utf-8") as stream:
        approval = json.load(stream)
    approved = set(approval.get("approved_tables", []))
    missing = required - approved
    if missing:
        raise SystemExit(
            "Cutover blocked: archive-only tables lack approval: " + ", ".join(sorted(missing))
        )
    if not all(approval.get(field) for field in ("approved_by", "approved_at", "decision")):
        raise SystemExit(
            "Cutover blocked: archive approval needs approved_by, approved_at, and decision"
        )
print("Data gate passed")
PY

if [[ "${REQUIRE_MEDIA_MANIFEST:-true}" == "true" ]]; then
  python3 - "${media_manifest}" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"Cutover blocked: media manifest is missing: {path}")
with path.open(encoding="utf-8") as stream:
    manifest = json.load(stream)
files = manifest.get("files", [])
if manifest.get("file_count") != len(files):
    raise SystemExit("Cutover blocked: media manifest file count is inconsistent")
if manifest.get("total_bytes") != sum(int(item.get("byte_size", -1)) for item in files):
    raise SystemExit("Cutover blocked: media manifest byte count is inconsistent")
invalid = [
    item.get("path", "<unknown>")
    for item in files
    if not item.get("storage_key")
    or not item.get("sha256")
    or item.get("target_verified") is not True
]
if invalid:
    raise SystemExit("Cutover blocked: unverified media objects: " + ", ".join(invalid[:20]))
print("Media gate passed")
PY
fi

curl --fail --silent --show-error "${API_HEALTH_URL:-http://localhost:8000/health/ready}" >/dev/null
curl --fail --silent --show-error "${WEB_HEALTH_URL:-http://localhost:3000/api/health}" >/dev/null

echo "Technical cutover gates passed. Named business approval is still required."
