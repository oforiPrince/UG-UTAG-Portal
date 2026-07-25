from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from starlette.concurrency import run_in_threadpool

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.dependencies import DbSession, event_context
from utag_api.errors import ApiError
from utag_api.models import (
    AdCampaign,
    AdSlot,
    Article,
    BackgroundJob,
    Document,
    DocumentFile,
    Event,
    EventRegistration,
    ExecutiveAppointment,
    Gallery,
    GalleryItem,
    MediaAsset,
    OrganizationUnit,
    SiteSetting,
    User,
)
from utag_api.rate_limit import enforce_rate_limit
from utag_api.routers.content import article_views
from utag_api.routers.events import event_attachment_map, serialize_event
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    AdCampaignView,
    ArticleView,
    ContactRequest,
    EventView,
    PublicExecutiveView,
    SearchResult,
)
from utag_api.services.content import sanitize_html
from utag_api.services.events import record_change
from utag_api.services.executives import (
    executive_row_order_key,
    is_executive_officer_position,
)
from utag_api.services.query import paginate
from utag_api.services.storage import s3_client, safe_filename

router = APIRouter(prefix="/public", tags=["public website"])


async def public_executive_views(
    db: DbSession,
    rows: list[tuple[ExecutiveAppointment, User]],
) -> list[PublicExecutiveView]:
    unit_ids = {
        unit_id
        for _, user in rows
        for unit_id in (user.school_id, user.college_id, user.department_id)
        if unit_id is not None
    }
    units = (
        (await db.scalars(select(OrganizationUnit).where(OrganizationUnit.id.in_(unit_ids)))).all()
        if unit_ids
        else []
    )
    unit_names = {unit.id: unit.name for unit in units}
    return [
        PublicExecutiveView(
            **{
                key: value for key, value in appointment.__dict__.items() if not key.startswith("_")
            },
            full_name=user.full_name,
            title=user.title,
            academic_rank=user.academic_rank,
            profile_media_id=user.profile_media_id,
            email=user.email,
            phone_number=user.phone_number,
            school_name=unit_names.get(user.school_id) if user.school_id else None,
            college_name=unit_names.get(user.college_id) if user.college_id else None,
            department_name=unit_names.get(user.department_id) if user.department_id else None,
        )
        for appointment, user in rows
    ]


def public_setting_value(setting: SiteSetting) -> dict[str, Any]:
    if setting.key != "site.carousel":
        return setting.value
    slides = setting.value.get("slides", [])
    if not isinstance(slides, list):
        slides = []
    public_slides = [
        slide
        for slide in slides
        if isinstance(slide, dict)
        and slide.get("is_published") is True
        and slide.get("archived") is not True
    ]
    return {**setting.value, "slides": sorted(public_slides, key=lambda row: row.get("order", 0))}


@router.get("/home")
async def home(db: DbSession) -> dict[str, Any]:
    now = datetime.now(UTC)
    articles = (
        await db.scalars(
            select(Article)
            .where(Article.status == "published", Article.published_at <= now)
            .order_by(Article.is_featured.desc(), Article.published_at.desc())
            .limit(6)
        )
    ).all()
    events = (
        await db.scalars(
            select(Event)
            .where(
                Event.publication_status == "published",
                Event.published_at <= now,
                Event.start_date >= now.date(),
            )
            .order_by(Event.start_date, Event.start_time)
            .limit(5)
        )
    ).all()
    leadership = sorted(
        [
            (appointment, user)
            for appointment, user in (
                await db.execute(
                    select(ExecutiveAppointment, User)
                    .join(User, User.id == ExecutiveAppointment.user_id)
                    .where(
                        ExecutiveAppointment.is_active.is_(True),
                        ExecutiveAppointment.is_public.is_(True),
                    )
                )
            ).all()
        ],
        key=lambda row: executive_row_order_key(row[0], row[1]),
    )
    leadership = [row for row in leadership if is_executive_officer_position(row[0].position)][:5]
    settings = {
        item.key: public_setting_value(item)
        for item in (
            await db.scalars(select(SiteSetting).where(SiteSetting.is_public.is_(True)))
        ).all()
    }
    return {
        "generated_at": now,
        "settings": settings,
        "featured_articles": await article_views(db, list(articles), public=True),
        "upcoming_events": [serialize_event(item, 0, False) for item in events],
        "leadership": await public_executive_views(db, leadership),
    }


