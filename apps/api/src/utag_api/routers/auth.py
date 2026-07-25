from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update

from utag_api.config import Settings, get_settings
from utag_api.database import new_id
from utag_api.dependencies import CurrentPrincipal, DbSession, MutationPrincipal, event_context
from utag_api.errors import ApiError
from utag_api.models import (
    AccountToken,
    ExecutiveAppointment,
    MediaAsset,
    OrganizationUnit,
    Session,
    User,
)
from utag_api.rate_limit import enforce_rate_limit
from utag_api.schemas import (
    AcceptInvitationRequest,
    AuthResponse,
    ChangePasswordRequest,
    ExecutiveProfileSummary,
    ExecutiveProfileUpdate,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdate,
    ResetPasswordRequest,
    SessionSummary,
    UserSummary,
)
from utag_api.security import (
    hash_password,
    new_token,
    normalize_email,
    token_digest,
    verify_password,
)
from utag_api.services.content import sanitize_html
from utag_api.services.events import EventContext, record_change
from utag_api.services.identity import strong_password_errors

router = APIRouter(prefix="/auth", tags=["authentication"])


def summarize_user(principal: CurrentPrincipal) -> UserSummary:
    return UserSummary(
        id=principal.user.id,
        email=principal.user.email,
        full_name=principal.user.full_name,
        title=principal.user.title,
        other_name=principal.user.other_name,
        surname=principal.user.surname,
        staff_id=principal.user.staff_id,
        gender=principal.user.gender,
        academic_rank=principal.user.academic_rank,
        phone_number=principal.user.phone_number,
        profile_media_id=principal.user.profile_media_id,
        school_id=principal.user.school_id,
        college_id=principal.user.college_id,
        department_id=principal.user.department_id,
        must_change_password=principal.user.must_change_password,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
    )


async def current_executive_appointment(
    db: DbSession, user_id: UUID
) -> ExecutiveAppointment | None:
    appointment: ExecutiveAppointment | None = await db.scalar(
        select(ExecutiveAppointment)
        .where(
            ExecutiveAppointment.user_id == user_id,
            ExecutiveAppointment.is_active.is_(True),
        )
        .order_by(
            ExecutiveAppointment.appointed_on.desc(),
            ExecutiveAppointment.created_at.desc(),
        )
        .limit(1)
    )
    return appointment


def summarize_executive_profile(
    appointment: ExecutiveAppointment,
) -> ExecutiveProfileSummary:
    return ExecutiveProfileSummary(
        id=appointment.id,
        position=appointment.position,
        biography_html=sanitize_html(appointment.biography_html),
        social_links=appointment.social_links,
    )


def set_auth_cookies(
    response: Response,
    settings: Settings,
    *,
    session_token: str,
    csrf_token: str,
) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        domain=settings.session_cookie_domain,
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        domain=settings.session_cookie_domain,
        path="/",
        max_age=settings.session_ttl_seconds,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthResponse:
    email = normalize_email(str(payload.email))
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit("login-ip", client_ip, limit=25, period_seconds=900)
    await enforce_rate_limit("login-account", email, limit=8, period_seconds=900)

    user = await db.scalar(select(User).where(User.email == email))
    if user is None:
        raise ApiError(401, "invalid_credentials", "The email or password is incorrect")
    valid, upgrade = verify_password(user.password_hash, payload.password)
    if not valid:
        raise ApiError(401, "invalid_credentials", "The email or password is incorrect")
    if user.status != "active":
        raise ApiError(403, "account_unavailable", "This account is not currently active")

    now = datetime.now(UTC)
    session_token = new_token()
    csrf_token = new_token()
    expires_at = now + timedelta(seconds=settings.session_ttl_seconds)
    session = Session(
        id=new_id(),
        user_id=user.id,
        token_hash=token_digest(session_token),
        csrf_hash=token_digest(csrf_token),
        user_agent=request.headers.get("User-Agent", "")[:500],
        ip_prefix=client_ip[:80],
        created_at=now,
        last_seen_at=now,
        expires_at=expires_at,
    )
    db.add(session)
    if upgrade:
        user.password_hash = hash_password(payload.password)
    user.last_login_at = now
    await db.commit()

    from utag_api.dependencies import resolve_principal

    principal = await resolve_principal(db, session_token, touch=False)
    if principal is None:
        raise ApiError(500, "session_creation_failed", "Could not create the session")
    set_auth_cookies(
        response,
        settings,
        session_token=session_token,
        csrf_token=csrf_token,
    )
    return AuthResponse(
        user=summarize_user(principal), csrf_token=csrf_token, expires_at=expires_at
    )


