from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import delete, func, or_, select

from utag_api.database import new_id
from utag_api.dependencies import (
    CurrentPrincipal,
    DbSession,
    MutationPrincipal,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import Event, EventAttachment, EventRegistration, MediaAsset, Notification
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import EventCreate, EventView
from utag_api.security import decrypt_text, encrypt_text
from utag_api.services.content import sanitize_html
from utag_api.services.deletion import (
    DeleteBlocker,
    block_delete_if_referenced,
    commit_permanent_delete,
    count_rows,
)
from utag_api.services.events import record_change
from utag_api.services.moderation import ensure_publish_permission
from utag_api.services.query import paginate, unique_slug

router = APIRouter(prefix="/events", tags=["events"])


def serialize_event(
    item: Event,
    registrations: int,
    registered: bool,
    featured_media_name: str | None = None,
    attachments: list[dict[str, object]] | None = None,
) -> EventView:
    attachment_items = attachments or []
    return EventView(
        **{key: value for key, value in item.__dict__.items() if not key.startswith("_")},
        registrations=registrations,
        registered=registered,
        featured_media_name=featured_media_name,
        supplementary_media_ids=[item["media_asset_id"] for item in attachment_items],
        attachments=attachment_items,
    )


async def event_media_names(db: DbSession, events: list[Event]) -> dict[UUID, str]:
    media_ids = {event.featured_media_id for event in events if event.featured_media_id is not None}
    return {
        asset.id: asset.original_filename
        for asset in (
            await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids)))
        ).all()
    }


async def event_attachment_map(
    db: DbSession, event_ids: list[UUID], *, public: bool = False
) -> dict[UUID, list[dict[str, object]]]:
    if not event_ids:
        return {}
    statement = (
        select(EventAttachment, MediaAsset)
        .join(MediaAsset, MediaAsset.id == EventAttachment.media_asset_id)
        .where(EventAttachment.event_id.in_(event_ids))
        .order_by(EventAttachment.event_id, EventAttachment.position)
    )
    if public:
        statement = statement.where(MediaAsset.status == "ready", MediaAsset.is_private.is_(False))
    rows = (await db.execute(statement)).all()
    result: dict[UUID, list[dict[str, object]]] = {}
    for attachment, asset in rows:
        result.setdefault(attachment.event_id, []).append(
            {
                "media_asset_id": asset.id,
                "filename": asset.original_filename,
                "content_type": asset.content_type,
                "byte_size": asset.byte_size,
                "content_url": (
                    f"/api/v1/public/media/{asset.id}"
                    if public
                    else f"/api/v1/media/{asset.id}/content"
                ),
            }
        )
    return result


async def validate_event_attachments(
    db: DbSession, media_asset_ids: list[UUID]
) -> list[MediaAsset]:
    if not media_asset_ids:
        return []
    unique_ids = list(dict.fromkeys(media_asset_ids))
    assets = list((await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(unique_ids)))).all())
    if len(assets) != len(unique_ids) or any(
        asset.status != "ready" or asset.is_private for asset in assets
    ):
        raise ApiError(
            409,
            "event_attachment_invalid",
            "Choose public files that have completed security scanning",
        )
    by_id = {asset.id: asset for asset in assets}
    return [by_id[asset_id] for asset_id in unique_ids]


async def event_counts(
    db: DbSession, event_ids: list[UUID], user_id: UUID
) -> tuple[dict[UUID, int], set[UUID]]:
    if not event_ids:
        return {}, set()
    count_rows = (
        await db.execute(
            select(EventRegistration.event_id, func.count(EventRegistration.id))
            .where(
                EventRegistration.event_id.in_(event_ids),
                EventRegistration.status != "cancelled",
            )
            .group_by(EventRegistration.event_id)
        )
    ).all()
    counts: dict[UUID, int] = {event_id: count for event_id, count in count_rows}
    registrations = set(
        (
            await db.scalars(
                select(EventRegistration.event_id).where(
                    EventRegistration.event_id.in_(event_ids),
                    EventRegistration.user_id == user_id,
                    EventRegistration.status != "cancelled",
                )
            )
        ).all()
    )
    return counts, registrations