@router.get("/articles", response_model=Page[ArticleView])
async def articles(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 12,
    tag: str | None = None,
) -> Page[ArticleView]:
    now = datetime.now(UTC)
    statement = (
        select(Article)
        .where(Article.status == "published", Article.published_at <= now)
        .order_by(Article.published_at.desc())
    )
    if tag:
        # JSON containment differs between PostgreSQL and SQLite; narrow after title/tag search.
        statement = statement.where(Article.tags.contains([tag]))
    result = await paginate(db, statement, page=page, page_size=page_size)
    return Page[ArticleView](
        items=await article_views(db, list(result.items), public=True),
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/articles/{slug}", response_model=ArticleView)
async def article(slug: str, db: DbSession) -> ArticleView:
    now = datetime.now(UTC)
    item = await db.scalar(
        select(Article).where(
            Article.slug == slug,
            Article.status == "published",
            Article.published_at <= now,
        )
    )
    if item is None:
        raise ApiError(404, "article_not_found", "Article not found")
    return (await article_views(db, [item], public=True))[0]


@router.get("/events", response_model=Page[EventView])
async def events(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 12,
    include_past: bool = False,
) -> Page[EventView]:
    now = datetime.now(UTC)
    statement = select(Event).where(
        Event.publication_status == "published",
        Event.published_at <= now,
    )
    if not include_past:
        statement = statement.where(Event.start_date >= now.date())
    statement = statement.order_by(Event.start_date, Event.start_time)
    result = await paginate(db, statement, page=page, page_size=page_size)
    attachments = await event_attachment_map(db, [item.id for item in result.items], public=True)
    return Page[EventView](
        items=[
            serialize_event(
                item,
                0,
                False,
                attachments=attachments.get(item.id, []),
            )
            for item in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/events/{slug}", response_model=EventView)
async def event(slug: str, db: DbSession) -> EventView:
    now = datetime.now(UTC)
    item = await db.scalar(
        select(Event).where(
            Event.slug == slug,
            Event.publication_status == "published",
            Event.published_at <= now,
        )
    )
    if item is None:
        raise ApiError(404, "event_not_found", "Event not found")
    registrations = int(
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
    attachments = await event_attachment_map(db, [item.id], public=True)
    return serialize_event(
        item,
        registrations,
        False,
        attachments=attachments.get(item.id, []),
    )


@router.get("/leadership", response_model=list[PublicExecutiveView])
async def leadership(db: DbSession, include_past: bool = False) -> list[PublicExecutiveView]:
    statement = (
        select(ExecutiveAppointment, User)
        .join(User, User.id == ExecutiveAppointment.user_id)
        .where(ExecutiveAppointment.is_public.is_(True))
    )
    if not include_past:
        statement = statement.where(ExecutiveAppointment.is_active.is_(True))
    rows = sorted(
        [(appointment, user) for appointment, user in (await db.execute(statement)).all()],
        key=lambda row: executive_row_order_key(row[0], row[1]),
    )
    return await public_executive_views(db, rows)


async def public_gallery_data(db: DbSession, gallery: Gallery) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(GalleryItem, MediaAsset)
            .join(MediaAsset, MediaAsset.id == GalleryItem.media_asset_id)
            .where(
                GalleryItem.gallery_id == gallery.id,
                MediaAsset.status == "ready",
                MediaAsset.is_private.is_(False),
            )
            .order_by(GalleryItem.position)
        )
    ).all()
    images = [
        {
            "id": asset.id,
            "caption": item.caption,
            "alt_text": asset.alt_text,
            "credit": asset.credit,
            "url": f"/api/v1/public/media/{asset.id}",
            "allow_download": item.allow_download,
            "download_url": (
                f"/api/v1/public/galleries/{gallery.slug}/media/{asset.id}/download"
                if item.allow_download
                else None
            ),
            "original_filename": asset.original_filename,
        }
        for item, asset in rows
    ]
    return {
        "id": gallery.id,
        "slug": gallery.slug,
        "title": gallery.title,
        "description": sanitize_html(gallery.description),
        "external_album_url": gallery.external_album_url,
        "published_at": gallery.published_at,
        "image_count": len(images),
        "cover_media_id": images[0]["id"] if images else None,
        "images": images,
    }


@router.get("/galleries")
async def galleries(db: DbSession) -> list[dict[str, Any]]:
    rows = (
        await db.scalars(
            select(Gallery)
            .where(Gallery.status == "published")
            .order_by(Gallery.published_at.desc())
        )
    ).all()
    return [await public_gallery_data(db, gallery) for gallery in rows]


@router.get("/galleries/{slug}")
async def gallery(slug: str, db: DbSession) -> dict[str, Any]:
    item = await db.scalar(
        select(Gallery).where(Gallery.slug == slug, Gallery.status == "published")
    )
    if item is None:
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    return await public_gallery_data(db, item)


@router.get("/galleries/{slug}/media/{asset_id}/download")
async def download_gallery_media(
    slug: str, asset_id: UUID, db: DbSession
) -> StreamingResponse:
    gallery = await db.scalar(
        select(Gallery).where(Gallery.slug == slug, Gallery.status == "published")
    )
    if gallery is None:
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    row = (
        await db.execute(
            select(GalleryItem, MediaAsset)
            .join(MediaAsset, MediaAsset.id == GalleryItem.media_asset_id)
            .where(
                GalleryItem.gallery_id == gallery.id,
                GalleryItem.media_asset_id == asset_id,
                GalleryItem.allow_download.is_(True),
                MediaAsset.status == "ready",
                MediaAsset.is_private.is_(False),
            )
        )
    ).first()
    if row is None:
        raise ApiError(
            403,
            "gallery_download_forbidden",
            "Downloading this image is not allowed",
        )
    _item, asset = row
    try:
        stored = await run_in_threadpool(
            lambda: s3_client().get_object(
                Bucket=get_settings().media_bucket,
                Key=asset.storage_key,
            )
        )
    except Exception as exc:
        raise ApiError(404, "media_not_found", "Media asset not found") from exc
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=asset.content_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{safe_filename(asset.original_filename)}"'
            ),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/documents")
async def public_documents(db: DbSession) -> list[dict[str, Any]]:
    latest_versions = (
        select(
            DocumentFile.document_id,
            func.max(DocumentFile.version_number).label("version_number"),
        )
        .group_by(DocumentFile.document_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Document, DocumentFile, MediaAsset)
            .join(latest_versions, latest_versions.c.document_id == Document.id)
            .join(
                DocumentFile,
                (DocumentFile.document_id == Document.id)
                & (DocumentFile.version_number == latest_versions.c.version_number),
            )
            .join(MediaAsset, MediaAsset.id == DocumentFile.media_asset_id)
            .where(
                Document.category == "external",
                Document.status == "published",
                MediaAsset.status == "ready",
                MediaAsset.is_private.is_(False),
            )
            .order_by(Document.document_date.desc(), Document.created_at.desc())
        )
    ).all()
    documents: dict[UUID, dict[str, Any]] = {}
    for document, _version, asset in rows:
        file_data = {
            "media_asset_id": asset.id,
            "filename": asset.original_filename,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "download_url": f"/api/v1/public/media/{asset.id}",
        }
        entry = documents.setdefault(
            document.id,
            {
                "id": document.id,
                "public_id": document.public_id,
                "title": document.title,
                "sender": document.sender,
                "receiver": document.receiver,
                "description_html": document.description_html,
                "document_date": document.document_date,
                "filename": asset.original_filename,
                "content_type": asset.content_type,
                "byte_size": asset.byte_size,
                "download_url": f"/api/v1/public/media/{asset.id}",
                "files": [],
            },
        )
        entry["files"].append(file_data)
    return list(documents.values())


