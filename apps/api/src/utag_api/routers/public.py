from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from starlette.concurrency import run_in_threadpool

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.dependencies import DbSession, client_ip, event_context
from utag_api.errors import ApiError
from utag_api.models import (
    AdCampaign,
    AdSlot,
    Article,
    ArticleAttachment,
    BackgroundJob,
    Document,
    DocumentFile,
    Event,
    EventAttachment,
    EventRegistration,
    ExecutiveAppointment,
    FeatureFlag,
    Gallery,
    GalleryItem,
    MediaAsset,
    MediaVariant,
    OrganizationUnit,
    SiteSetting,
    User,
)
from utag_api.rate_limit import enforce_rate_limit
from utag_api.routers.content import article_views
from utag_api.routers.events import event_attachment_map, serialize_event
from utag_api.schemas.common import DeliveryCapabilities, MessageResponse, Page
from utag_api.schemas.domain import (
    AdCampaignView,
    ArticleView,
    ContactRequest,
    EventView,
    PublicExecutiveView,
    SearchResult,
)
from utag_api.services.audiences import includes_general_public
from utag_api.services.content import sanitize_html
from utag_api.services.delivery import public_capabilities, require_email_delivery
from utag_api.services.events import enqueue_task, record_change
from utag_api.services.executives import (
    executive_row_order_key,
    is_executive_officer_position,
)
from utag_api.services.features import feature_enabled
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
            email=user.email if appointment.show_email else None,
            phone_number=user.phone_number if appointment.show_phone else None,
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


async def public_document_media_is_referenced(db: DbSession, asset_id: UUID) -> bool:
    latest_versions = (
        select(
            DocumentFile.document_id,
            func.max(DocumentFile.version_number).label("version_number"),
        )
        .group_by(DocumentFile.document_id)
        .subquery()
    )
    document_audiences = (
        await db.scalars(
            select(Document.audiences)
            .join(DocumentFile, DocumentFile.document_id == Document.id)
            .join(
                latest_versions,
                (latest_versions.c.document_id == DocumentFile.document_id)
                & (latest_versions.c.version_number == DocumentFile.version_number),
            )
            .where(
                DocumentFile.media_asset_id == asset_id,
                Document.category == "external",
                Document.status == "published",
            )
        )
    ).all()
    return any(includes_general_public(audiences) for audiences in document_audiences)


async def public_media_is_referenced(db: DbSession, asset_id: UUID, now: datetime) -> bool:
    published_article = (
        Article.status == "published",
        Article.published_at <= now,
    )
    published_event = (
        Event.publication_status == "published",
        Event.published_at <= now,
    )
    statements = (
        select(Article.id).where(
            Article.featured_media_id == asset_id,
            *published_article,
        ),
        select(ArticleAttachment.id)
        .join(Article, Article.id == ArticleAttachment.article_id)
        .where(ArticleAttachment.media_asset_id == asset_id, *published_article),
        select(Event.id).where(
            Event.featured_media_id == asset_id,
            *published_event,
        ),
        select(EventAttachment.id)
        .join(Event, Event.id == EventAttachment.event_id)
        .where(EventAttachment.media_asset_id == asset_id, *published_event),
        select(ExecutiveAppointment.id)
        .join(User, User.id == ExecutiveAppointment.user_id)
        .where(
            User.profile_media_id == asset_id,
            User.status == "active",
            ExecutiveAppointment.is_active.is_(True),
            ExecutiveAppointment.is_public.is_(True),
        ),
        select(AdCampaign.id).where(
            AdCampaign.media_asset_id == asset_id,
            AdCampaign.status == "active",
            or_(AdCampaign.starts_at.is_(None), AdCampaign.starts_at <= now),
            or_(AdCampaign.ends_at.is_(None), AdCampaign.ends_at >= now),
        ),
    )
    for statement in statements:
        if await db.scalar(statement.limit(1)) is not None:
            return True

    if await feature_enabled(db, "public-gallery"):
        gallery_reference = await db.scalar(
            select(GalleryItem.id)
            .join(Gallery, Gallery.id == GalleryItem.gallery_id)
            .where(
                GalleryItem.media_asset_id == asset_id,
                Gallery.status == "published",
            )
            .limit(1)
        )
        if gallery_reference is not None:
            return True

    if await feature_enabled(db, "public-resources") and await public_document_media_is_referenced(
        db, asset_id
    ):
        return True

    carousel = await db.scalar(
        select(SiteSetting).where(
            SiteSetting.key == "site.carousel",
            SiteSetting.is_public.is_(True),
        )
    )
    if carousel is None:
        return False
    slides = public_setting_value(carousel).get("slides", [])
    return any(
        isinstance(slide, dict) and str(slide.get("media_asset_id")) == str(asset_id)
        for slide in slides
    )


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
                        User.status == "active",
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
        .where(
            ExecutiveAppointment.is_public.is_(True),
            User.status == "active",
        )
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
            "url": f"/api/v1/public/media/{asset.id}?v=w960",
            "thumb_url": f"/api/v1/public/media/{asset.id}?v=w480",
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
    if not await feature_enabled(db, "public-gallery"):
        return []
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
    if not await feature_enabled(db, "public-gallery"):
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    item = await db.scalar(
        select(Gallery).where(Gallery.slug == slug, Gallery.status == "published")
    )
    if item is None:
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    return await public_gallery_data(db, item)


