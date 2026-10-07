from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import GoogleDriveConnection
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import GoogleDriveStatus
from utag_api.security import new_token
from utag_api.services import google_drive as drive
from utag_api.services.events import record_change

router = APIRouter(prefix="/integrations/google-drive", tags=["integrations"])


@router.get("/status", response_model=GoogleDriveStatus)
async def google_drive_status(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.edit"))],
) -> GoogleDriveStatus:
    settings = get_settings()
    connection = await db.scalar(
        select(GoogleDriveConnection).where(GoogleDriveConnection.user_id == principal.user.id)
    )
    return GoogleDriveStatus(
        configured=settings.google_drive_configured,
        connected=connection is not None,
        email=connection.google_email if connection else None,
    )


@router.get("/connect")
async def google_drive_connect(
    principal: Annotated[Principal, Depends(require_permissions("content.edit"))],
) -> RedirectResponse:
    drive.require_google_drive_configured()
    url = drive.authorization_url(
        user_id=principal.user.id,
        session_id=principal.session.id,
        nonce=new_token(),
    )
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
async def google_drive_callback(
    db: DbSession,
    request: Request,
    principal: Annotated[Principal, Depends(require_permissions("content.edit"))],
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    galleries_url = f"{settings.public_web_url.rstrip('/')}/dashboard/galleries"
    if error or not code or not state:
        return RedirectResponse(url=f"{galleries_url}?drive=error", status_code=302)
    try:
        oauth_state = drive.verify_oauth_state(state)
        if (
            oauth_state.user_id != principal.user.id
            or oauth_state.session_id != principal.session.id
        ):
            raise ApiError(400, "invalid_oauth_state", "Google sign-in state is invalid")
        token_payload = await drive.exchange_code_for_tokens(code)
        access_token = str(token_payload["access_token"])
        profile = await drive.fetch_userinfo(access_token)
        google_sub = str(profile.get("sub") or "")
        google_email = str(profile.get("email") or "")
        if not google_sub:
            raise ApiError(502, "google_userinfo_failed", "Google account id missing")
        connection = await db.scalar(
            select(GoogleDriveConnection).where(GoogleDriveConnection.user_id == principal.user.id)
        )
        if connection is None:
            connection = GoogleDriveConnection(
                id=new_id(),
                user_id=principal.user.id,
                google_sub=google_sub,
                google_email=google_email,
                access_token_encrypted=b"\x00",
                refresh_token_encrypted=b"\x00",
                token_expires_at=datetime.now(UTC),
                scopes="",
            )
            drive.apply_token_payload(connection, token_payload)
            db.add(connection)
        else:
            connection.google_sub = google_sub
            connection.google_email = google_email
            drive.apply_token_payload(connection, token_payload)
        record_change(
            db,
            context=event_context(request, principal),
            action="integration.google_drive.connected",
            resource_type="google_drive_connection",
            resource_id=connection.id,
            topic="integrations",
            payload={"provider": "google_drive"},
        )
        await db.commit()
    except ApiError:
        return RedirectResponse(url=f"{galleries_url}?drive=error", status_code=302)
    return RedirectResponse(url=f"{galleries_url}?drive=connected", status_code=302)


@router.delete("", response_model=MessageResponse)
async def google_drive_disconnect(
    db: DbSession,
    request: Request,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
) -> MessageResponse:
    connection = await db.scalar(
        select(GoogleDriveConnection).where(GoogleDriveConnection.user_id == principal.user.id)
    )
    if connection is None:
        return MessageResponse(message="Google Drive is not connected")
    try:
        access, refresh = drive.connection_tokens(connection)
        await drive.revoke_token(refresh or access)
    except ApiError:
        pass
    record_change(
        db,
        context=event_context(request, principal),
        action="integration.google_drive.disconnected",
        resource_type="google_drive_connection",
        resource_id=connection.id,
        topic="integrations",
        payload={"provider": "google_drive"},
    )
    await db.delete(connection)
    await db.commit()
    return MessageResponse(message="Google Drive disconnected")
