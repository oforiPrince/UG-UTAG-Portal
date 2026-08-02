import re
from typing import Any
from uuid import UUID

import boto3
from botocore.client import Config

from utag_api.config import get_settings
from utag_api.errors import ApiError

ALLOWED_UPLOAD_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/avif",
    "image/gif",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/plain",
}


def safe_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return sanitized[:180] or "upload"


def s3_client() -> Any:
    settings = get_settings()
    kwargs: dict[str, Any] = {
        "region_name": settings.s3_region,
        "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.s3_access_key and settings.s3_secret_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key.get_secret_value()
        kwargs["aws_secret_access_key"] = settings.s3_secret_key.get_secret_value()
    return boto3.client("s3", **kwargs)


def s3_encryption_args() -> dict[str, str]:
    settings = get_settings()
    if not settings.s3_server_side_encryption:
        return {}
    # Custom S3-compatible endpoints (for example MinIO) often advertise AES256
    # in config for production gates but do not implement AWS SSE-KMS/SSE-S3.
    endpoint = (settings.s3_endpoint_url or "").casefold()
    if endpoint and "amazonaws.com" not in endpoint:
        return {}
    values: dict[str, str] = {"ServerSideEncryption": settings.s3_server_side_encryption}
    if settings.s3_server_side_encryption == "aws:kms" and settings.s3_kms_key_id:
        values["SSEKMSKeyId"] = settings.s3_kms_key_id
    return values


def validate_upload(content_type: str, byte_size: int) -> None:
    settings = get_settings()
    if content_type not in ALLOWED_UPLOAD_TYPES:
        raise ApiError(415, "file_type_not_allowed", "This file type is not allowed")
    if byte_size > settings.upload_max_bytes:
        raise ApiError(
            413,
            "file_too_large",
            f"Files must be smaller than {settings.upload_max_bytes // 1_000_000} MB",
        )


def quarantine_key(asset_id: UUID, filename: str) -> str:
    return f"quarantine/{asset_id}/{safe_filename(filename)}"


def presign_put(
    *, storage_key: str, content_type: str, byte_size: int, sha256: str
) -> tuple[str, dict[str, str]]:
    settings = get_settings()
    headers = {
        "Content-Type": content_type,
        "x-amz-meta-byte-size": str(byte_size),
        "x-amz-meta-sha256": sha256.casefold(),
    }
    encryption = s3_encryption_args()
    if encryption:
        headers["x-amz-server-side-encryption"] = encryption["ServerSideEncryption"]
        if "SSEKMSKeyId" in encryption:
            headers["x-amz-server-side-encryption-aws-kms-key-id"] = encryption["SSEKMSKeyId"]
    params = {
        "Bucket": settings.media_bucket,
        "Key": storage_key,
        "ContentType": content_type,
        "Metadata": {"byte-size": str(byte_size), "sha256": sha256.casefold()},
        **encryption,
    }
    url = str(
        s3_client().generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=settings.presigned_url_ttl_seconds,
            HttpMethod="PUT",
        )
    )
    return url, headers


def presign_get(storage_key: str, filename: str) -> str:
    settings = get_settings()
    return str(
        s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": settings.media_bucket,
                "Key": storage_key,
                "ResponseContentDisposition": f'inline; filename="{safe_filename(filename)}"',
            },
            ExpiresIn=settings.presigned_url_ttl_seconds,
            HttpMethod="GET",
        )
    )