@router.get("/settings")
async def public_settings(db: DbSession) -> dict[str, Any]:
    rows = (
        await db.scalars(
            select(SiteSetting).where(SiteSetting.is_public.is_(True)).order_by(SiteSetting.key)
        )
    ).all()
    return {item.key: public_setting_value(item) for item in rows}


@router.get("/media/{asset_id}")
async def public_media(asset_id: UUID, db: DbSession) -> StreamingResponse:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.status != "ready" or asset.is_private:
        raise ApiError(404, "media_not_found", "Media asset not found")
    try:
        stored = await run_in_threadpool(
            lambda: s3_client().get_object(
                Bucket=get_settings().media_bucket,
                Key=asset.storage_key,
            )
        )
    except Exception as exc:
        raise ApiError(404, "media_not_found", "Media asset not found") from exc
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=asset.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename(asset.original_filename)}"',
            "Cache-Control": "public, max-age=300, stale-while-revalidate=3600",
        },
    )


@router.get("/ads/{slot_key}", response_model=list[AdCampaignView])
async def live_ads(slot_key: str, db: DbSession) -> list[AdCampaignView]:
    now = datetime.now(UTC)
    rows = (
        await db.scalars(
            select(AdCampaign)
            .join(AdSlot, AdSlot.id == AdCampaign.slot_id)
            .where(
                AdSlot.key == slot_key,
                AdSlot.is_active.is_(True),
                AdCampaign.status == "active",
                or_(AdCampaign.starts_at.is_(None), AdCampaign.starts_at <= now),
                or_(AdCampaign.ends_at.is_(None), AdCampaign.ends_at >= now),
            )
            .order_by(AdCampaign.priority.desc(), AdCampaign.created_at.desc())
        )
    ).all()
    return [AdCampaignView.model_validate(row) for row in rows]


