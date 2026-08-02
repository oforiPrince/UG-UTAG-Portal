from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address, ip_network
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.config import Settings, get_settings
from utag_api.database import get_db
from utag_api.errors import ApiError
from utag_api.models import ExecutiveAppointment, Session, User
from utag_api.security import constant_time_equal, token_digest
from utag_api.services.events import EventContext
from utag_api.services.executives import executive_public_profile_incomplete
from utag_api.services.identity import load_user_access

DbSession = Annotated[AsyncSession, Depends(get_db)]
RESTRICTED_SESSION_PATHS = {
    "/api/v1/auth/logout",
    "/api/v1/auth/me",
    "/api/v1/auth/password",
    "/api/v1/auth/profile",
    "/api/v1/auth/executive-profile",
    "/api/v1/organization/units",
}
# Keep the old name as an alias for any lingering imports/tests.
PASSWORD_CHANGE_PATHS = RESTRICTED_SESSION_PATHS


@dataclass(slots=True)
class Principal:
    user: User
    session: Session
    roles: set[str]
    permissions: set[str]
    must_complete_executive_profile: bool = False


def session_path_allowed(path: str) -> bool:
    if path in RESTRICTED_SESSION_PATHS:
        return True
    return path == "/api/v1/media" or path.startswith("/api/v1/media/")


async def active_executive_appointment(
    db: AsyncSession, user_id: UUID
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


async def resolve_principal(
    db: AsyncSession,
    raw_token: str | None,
    *,
    touch: bool = True,
) -> Principal | None:
    if not raw_token:
        return None
    now = datetime.now(UTC)
    statement = (
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(
            Session.token_hash == token_digest(raw_token),
            Session.revoked_at.is_(None),
            Session.expires_at > now,
            User.status == "active",
        )
    )
    row = (await db.execute(statement)).one_or_none()
    if row is None:
        return None
    session, user = row
    access = await load_user_access(db, user.id)
    appointment = await active_executive_appointment(db, user.id)
    last_seen = session.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if touch and last_seen < now - timedelta(minutes=5):
        session.last_seen_at = now
        await db.commit()
    return Principal(
        user=user,
        session=session,
        roles=access.roles,
        permissions=access.effective_permissions,
        must_complete_executive_profile=executive_public_profile_incomplete(user, appointment),
    )


async def get_current_principal(
    db: DbSession,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> Principal:
    session_cookie = request.cookies.get(settings.session_cookie_name)
    principal = await resolve_principal(db, session_cookie)
    if principal is None:
        raise ApiError(401, "authentication_required", "Please sign in to continue")
    if principal.user.must_change_password and not session_path_allowed(request.url.path):
        raise ApiError(
            403,
            "password_change_required",
            "Change your temporary password before continuing",
        )
    if principal.must_complete_executive_profile and not session_path_allowed(request.url.path):
        raise ApiError(
            403,
            "executive_profile_required",
            "Complete your public executive profile before continuing",
        )
    return principal


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def get_mutation_principal(
    principal: CurrentPrincipal,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> Principal:
    if not csrf_header or not constant_time_equal(
        token_digest(csrf_header), principal.session.csrf_hash
    ):
        raise ApiError(403, "csrf_failed", "The security token is missing or invalid")
    return principal


MutationPrincipal = Annotated[Principal, Depends(get_mutation_principal)]


def require_permissions(*required: str):  # type: ignore[no-untyped-def]
    async def permission_dependency(principal: CurrentPrincipal) -> Principal:
        missing = set(required) - principal.permissions
        if missing:
            raise ApiError(
                403,
                "permission_denied",
                "You do not have permission to perform this action",
                details={"missing": sorted(missing)},
            )
        return principal

    return permission_dependency


def require_mutation_permissions(*required: str):  # type: ignore[no-untyped-def]
    async def permission_dependency(principal: MutationPrincipal) -> Principal:
        missing = set(required) - principal.permissions
        if missing:
            raise ApiError(
                403,
                "permission_denied",
                "You do not have permission to perform this action",
                details={"missing": sorted(missing)},
            )
        return principal

    return permission_dependency


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    networks = tuple(ip_network(network) for network in get_settings().trusted_proxy_cidrs)
    try:
        peer_address = ip_address(peer)
        trusted = any(peer_address in network for network in networks)
    except ValueError:
        trusted = False
    if trusted:
        forwarded_addresses = []
        for forwarded_value in request.headers.get("X-Forwarded-For", "").split(","):
            forwarded_value = forwarded_value.strip()
            try:
                forwarded_addresses.append(ip_address(forwarded_value))
            except ValueError:
                continue
        for forwarded_address in reversed(forwarded_addresses):
            if not any(forwarded_address in network for network in networks):
                return str(forwarded_address)
        if forwarded_addresses:
            return str(forwarded_addresses[0])
    return peer


def event_context(request: Request, principal: Principal | None = None) -> EventContext:
    return EventContext(
        actor_id=principal.user.id if principal else None,
        request_id=request.headers.get("X-Request-ID"),
        metadata={
            "ip": client_ip(request),
            "user_agent": request.headers.get("User-Agent", "")[:500],
        },
    )