@router.get("", response_model=Page[EventView])
async def list_events(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("dashboard.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    status: str | None = None,
    publication_status: str | None = None,
    q: str | None = None,
) -> Page[EventView]:
    statement = select(Event).order_by(Event.start_date.desc(), Event.start_time.desc())
    if "events.manage" not in principal.permissions:
        statement = statement.where(Event.publication_status == "published")
    if status:
        statement = statement.where(Event.status == status)
    if publication_status:
        statement = statement.where(Event.publication_status == publication_status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(Event.title.ilike(pattern), Event.venue.ilike(pattern)))
    result = await paginate(db, statement, page=page, page_size=page_size)
    counts, registered = await event_counts(
        db, [item.id for item in result.items], principal.user.id
    )
    media_names = await event_media_names(db, list(result.items))
    attachments = await event_attachment_map(db, [item.id for item in result.items])
    return Page[EventView](
        items=[
            serialize_event(
                item,
                counts.get(item.id, 0),
                item.id in registered,
                (media_names.get(item.featured_media_id) if item.featured_media_id else None),
                attachments.get(item.id, []),
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/{event_id}", response_model=EventView)
async def get_event(event_id: UUID, db: DbSession, principal: CurrentPrincipal) -> EventView:
    item = await db.get(Event, event_id)
    if item is None or (
        item.publication_status != "published" and "events.manage" not in principal.permissions
    ):
        raise ApiError(404, "event_not_found", "Event not found")
    counts, registered = await event_counts(db, [item.id], principal.user.id)
    media_names = await event_media_names(db, [item])
    attachments = await event_attachment_map(db, [item.id])
    return serialize_event(
        item,
        counts.get(item.id, 0),
        item.id in registered,
        (media_names.get(item.featured_media_id) if item.featured_media_id else None),
        attachments.get(item.id, []),
    )


@router.post("", response_model=EventView, status_code=201)
async def create_event(
    payload: EventCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("events.manage"))],
) -> EventView:
    ensure_publish_permission(principal.permissions, payload.publication_status)
    featured_media: MediaAsset | None = None
    if payload.featured_media_id is not None:
        featured_media = await db.get(MediaAsset, payload.featured_media_id)
        if featured_media is None or featured_media.status != "ready" or featured_media.is_private:
            raise ApiError(
                422,
                "featured_media_invalid",
                "Choose a ready public image from the media library",
            )
    attachment_assets = await validate_event_attachments(db, payload.supplementary_media_ids)
    data = payload.model_dump(
        exclude={"slug", "online_link", "access_code", "supplementary_media_ids"}
    )
    data["description_html"] = sanitize_html(payload.description_html)
    data["location_url"] = str(payload.location_url) if payload.location_url else None
    data["photos_url"] = str(payload.photos_url) if payload.photos_url else None
    data["registration_url"] = str(payload.registration_url) if payload.registration_url else None
    data["online_link_encrypted"] = encrypt_text(payload.online_link)
    data["access_code_encrypted"] = encrypt_text(payload.access_code)
    if payload.publication_status == "published" and not payload.published_at:
        data["published_at"] = datetime.now(UTC)
    item = Event(
        id=new_id(),
        slug=await unique_slug(db, Event, payload.title, payload.slug),
        created_by_id=principal.user.id,
        **data,
    )
    db.add(item)
    await db.flush()
    db.add_all(
        [
            EventAttachment(
                id=new_id(),
                event_id=item.id,
                media_asset_id=asset.id,
                position=position,
            )
            for position, asset in enumerate(attachment_assets)
        ]
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="event.created",
        resource_type="event",
        resource_id=item.id,
        topic="events",
        payload={"event_id": str(item.id), "status": item.status},
    )
    await db.commit()
    return serialize_event(
        item,
        0,
        False,
        featured_media.original_filename if featured_media else None,
        (await event_attachment_map(db, [item.id])).get(item.id, []),
    )


@router.put("/{event_id}", response_model=EventView)
async def update_event(
    event_id: UUID,
    payload: EventCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("events.manage"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> EventView:
    item = await db.scalar(select(Event).where(Event.id == event_id).with_for_update())
    if item is None:
        raise ApiError(404, "event_not_found", "Event not found")
    if if_match != f'"{item.version}"':
        raise ApiError(412, "version_conflict", "Refresh this event before saving")
    ensure_publish_permission(principal.permissions, payload.publication_status)
    featured_media: MediaAsset | None = None
    if payload.featured_media_id is not None:
        featured_media = await db.get(MediaAsset, payload.featured_media_id)
        if featured_media is None or featured_media.status != "ready" or featured_media.is_private:
            raise ApiError(
                422,
                "featured_media_invalid",
                "Choose a ready public image from the media library",
            )
    attachment_assets = await validate_event_attachments(db, payload.supplementary_media_ids)
    data = payload.model_dump(
        exclude={"slug", "online_link", "access_code", "supplementary_media_ids"}
    )
    data["description_html"] = sanitize_html(payload.description_html)
    data["location_url"] = str(payload.location_url) if payload.location_url else None
    data["photos_url"] = str(payload.photos_url) if payload.photos_url else None
    data["registration_url"] = str(payload.registration_url) if payload.registration_url else None
    if payload.online_link is not None:
        data["online_link_encrypted"] = encrypt_text(payload.online_link)
    if payload.access_code is not None:
        data["access_code_encrypted"] = encrypt_text(payload.access_code)
    if payload.publication_status == "published" and not item.published_at:
        data["published_at"] = datetime.now(UTC)
    for key, value in data.items():
        setattr(item, key, value)
    await db.execute(delete(EventAttachment).where(EventAttachment.event_id == item.id))
    db.add_all(
        [
            EventAttachment(
                id=new_id(),
                event_id=item.id,
                media_asset_id=asset.id,
                position=position,
            )
            for position, asset in enumerate(attachment_assets)
        ]
    )
    item.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="event.updated",
        resource_type="event",
        resource_id=item.id,
        topic="events",
        payload={"event_id": str(item.id), "status": item.status, "version": item.version},
    )
    await db.commit()
    count = int(
        (
            await db.scalar(
                select(func.count(EventRegistration.id)).where(
                    EventRegistration.event_id == item.id,
                    EventRegistration.status != "cancelled",
                )
            )
        )
        or 0
    )
    return serialize_event(
        item,
        count,
        False,
        featured_media.original_filename if featured_media else None,
        (await event_attachment_map(db, [item.id])).get(item.id, []),
    )


@router.delete("/{event_id}", response_model=MessageResponse)
async def archive_event(
    event_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("events.manage"))],
) -> MessageResponse:
    item = await db.get(Event, event_id)
    if item is None:
        raise ApiError(404, "event_not_found", "Event not found")
    item.status = "cancelled"
    item.publication_status = "archived"
    item.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="event.archived",
        resource_type="event",
        resource_id=item.id,
        topic="events",
        payload={"event_id": str(item.id), "version": item.version},
    )
    await db.commit()
    return MessageResponse(message="Event archived")