@router.get("/search", response_model=list[SearchResult])
async def search_public(
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchResult]:
    pattern = f"%{q.strip()}%"
    article_rows = (
        await db.scalars(
            select(Article)
            .where(
                Article.status == "published",
                or_(Article.title.ilike(pattern), Article.excerpt.ilike(pattern)),
            )
            .limit(limit)
        )
    ).all()
    event_rows = (
        await db.scalars(
            select(Event)
            .where(
                Event.publication_status == "published",
                or_(Event.title.ilike(pattern), Event.short_description.ilike(pattern)),
            )
            .limit(limit)
        )
    ).all()
    document_rows = (
        await db.scalars(
            select(Document)
            .where(
                Document.category == "external",
                Document.status == "published",
                Document.title.ilike(pattern),
            )
            .limit(limit)
        )
    ).all()
    results = [
        SearchResult(
            id=item.id,
            kind="article",
            title=item.title,
            excerpt=item.excerpt,
            url=f"/news/{item.slug}",
            published_at=item.published_at,
        )
        for item in article_rows
    ]
    results.extend(
        SearchResult(
            id=item.id,
            kind="event",
            title=item.title,
            excerpt=item.short_description,
            url=f"/events/{item.slug}",
            published_at=item.start_date,
        )
        for item in event_rows
    )
    results.extend(
        SearchResult(
            id=item.id,
            kind="document",
            title=item.title,
            excerpt=item.description_html,
            url=f"/resources#{item.id}",
            published_at=item.document_date,
        )
        for item in document_rows
    )
    return results[:limit]


@router.post("/contact", response_model=MessageResponse)
async def contact(
    payload: ContactRequest,
    request: Request,
    db: DbSession,
) -> MessageResponse:
    # Honeypot submissions receive the same response but are not persisted.
    if payload.website:
        return MessageResponse(message="Thank you. Your message has been received")
    client_ip = request.client.host if request.client else "unknown"
    await enforce_rate_limit("contact", client_ip, limit=5, period_seconds=3600)
    job = BackgroundJob(
        id=new_id(),
        kind="contact_message",
        status="queued",
        input_json={
            "name": payload.name,
            "email": str(payload.email),
            "subject": payload.subject,
            "message": payload.message,
        },
    )
    db.add(job)
    record_change(
        db,
        context=event_context(request),
        action="contact.received",
        resource_type="background_job",
        resource_id=job.id,
        topic="admin:communications",
        payload={"job_id": str(job.id), "subject": payload.subject},
    )
    await db.commit()
    from utag_api.worker.tasks import deliver_contact_message

    deliver_contact_message.delay(str(job.id))
    return MessageResponse(message="Thank you. Your message has been received")
