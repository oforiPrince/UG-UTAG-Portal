"""Google Drive OAuth and folder listing helpers (Drive REST via httpx)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

import httpx

from utag_api.config import Settings, get_settings
from utag_api.errors import ApiError
from utag_api.models import GoogleDriveConnection
from utag_api.security import decrypt_text, encrypt_text
from utag_api.services.storage import ALLOWED_UPLOAD_TYPES

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_DRIVE_FILES_URL = "https://www.googleapis.com/drive/v3/files"

DRIVE_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/drive.readonly",
)
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"
IMAGE_CONTENT_TYPES = {
    content_type for content_type in ALLOWED_UPLOAD_TYPES if content_type.startswith("image/")
}
FOLDER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{10,}$")
OAUTH_STATE_TTL_SECONDS = 600


@dataclass(frozen=True, slots=True)
class DriveFile:
    id: str
    name: str
    mime_type: str
    size: int


@dataclass(frozen=True, slots=True)
class OAuthState:
    user_id: UUID
    session_id: UUID


def require_google_drive_configured(settings: Settings | None = None) -> Settings:
    configured = settings or get_settings()
    if not configured.google_drive_configured:
        raise ApiError(
            503,
            "google_drive_not_configured",
            "Google Drive import is not configured on this server",
        )
    return configured


def parse_drive_folder_id(folder_url: str) -> str:
    raw = folder_url.strip()
    if not raw:
        raise ApiError(422, "invalid_drive_folder_url", "Enter a Google Drive folder link")
    if FOLDER_ID_RE.fullmatch(raw):
        return raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").casefold()
    if host not in {"drive.google.com", "www.drive.google.com"}:
        raise ApiError(
            422,
            "invalid_drive_folder_url",
            "Use a Google Drive folder link (drive.google.com)",
        )
    path_parts = [part for part in parsed.path.split("/") if part]
    folder_id: str | None = None
    if "folders" in path_parts:
        index = path_parts.index("folders")
        if index + 1 < len(path_parts):
            folder_id = path_parts[index + 1]
    if not folder_id:
        query = parse_qs(parsed.query)
        candidates = query.get("id") or []
        folder_id = candidates[0] if candidates else None
    if not folder_id or not FOLDER_ID_RE.fullmatch(folder_id):
        raise ApiError(
            422,
            "invalid_drive_folder_url",
            "Could not read a folder ID from that Google Drive link",
        )
    return folder_id


def sign_oauth_state(
    *,
    user_id: UUID,
    session_id: UUID,
    nonce: str,
    now: datetime | None = None,
) -> str:
    settings = get_settings()
    issued = int((now or datetime.now(UTC)).timestamp())
    payload = {
        "uid": str(user_id),
        "sid": str(session_id),
        "nonce": nonce,
        "iat": issued,
        "exp": issued + OAUTH_STATE_TTL_SECONDS,
    }
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()
    signature = hmac.new(
        settings.app_secret_key.get_secret_value().encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{signature}"


def verify_oauth_state(state: str) -> OAuthState:
    settings = get_settings()
    try:
        body, signature = state.split(".", 1)
    except ValueError as exc:
        raise ApiError(400, "invalid_oauth_state", "Google sign-in state is invalid") from exc
    expected = hmac.new(
        settings.app_secret_key.get_secret_value().encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise ApiError(400, "invalid_oauth_state", "Google sign-in state is invalid")
    try:
        payload = json.loads(base64.urlsafe_b64decode(body.encode()))
        user_id = UUID(str(payload["uid"]))
        session_id = UUID(str(payload["sid"]))
        nonce = str(payload["nonce"])
        issued_at = int(payload["iat"])
        exp = int(payload["exp"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ApiError(400, "invalid_oauth_state", "Google sign-in state is invalid") from exc
    now = int(time.time())
    if not nonce or issued_at > now + 60:
        raise ApiError(400, "invalid_oauth_state", "Google sign-in state is invalid")
    if exp < now:
        raise ApiError(400, "oauth_state_expired", "Google sign-in expired. Please try again.")
    return OAuthState(user_id=user_id, session_id=session_id)


def authorization_url(*, user_id: UUID, session_id: UUID, nonce: str) -> str:
    settings = require_google_drive_configured()
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(DRIVE_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": sign_oauth_state(user_id=user_id, session_id=session_id, nonce=nonce),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    settings = require_google_drive_configured()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret.get_secret_value()
                    if settings.google_oauth_client_secret
                    else "",
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            502,
            "google_token_exchange_failed",
            "Google sign-in could not be reached",
        ) from exc
    if response.status_code >= 400:
        raise ApiError(
            502,
            "google_token_exchange_failed",
            "Google did not accept the authorization code",
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise ApiError(
            502,
            "google_token_exchange_failed",
            "Google returned an invalid sign-in response",
        ) from exc
    if not data.get("access_token") or not data.get("refresh_token"):
        raise ApiError(
            502,
            "google_refresh_token_missing",
            "Google did not return a refresh token. Disconnect and connect again.",
        )
    return cast(dict[str, Any], data)


async def fetch_userinfo(access_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            502,
            "google_userinfo_failed",
            "Could not load the Google account profile",
        ) from exc
    if response.status_code >= 400:
        raise ApiError(502, "google_userinfo_failed", "Could not load the Google account profile")
    try:
        return cast(dict[str, Any], response.json())
    except ValueError as exc:
        raise ApiError(
            502,
            "google_userinfo_failed",
            "Google returned an invalid account profile",
        ) from exc


async def revoke_token(token: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            await client.post(GOOGLE_REVOKE_URL, data={"token": token})
    except httpx.HTTPError:
        # Local disconnection must still succeed when Google is temporarily unavailable.
        return


def connection_tokens(connection: GoogleDriveConnection) -> tuple[str, str]:
    access = decrypt_text(connection.access_token_encrypted)
    refresh = decrypt_text(connection.refresh_token_encrypted)
    if not access or not refresh:
        raise ApiError(
            409,
            "google_drive_token_corrupt",
            "Reconnect Google Drive to continue importing",
        )
    return access, refresh


def apply_token_payload(
    connection: GoogleDriveConnection,
    payload: dict[str, Any],
    *,
    keep_refresh: str | None = None,
) -> None:
    access = str(payload["access_token"])
    refresh = str(payload.get("refresh_token") or keep_refresh or "")
    if not refresh:
        raise ApiError(
            502,
            "google_refresh_token_missing",
            "Google did not return a refresh token. Disconnect and connect again.",
        )
    encrypted_access = encrypt_text(access)
    encrypted_refresh = encrypt_text(refresh)
    if encrypted_access is None or encrypted_refresh is None:
        raise ApiError(500, "token_encryption_failed", "Could not store Google Drive tokens")
    connection.access_token_encrypted = encrypted_access
    connection.refresh_token_encrypted = encrypted_refresh
    expires_in = int(payload.get("expires_in") or 3600)
    connection.token_expires_at = datetime.now(UTC) + timedelta(seconds=max(expires_in - 60, 0))
    if payload.get("scope"):
        connection.scopes = str(payload["scope"])


async def refresh_access_token(connection: GoogleDriveConnection) -> str:
    settings = require_google_drive_configured()
    _, refresh = connection_tokens(connection)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret.get_secret_value()
                    if settings.google_oauth_client_secret
                    else "",
                    "refresh_token": refresh,
                    "grant_type": "refresh_token",
                },
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            502,
            "google_drive_refresh_failed",
            "Google Drive could not be reached. Try again shortly.",
        ) from exc
    if response.status_code >= 400:
        raise ApiError(
            401,
            "google_drive_reauth_required",
            "Google Drive access expired. Disconnect and connect again.",
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise ApiError(
            502,
            "google_drive_refresh_failed",
            "Google returned an invalid token response",
        ) from exc
    apply_token_payload(connection, payload, keep_refresh=refresh)
    access, _ = connection_tokens(connection)
    return access


async def ensure_access_token(connection: GoogleDriveConnection) -> str:
    expires = connection.token_expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires > datetime.now(UTC) + timedelta(seconds=30):
        access, _ = connection_tokens(connection)
        return access
    return await refresh_access_token(connection)


async def _drive_get(
    access_token: str,
    *,
    params: dict[str, str],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                GOOGLE_DRIVE_FILES_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
            )
    except httpx.HTTPError as exc:
        raise ApiError(
            502,
            "google_drive_list_failed",
            "Could not reach Google Drive",
        ) from exc
    if response.status_code == 401:
        raise ApiError(
            401,
            "google_drive_reauth_required",
            "Google Drive access expired. Disconnect and connect again.",
        )
    if response.status_code == 404:
        raise ApiError(404, "drive_folder_not_found", "That Google Drive folder was not found")
    if response.status_code >= 400:
        raise ApiError(
            502,
            "google_drive_list_failed",
            "Could not list files from Google Drive",
        )
    try:
        return cast(dict[str, Any], response.json())
    except ValueError as exc:
        raise ApiError(
            502,
            "google_drive_list_failed",
            "Google Drive returned an invalid folder listing",
        ) from exc


async def list_folder_children(access_token: str, folder_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    query = f"'{folder_id}' in parents and trashed = false"
    while True:
        params: dict[str, str] = {
            "q": query,
            "spaces": "drive",
            "pageSize": "100",
            "fields": "nextPageToken, files(id, name, mimeType, size)",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page_token:
            params["pageToken"] = page_token
        payload = await _drive_get(access_token, params=params)
        items.extend(payload.get("files") or [])
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return items


def _to_drive_file(row: dict[str, Any]) -> DriveFile | None:
    mime_type = str(row.get("mimeType") or "")
    if mime_type not in IMAGE_CONTENT_TYPES:
        return None
    try:
        size = int(row.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    file_id = str(row.get("id") or "")
    name = str(row.get("name") or "image")
    if not file_id:
        return None
    return DriveFile(id=file_id, name=name, mime_type=mime_type, size=size)


async def list_importable_images(
    access_token: str,
    folder_id: str,
    *,
    max_bytes: int,
) -> tuple[list[DriveFile], list[DriveFile]]:
    """Return (importable, skipped_oversized) images from a folder and its direct subfolders."""
    importable: list[DriveFile] = []
    oversized: list[DriveFile] = []
    seen: set[str] = set()

    def consider(file: DriveFile) -> None:
        if file.id in seen:
            return
        seen.add(file.id)
        if file.size <= 0 or file.size > max_bytes:
            oversized.append(file)
            return
        importable.append(file)

    root_children = await list_folder_children(access_token, folder_id)
    subfolders: list[str] = []
    for row in root_children:
        mime_type = str(row.get("mimeType") or "")
        if mime_type == DRIVE_FOLDER_MIME:
            child_id = str(row.get("id") or "")
            if child_id:
                subfolders.append(child_id)
            continue
        file = _to_drive_file(row)
        if file is not None:
            consider(file)

    for subfolder_id in subfolders:
        for row in await list_folder_children(access_token, subfolder_id):
            file = _to_drive_file(row)
            if file is not None:
                consider(file)

    return importable, oversized


async def download_file(
    access_token: str,
    file_id: str,
    *,
    max_bytes: int,
) -> bytes:
    try:
        async with (
            httpx.AsyncClient(timeout=120.0) as client,
            client.stream(
                "GET",
                f"{GOOGLE_DRIVE_FILES_URL}/{file_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"alt": "media", "supportsAllDrives": "true"},
            ) as response,
        ):
            if response.status_code == 401:
                raise ApiError(
                    401,
                    "google_drive_reauth_required",
                    "Google Drive access expired. Disconnect and connect again.",
                )
            if response.status_code >= 400:
                raise ApiError(
                    502,
                    "google_drive_download_failed",
                    "Could not download a file from Google Drive",
                )
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > max_bytes:
                raise ApiError(
                    413,
                    "google_drive_file_too_large",
                    "A Google Drive image exceeds the upload limit",
                )
            chunks: list[bytes] = []
            byte_size = 0
            async for chunk in response.aiter_bytes():
                byte_size += len(chunk)
                if byte_size > max_bytes:
                    raise ApiError(
                        413,
                        "google_drive_file_too_large",
                        "A Google Drive image exceeds the upload limit",
                    )
                chunks.append(chunk)
    except ApiError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(
            502,
            "google_drive_download_failed",
            "Could not download a file from Google Drive",
        ) from exc
    return b"".join(chunks)
