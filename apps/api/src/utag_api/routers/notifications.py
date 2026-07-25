from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, update

from utag_api.database import new_id
from utag_api.dependencies import (
    CurrentPrincipal,
    DbSession,
    MutationPrincipal,
    Principal,
    event_context,
    require_mutation_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import Notification, User
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import NotificationCreate, NotificationView
from utag_api.services.content import sanitize_html
from utag_api.services.events import record_change
from utag_api.services.query import paginate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationView])
async def list_notifications(
    db: DbSession,
    principal: CurrentPrincipal,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 30,
    unread_only: bool = False,
) -> Page[NotificationView]:
    statement = select(Notification).where(
        Notification.user_id == principal.user.id,
        Notification.archived_at.is_(None),
    )
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    statement = statement.order_by(Notification.created_at.desc())
    result = await paginate(db, statement, page=page, page_size=page_size)
    return Page[NotificationView](
        items=[NotificationView.model_validate(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/unread-count")
async def unread_count(db: DbSession, principal: CurrentPrincipal) -> dict[str, int]:
    count = int(
        (
            await db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == principal.user.id,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                )
            )
        )
        or 0
    )
    return {"unread": count}


@router.post("/{notification_id}/read", response_model=MessageResponse)
async def mark_read(
    notification_id: UUID,
    request: Request,
    db: DbSession,
    principal: MutationPrincipal,
) -> MessageResponse:
    item = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == principal.user.id,
        )
    )
    if item is None:
        raise ApiError(404, "notification_not_found", "Notification not found")
    item.read_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="notification.read",
        resource_type="notification",
        resource_id=item.id,
        topic=f"user:{principal.user.id}",
        payload={"notification_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Notification marked as read")


@router.delete("/{notification_id}", response_model=MessageResponse)
async def archive_notification(
    notification_id: UUID,
    request: Request,
    db: DbSession,
    principal: MutationPrincipal,
) -> MessageResponse:
    item = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == principal.user.id,
        )
    )
    if item is None:
        raise ApiError(404, "notification_not_found", "Notification not found")
    item.archived_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="notification.archived",
        resource_type="notification",
        resource_id=item.id,
        topic=f"user:{principal.user.id}",
        payload={"notification_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Notification archived")


@router.post("/read-all", response_model=MessageResponse)
async def mark_all_read(
    request: Request, db: DbSession, principal: MutationPrincipal
) -> MessageResponse:
    now = datetime.now(UTC)
    await db.execute(
        update(Notification)
        .where(Notification.user_id == principal.user.id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="notification.read_all",
        resource_type="user",
        resource_id=principal.user.id,
        topic=f"user:{principal.user.id}",
        payload={"read_at": now.isoformat()},
    )
    await db.commit()
    return MessageResponse(message="All notifications marked as read")


@router.post("/send", response_model=MessageResponse)
async def send_notifications(
    payload: NotificationCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("notifications.manage"))],
) -> MessageResponse:
    valid_users = set(
        (
            await db.scalars(
                select(User.id).where(User.id.in_(set(payload.user_ids)), User.status == "active")
            )
        ).all()
    )
    if len(valid_users) != len(set(payload.user_ids)):
        raise ApiError(422, "invalid_recipients", "One or more recipients are invalid")
    for user_id in valid_users:
        item = Notification(
            id=new_id(),
            user_id=user_id,
            category=payload.category,
            priority=payload.priority,
            title=payload.title,
            body=sanitize_html(payload.body),
            resource_type=payload.resource_type,
            resource_id=payload.resource_id,
            deep_link=payload.deep_link,
        )
        db.add(item)
        record_change(
            db,
            context=event_context(request, principal),
            action="notification.created",
            resource_type="notification",
            resource_id=item.id,
            topic=f"user:{user_id}",
            payload={
                "notification_id": str(item.id),
                "category": item.category,
                "priority": item.priority,
            },
        )
    await db.commit()
    return MessageResponse(message=f"Notification sent to {len(valid_users)} members")