@router.get("/galleries/{slug}/media/{asset_id}/download")
async def download_gallery_media(slug: str, asset_id: UUID, db: DbSession) -> StreamingResponse:
    if not await feature_enabled(db, "public-gallery"):
        raise ApiError(404, "gallery_not_found", "Gallery not found")
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


async def public_document_views(
    db: DbSession, document_id: UUID | None = None
) -> list[dict[str, Any]]:
    if not await feature_enabled(db, "public-resources"):
        return []
    latest_versions = (
        select(
            DocumentFile.document_id,
            func.max(DocumentFile.version_number).label("version_number"),
        )
        .group_by(DocumentFile.document_id)
        .subquery()
    )
    statement = (
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
        )
    )
    if document_id is not None:
        statement = statement.where(Document.id == document_id)
    rows = (
        await db.execute(
            statement.order_by(
                Document.document_date.desc(),
                Document.created_at.desc(),
                DocumentFile.position,
            )
        )
    ).all()
    documents: dict[UUID, dict[str, Any]] = {}
    for document, _version, asset in rows:
        if not includes_general_public(document.audiences):
            continue
        file_data = {
            "media_asset_id": asset.id,
            "filename": asset.original_filename,
            "content_type": asset.content_type,
            "byte_size": asset.byte_size,
            "content_url": f"/api/v1/public/media/{asset.id}",
            "download_url": f"/api/v1/public/media/{asset.id}",
        }
        entry = documents.setdefault(
            document.id,
            {
                "id": document.id,
                "title": document.title,
                "sender": document.sender,
                "receiver": document.receiver,
                "description_html": document.description_html,
                "document_date": document.document_date,
                "filename": asset.original_filename,
                "content_type": asset.content_type,
                "byte_size": asset.byte_size,
                "content_url": f"/api/v1/public/media/{asset.id}",
                "download_url": f"/api/v1/public/media/{asset.id}",
                "files": [],
            },
        )
        entry["files"].append(file_data)
    return list(documents.values())


@router.get("/documents")
async def public_documents(db: DbSession) -> list[dict[str, Any]]:
    return await public_document_views(db)


@router.get("/documents/{document_id}")
async def public_document(document_id: UUID, db: DbSession) -> dict[str, Any]:
    documents = await public_document_views(db, document_id)
    if not documents:
        raise ApiError(404, "document_not_found", "Document not found")
    return documents[0]


@router.get("/settings")
async def public_settings(db: DbSession) -> dict[str, Any]:
    rows = (
        await db.scalars(
            select(SiteSetting).where(SiteSetting.is_public.is_(True)).order_by(SiteSetting.key)
        )
    ).all()
    return {item.key: public_setting_value(item) for item in rows}