@router.get("/me", response_model=UserSummary)
async def me(principal: CurrentPrincipal) -> UserSummary:
    return summarize_user(principal)


@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(principal: CurrentPrincipal, db: DbSession) -> list[SessionSummary]:
    now = datetime.now(UTC)
    sessions = (
        await db.scalars(
            select(Session)
            .where(
                Session.user_id == principal.user.id,
                Session.revoked_at.is_(None),
                Session.expires_at > now,
            )
            .order_by(Session.last_seen_at.desc())
        )
    ).all()
    return [
        SessionSummary(
            id=item.id,
            created_at=item.created_at,
            last_seen_at=item.last_seen_at,
            expires_at=item.expires_at,
            user_agent=item.user_agent,
            current=item.id == principal.session.id,
        )
        for item in sessions
    ]


@router.patch("/profile", response_model=UserSummary)
async def update_profile(
    payload: ProfileUpdate,
    request: Request,
    principal: MutationPrincipal,
    db: DbSession,
) -> UserSummary:
    changes = payload.model_dump(exclude_unset=True)
    unit_types = {
        "school_id": "school",
        "college_id": "college",
        "department_id": "department",
    }
    for field, expected_type in unit_types.items():
        unit_id = changes.get(field)
        if unit_id is None:
            continue
        unit = await db.get(OrganizationUnit, unit_id)
        if unit is None or unit.unit_type != expected_type or not unit.is_active:
            raise ApiError(422, "organization_unit_invalid", f"Select a valid {expected_type}")
    profile_media_id = changes.get("profile_media_id")
    if profile_media_id is not None:
        asset = await db.get(MediaAsset, profile_media_id)
        if (
            asset is None
            or asset.status != "ready"
            or not asset.content_type.startswith("image/")
            or asset.owner_id != principal.user.id
        ):
            raise ApiError(422, "profile_image_invalid", "Select one of your ready image uploads")
    for key, value in changes.items():
        setattr(principal.user, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="profile.updated",
        resource_type="user",
        resource_id=principal.user.id,
        topic=f"user:{principal.user.id}",
        payload={"user_id": str(principal.user.id)},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return summarize_user(principal)


@router.get("/executive-profile", response_model=ExecutiveProfileSummary | None)
async def executive_profile(
    principal: CurrentPrincipal,
    db: DbSession,
) -> ExecutiveProfileSummary | None:
    appointment = await current_executive_appointment(db, principal.user.id)
    return summarize_executive_profile(appointment) if appointment else None


@router.patch("/executive-profile", response_model=ExecutiveProfileSummary)
async def update_executive_profile(
    payload: ExecutiveProfileUpdate,
    request: Request,
    principal: MutationPrincipal,
    db: DbSession,
) -> ExecutiveProfileSummary:
    appointment = await current_executive_appointment(db, principal.user.id)
    if appointment is None:
        raise ApiError(
            404,
            "executive_appointment_not_found",
            "No active executive appointment is linked to this account",
        )

    appointment.biography_html = sanitize_html(payload.biography_html)
    appointment.social_links = {
        key: value.strip() for key, value in payload.social_links.items() if value.strip()
    }
    record_change(
        db,
        context=event_context(request, principal),
        action="executive.profile_updated",
        resource_type="executive_appointment",
        resource_id=appointment.id,
        topic="executives",
        payload={
            "appointment_id": str(appointment.id),
            "user_id": str(principal.user.id),
        },
        changes={
            "biography_html": {"updated": True},
            "social_links": {"to": sorted(appointment.social_links)},
        },
    )
    await db.commit()
    return summarize_executive_profile(appointment)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    principal: MutationPrincipal,
    db: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    principal.session.revoked_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="auth.session.revoked",
        resource_type="session",
        resource_id=principal.session.id,
        topic=f"user:{principal.user.id}",
        payload={"session_id": str(principal.session.id)},
    )
    await db.commit()
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        domain=settings.session_cookie_domain,
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        domain=settings.session_cookie_domain,
    )
    return MessageResponse(message="Signed out")


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: str,
    request: Request,
    principal: MutationPrincipal,
    db: DbSession,
) -> MessageResponse:
    try:
        from uuid import UUID

        target_id = UUID(session_id)
    except ValueError as exc:
        raise ApiError(404, "session_not_found", "Session not found") from exc
    target = await db.scalar(
        select(Session).where(Session.id == target_id, Session.user_id == principal.user.id)
    )
    if target is None:
        raise ApiError(404, "session_not_found", "Session not found")
    target.revoked_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="auth.session.revoked",
        resource_type="session",
        resource_id=target.id,
        topic=f"user:{principal.user.id}",
        payload={"session_id": str(target.id)},
    )
    await db.commit()
    return MessageResponse(message="Session revoked")


