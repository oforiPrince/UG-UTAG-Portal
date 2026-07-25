from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.config import Settings, get_settings
from utag_api.database import get_db
from utag_api.errors import ApiError
from utag_api.models import Session, User
from utag_api.security import constant_time_equal, token_digest
from utag_api.services.events import EventContext
from utag_api.services.identity import load_user_access

DbSession = Annotated[AsyncSession, Depends(get_db)]


@dataclass(slots=True)
class Principal:
    user: User
    session: Session
    roles: set[str]
    permissions: set[str]


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


def event_context(request: Request, principal: Principal | None = None) -> EventContext:
    forwarded = request.headers.get("X-Forwarded-For", "")
    ip_address = forwarded.split(",", 1)[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    return EventContext(
        actor_id=principal.user.id if principal else None,
        request_id=request.headers.get("X-Request-ID"),
        metadata={"ip": ip_address, "user_agent": request.headers.get("User-Agent", "")[:500]},
    )