@router.get("/features")
async def public_features(db: DbSession) -> dict[str, bool]:
    keys = ("association-pulse", "public-resources", "public-gallery")
    values = {
        row.key: row.enabled
        for row in (await db.scalars(select(FeatureFlag).where(FeatureFlag.key.in_(keys)))).all()
    }
    return {key: bool(values.get(key, True)) for key in keys}


@router.get("/capabilities", response_model=DeliveryCapabilities)
async def capabilities() -> DeliveryCapabilities:
    return DeliveryCapabilities(**public_capabilities())


@router.get("/media/{asset_id}")
async def public_media(
    asset_id: UUID,
    db: DbSession,
    v: Annotated[str | None, Query(pattern="^(w480|w960|w1600|original)$")] = None,
) -> StreamingResponse:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.status != "ready":
        raise ApiError(404, "media_not_found", "Media asset not found")
    document_reference = await feature_enabled(
        db, "public-resources"
    ) and await public_document_media_is_referenced(db, asset_id)
    is_referenced = document_reference or (
        not asset.is_private and await public_media_is_referenced(db, asset_id, datetime.now(UTC))
    )
    if not is_referenced:
        raise ApiError(404, "media_not_found", "Media asset not found")

    storage_key = asset.storage_key
    content_type = asset.content_type
    filename = asset.original_filename
    cache_control = "public, max-age=86400, stale-while-revalidate=604800"
    if v and v != "original" and asset.content_type.startswith("image/"):
        variant = await db.scalar(
            select(MediaVariant).where(
                MediaVariant.asset_id == asset.id,
                MediaVariant.variant == v,
            )
        )
        if variant is not None:
            storage_key = variant.storage_key
            content_type = variant.content_type
            filename = f"{Path(asset.original_filename).stem}-{v}.webp"
            cache_control = "public, max-age=604800, immutable"

    try:
        stored = await run_in_threadpool(
            lambda: s3_client().get_object(
                Bucket=get_settings().media_bucket,
                Key=storage_key,
            )
        )
    except Exception as exc:
        raise ApiError(404, "media_not_found", "Media asset not found") from exc
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename(filename)}"',
            "Cache-Control": cache_control,
        },
    )


@router.get("/ads/{slot_key}", response_model=list[AdCampaignView])
async def live_ads(slot_key: str, db: DbSession) -> list[AdCampaignView]:
    now = datetime.now(UTC)
    slot = await db.scalar(select(AdSlot).where(AdSlot.key == slot_key, AdSlot.is_active.is_(True)))
    if slot is None:
        return []
    rows = (
        await db.scalars(
            select(AdCampaign)
            .where(
                AdCampaign.slot_id == slot.id,
                AdCampaign.status == "active",
                or_(AdCampaign.starts_at.is_(None), AdCampaign.starts_at <= now),
                or_(AdCampaign.ends_at.is_(None), AdCampaign.ends_at >= now),
            )
            .order_by(AdCampaign.priority.desc(), AdCampaign.created_at.desc())
        )
    ).all()
    return [
        AdCampaignView.model_validate(
            {
                **{key: value for key, value in vars(row).items() if not key.startswith("_")},
                "placement_name": slot.name,
                "slot_key": slot.key,
                "width": slot.width,
                "height": slot.height,
            }
        )
        for row in rows
    ]


@router.get("/search", response_model=list[SearchResult])
async def search_public(
    db: DbSession,
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SearchResult]:
    now = datetime.now(UTC)
    pattern = f"%{q.strip()}%"
    article_rows = (
        await db.scalars(
            select(Article)
            .where(
                Article.status == "published",
                Article.published_at <= now,
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
                Event.published_at <= now,
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
    document_rows = [item for item in document_rows if includes_general_public(item.audiences)]
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
    require_email_delivery()
    request_ip = client_ip(request)
    await enforce_rate_limit("contact", request_ip, limit=5, period_seconds=3600)
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
    enqueue_task(
        db,
        task_name="utag.contact.deliver",
        aggregate_type="background_job",
        aggregate_id=job.id,
        args=[str(job.id)],
        queue="communications",
    )
    await db.commit()
    return MessageResponse(message="Thank you. Your message has been received")