@router.delete("/{event_id}/permanent", response_model=MessageResponse)
async def delete_event_permanently(
    event_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[
        Principal,
        Depends(require_mutation_permissions("records.delete", "events.manage")),
    ],
) -> MessageResponse:
    item = await db.get(Event, event_id, with_for_update=True)
    if item is None:
        raise ApiError(404, "event_not_found", "Event not found")
    registrations = await count_rows(
        db,
        EventRegistration,
        EventRegistration.event_id == item.id,
    )
    notifications = await count_rows(
        db,
        Notification,
        Notification.resource_type == "event",
        Notification.resource_id == item.id,
    )
    block_delete_if_referenced(
        "event",
        [
            DeleteBlocker("registration record", registrations),
            DeleteBlocker("member notification", notifications),
        ],
        guidance=("Events with participant or communication history must be archived instead"),
    )
    await db.execute(delete(EventAttachment).where(EventAttachment.event_id == item.id))
    record_change(
        db,
        context=event_context(request, principal),
        action="event.deleted",
        resource_type="event",
        resource_id=item.id,
        topic="events",
        payload={"event_id": str(item.id), "slug": item.slug},
    )
    await db.delete(item)
    await commit_permanent_delete(db, "event")
    return MessageResponse(message="Event deleted permanently")