@router.post("/password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    principal: MutationPrincipal,
    db: DbSession,
) -> MessageResponse:
    valid, _ = verify_password(principal.user.password_hash, payload.current_password)
    if not valid:
        raise ApiError(400, "current_password_invalid", "The current password is incorrect")
    errors = strong_password_errors(payload.new_password)
    if errors:
        raise ApiError(422, "weak_password", "Choose a stronger password", details=errors)
    principal.user.password_hash = hash_password(payload.new_password)
    principal.user.must_change_password = False
    now = datetime.now(UTC)
    await db.execute(
        update(Session)
        .where(
            Session.user_id == principal.user.id,
            Session.id != principal.session.id,
            Session.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="auth.password.changed",
        resource_type="user",
        resource_id=principal.user.id,
        topic=f"user:{principal.user.id}",
        payload={"user_id": str(principal.user.id)},
    )
    await db.commit()
    return MessageResponse(message="Password updated")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: DbSession,
) -> MessageResponse:
    email = normalize_email(str(payload.email))
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit("password-reset", client_ip, limit=8, period_seconds=3600)
    user = await db.scalar(select(User).where(User.email == email, User.status == "active"))
    if user is not None:
        now = datetime.now(UTC)
        raw_token = new_token()
        db.add(
            AccountToken(
                user_id=user.id,
                kind="password_reset",
                token_hash=token_digest(raw_token),
                created_at=now,
                expires_at=now + timedelta(minutes=30),
            )
        )
        # The worker sends the token. It is intentionally never returned by the API.
        from utag_api.worker.tasks import send_password_reset

        await db.commit()
        send_password_reset.delay(str(user.id), raw_token)
    return MessageResponse(
        message="If the account exists, password reset instructions will be sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: DbSession) -> MessageResponse:
    errors = strong_password_errors(payload.password)
    if errors:
        raise ApiError(422, "weak_password", "Choose a stronger password", details=errors)
    now = datetime.now(UTC)
    account_token = await db.scalar(
        select(AccountToken).where(
            AccountToken.kind == "password_reset",
            AccountToken.token_hash == token_digest(payload.token),
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
    )
    if account_token is None:
        raise ApiError(400, "reset_token_invalid", "The reset link is invalid or has expired")
    user = await db.get(User, account_token.user_id)
    if user is None or user.status != "active":
        raise ApiError(400, "reset_token_invalid", "The reset link is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    user.must_change_password = False
    account_token.used_at = now
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    record_change(
        db,
        context=EventContext(actor_id=user.id, request_id=None),
        action="auth.password.reset",
        resource_type="user",
        resource_id=user.id,
        topic=f"user:{user.id}",
        payload={"user_id": str(user.id)},
    )
    await db.commit()
    return MessageResponse(message="Password reset. You can now sign in")


@router.post("/accept-invitation", response_model=MessageResponse)
async def accept_invitation(payload: AcceptInvitationRequest, db: DbSession) -> MessageResponse:
    errors = strong_password_errors(payload.password)
    if errors:
        raise ApiError(422, "weak_password", "Choose a stronger password", details=errors)
    now = datetime.now(UTC)
    account_token = await db.scalar(
        select(AccountToken).where(
            AccountToken.kind == "invitation",
            AccountToken.token_hash == token_digest(payload.token),
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
    )
    if account_token is None:
        raise ApiError(400, "invitation_invalid", "The invitation is invalid or has expired")
    user = await db.get(User, account_token.user_id)
    if user is None or user.status not in {"invited", "active"}:
        raise ApiError(400, "invitation_invalid", "The invitation is invalid or has expired")
    user.password_hash = hash_password(payload.password)
    user.must_change_password = False
    user.email_verified = True
    user.status = "active"
    account_token.used_at = now
    record_change(
        db,
        context=EventContext(actor_id=user.id, request_id=None),
        action="auth.invitation.accepted",
        resource_type="user",
        resource_id=user.id,
        topic=f"user:{user.id}",
        payload={"user_id": str(user.id)},
    )
    await db.commit()
    return MessageResponse(message="Account activated. You can now sign in")