@router.post("/{event_id}/registration", response_model=MessageResponse)
async def register_for_event(
    event_id: UUID,
    request: Request,
    db: DbSession,
    principal: MutationPrincipal,
) -> MessageResponse:
    item = await db.scalar(select(Event).where(Event.id == event_id).with_for_update())
    if item is None or item.publication_status != "published":
        raise ApiError(404, "event_not_found", "Event not found")
    now = datetime.now(UTC)
    if not item.registration_required:
        raise ApiError(409, "registration_not_required", "This event does not use registration")
    if item.registration_deadline and item.registration_deadline < now:
        raise ApiError(409, "registration_closed", "Registration has closed")
    registration = await db.scalar(
        select(EventRegistration).where(
            EventRegistration.event_id == item.id,
            EventRegistration.user_id == principal.user.id,
        )
    )
    if registration is not None and registration.status == "registered":
        return MessageResponse(message="Registration confirmed")
    count = int(
        (
            await db.scalar(
                select(func.count(EventRegistration.id)).where(
                    EventRegistration.event_id == item.id,
                    EventRegistration.status != "cancelled",
                )
            )
        )
        or 0
    )
    if item.max_participants and count >= item.max_participants:
        raise ApiError(409, "event_full", "This event is at capacity")
    if registration is None:
        registration = EventRegistration(
            id=new_id(), event_id=item.id, user_id=principal.user.id, status="registered"
        )
        db.add(registration)
    else:
        registration.status = "registered"
    record_change(
        db,
        context=event_context(request, principal),
        action="event.registration.created",
        resource_type="event_registration",
        resource_id=registration.id,
        topic=f"event:{item.id}",
        payload={"event_id": str(item.id), "registrations": count + 1},
    )
    await db.commit()
    return MessageResponse(message="Registration confirmed")


@router.delete("/{event_id}/registration", response_model=MessageResponse)
async def cancel_registration(
    event_id: UUID,
    request: Request,
    db: DbSession,
    principal: MutationPrincipal,
) -> MessageResponse:
    registration = await db.scalar(
        select(EventRegistration).where(
            EventRegistration.event_id == event_id,
            EventRegistration.user_id == principal.user.id,
        )
    )
    if registration is None:
        raise ApiError(404, "registration_not_found", "Registration not found")
    registration.status = "cancelled"
    record_change(
        db,
        context=event_context(request, principal),
        action="event.registration.cancelled",
        resource_type="event_registration",
        resource_id=registration.id,
        topic=f"event:{event_id}",
        payload={"event_id": str(event_id)},
    )
    await db.commit()
    return MessageResponse(message="Registration cancelled")


@router.get("/{event_id}/access")
async def event_access(
    event_id: UUID, db: DbSession, principal: CurrentPrincipal
) -> dict[str, str | None]:
    item = await db.get(Event, event_id)
    if item is None or (
        "events.manage" not in principal.permissions
        and (item.publication_status != "published" or item.status in {"cancelled", "completed"})
    ):
        raise ApiError(404, "event_not_found", "Event not found")
    registration = await db.scalar(
        select(EventRegistration.id).where(
            EventRegistration.event_id == item.id,
            EventRegistration.user_id == principal.user.id,
            EventRegistration.status != "cancelled",
        )
    )
    if registration is None and "events.manage" not in principal.permissions:
        raise ApiError(403, "event_access_denied", "Register to view the online event details")
    return {
        "online_platform": item.online_platform,
        "online_link": decrypt_text(item.online_link_encrypted),
        "access_code": decrypt_text(item.access_code_encrypted),
    }
