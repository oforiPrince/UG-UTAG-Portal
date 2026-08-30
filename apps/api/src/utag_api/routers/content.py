from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import delete, or_, select

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import (
    Announcement,
    Article,
    ArticleAttachment,
    MediaAsset,
    Notification,
    User,
)
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    AnnouncementCreate,
    AnnouncementView,
    ArticleCreate,
    ArticleUpdate,
    ArticleView,
)
from utag_api.services.content import sanitize_html
from utag_api.services.deletion import (
    DeleteBlocker,
    block_delete_if_referenced,
    commit_permanent_delete,
    count_rows,
)
from utag_api.services.events import record_change
from utag_api.services.moderation import ensure_publish_permission
from utag_api.services.notifications import deliver_announcement_notifications
from utag_api.services.query import paginate, unique_slug

router = APIRouter(prefix="/content", tags=["content"])


async def validate_featured_media(
    db: DbSession, featured_media_id: UUID | None
) -> MediaAsset | None:
    if featured_media_id is None:
        return None
    asset = await db.get(MediaAsset, featured_media_id)
    if (
        asset is None
        or asset.status != "ready"
        or asset.is_private
        or not asset.content_type.startswith("image/")
    ):
        raise ApiError(
            409,
            "featured_media_invalid",
            "Choose a public image that has completed security scanning",
        )
    return asset


async def validate_article_attachments(
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
            "attachment_media_invalid",
            "Choose public files that have completed security scanning",
        )
    by_id = {asset.id: asset for asset in assets}
    return [by_id[asset_id] for asset_id in unique_ids]


async def article_views(
    db: DbSession, articles: list[Article], *, public: bool = False
) -> list[ArticleView]:
    article_ids = [article.id for article in articles]
    author_ids = {article.author_id for article in articles if article.author_id is not None}
    media_ids = {
        article.featured_media_id for article in articles if article.featured_media_id is not None
    }
    authors = {
        item.id: item.full_name
        for item in (await db.scalars(select(User).where(User.id.in_(author_ids)))).all()
    }
    media = {
        item.id: item.original_filename
        for item in (await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids)))).all()
    }
    attachment_rows = (
        await db.execute(
            select(ArticleAttachment, MediaAsset)
            .join(MediaAsset, MediaAsset.id == ArticleAttachment.media_asset_id)
            .where(ArticleAttachment.article_id.in_(article_ids))
            .order_by(ArticleAttachment.article_id, ArticleAttachment.position)
        )
    ).all()
    attachments: dict[UUID, list[dict[str, object]]] = {}
    for attachment, asset in attachment_rows:
        attachments.setdefault(attachment.article_id, []).append(
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
    return [
        ArticleView.model_validate(
            {
                **{
                    key: value for key, value in article.__dict__.items() if not key.startswith("_")
                },
                "author_name": (authors.get(article.author_id) if article.author_id else None),
                "featured_media_name": (
                    media.get(article.featured_media_id) if article.featured_media_id else None
                ),
                "attachment_media_ids": [
                    item["media_asset_id"] for item in attachments.get(article.id, [])
                ],
                "attachments": attachments.get(article.id, []),
            }
        )
        for article in articles
    ]


@router.get("/articles", response_model=Page[ArticleView])
async def list_articles(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    status: str | None = None,
    q: str | None = None,
) -> Page[ArticleView]:
    statement = select(Article).order_by(Article.updated_at.desc())
    if status:
        statement = statement.where(Article.status == status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(Article.title.ilike(pattern), Article.excerpt.ilike(pattern))
        )
    result = await paginate(db, statement, page=page, page_size=page_size)
    return Page[ArticleView](
        items=await article_views(db, list(result.items)),
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/articles/{article_id}", response_model=ArticleView)
async def get_article(
    article_id: UUID,
    response: Response,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
) -> ArticleView:
    article = await db.get(Article, article_id)
    if article is None:
        raise ApiError(404, "article_not_found", "Article not found")
    response.headers["ETag"] = f'"{article.version}"'
    return (await article_views(db, [article]))[0]


@router.post("/articles", response_model=ArticleView, status_code=201)
async def create_article(
    payload: ArticleCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
) -> ArticleView:
    ensure_publish_permission(principal.permissions, payload.status)
    await validate_featured_media(db, payload.featured_media_id)
    attachment_assets = await validate_article_attachments(db, payload.attachment_media_ids)
    data = payload.model_dump(exclude={"slug", "attachment_media_ids"})
    data["content_html"] = sanitize_html(payload.content_html)
    if payload.status == "published" and not payload.published_at:
        data["published_at"] = datetime.now(UTC)
    article = Article(
        id=new_id(),
        slug=await unique_slug(db, Article, payload.title, payload.slug),
        author_id=principal.user.id,
        **data,
    )
    db.add(article)
    await db.flush()
    db.add_all(
        [
            ArticleAttachment(
                id=new_id(),
                article_id=article.id,
                media_asset_id=asset.id,
                position=position,
            )
            for position, asset in enumerate(attachment_assets)
        ]
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="article.created",
        resource_type="article",
        resource_id=article.id,
        topic="content",
        payload={"article_id": str(article.id), "status": article.status},
    )
    await db.commit()
    return (await article_views(db, [article]))[0]


@router.patch("/articles/{article_id}", response_model=ArticleView)
async def update_article(
    article_id: UUID,
    payload: ArticleUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> ArticleView:
    article = await db.get(Article, article_id)
    if article is None:
        raise ApiError(404, "article_not_found", "Article not found")
    if if_match != f'"{article.version}"':
        raise ApiError(
            412,
            "version_conflict",
            "This article changed after it was opened. Refresh before saving",
            details={"current_version": article.version},
        )
    ensure_publish_permission(principal.permissions, payload.status)
    changes = payload.model_dump(exclude_unset=True)
    if "featured_media_id" in changes:
        await validate_featured_media(db, changes["featured_media_id"])
    attachment_ids = changes.pop("attachment_media_ids", None)
    attachment_assets = (
        await validate_article_attachments(db, attachment_ids)
        if attachment_ids is not None
        else None
    )
    if "content_html" in changes:
        changes["content_html"] = sanitize_html(changes["content_html"])
    next_status = changes.get("status", article.status)
    next_published_at = changes.get("published_at", article.published_at)
    if next_status == "scheduled" and next_published_at is None:
        raise ApiError(
            422,
            "publication_time_required",
            "Scheduled articles require a publication time",
        )
    if changes.get("status") == "published" and not changes.get("published_at"):
        changes["published_at"] = datetime.now(UTC)
    for key, value in changes.items():
        setattr(article, key, value)
    if attachment_assets is not None:
        await db.execute(
            delete(ArticleAttachment).where(ArticleAttachment.article_id == article.id)
        )
        db.add_all(
            [
                ArticleAttachment(
                    id=new_id(),
                    article_id=article.id,
                    media_asset_id=asset.id,
                    position=position,
                )
                for position, asset in enumerate(attachment_assets)
            ]
        )
    article.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="article.updated",
        resource_type="article",
        resource_id=article.id,
        topic="content",
        payload={
            "article_id": str(article.id),
            "status": article.status,
            "version": article.version,
        },
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return (await article_views(db, [article]))[0]


@router.delete("/articles/{article_id}", response_model=MessageResponse)
async def archive_article(
    article_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.publish"))],
) -> MessageResponse:
    article = await db.get(Article, article_id)
    if article is None:
        raise ApiError(404, "article_not_found", "Article not found")
    article.status = "archived"
    article.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="article.archived",
        resource_type="article",
        resource_id=article.id,
        topic="content",
        payload={"article_id": str(article.id), "version": article.version},
    )
    await db.commit()
    return MessageResponse(message="Article archived")


@router.delete("/articles/{article_id}/permanent", response_model=MessageResponse)
async def delete_article_permanently(
    article_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[
        Principal,
        Depends(require_mutation_permissions("records.delete", "content.publish")),
    ],
) -> MessageResponse:
    article = await db.get(Article, article_id, with_for_update=True)
    if article is None:
        raise ApiError(404, "article_not_found", "Article not found")
    notification_count = await count_rows(
        db,
        Notification,
        Notification.resource_type == "article",
        Notification.resource_id == article.id,
    )
    block_delete_if_referenced(
        "article",
        [DeleteBlocker("member notification", notification_count)],
        guidance=(
            "Remove the related member notifications first, or archive the article to "
            "preserve communication history"
        ),
    )
    await db.execute(delete(ArticleAttachment).where(ArticleAttachment.article_id == article.id))
    record_change(
        db,
        context=event_context(request, principal),
        action="article.deleted",
        resource_type="article",
        resource_id=article.id,
        topic="content",
        payload={"article_id": str(article.id), "slug": article.slug},
    )
    await db.delete(article)
    await commit_permanent_delete(db, "article")
    return MessageResponse(message="Article deleted permanently")


@router.get("/announcements", response_model=Page[AnnouncementView])
async def list_announcements(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    status: str | None = None,
    priority: str | None = None,
    q: str | None = None,
) -> Page[AnnouncementView]:
    statement = select(Announcement)
    if status:
        statement = statement.where(Announcement.status == status)
    if priority:
        statement = statement.where(Announcement.priority == priority)
    if q and q.strip():
        statement = statement.where(Announcement.title.ilike(f"%{q.strip()}%"))
    result = await paginate(
        db,
        statement.order_by(Announcement.updated_at.desc()),
        page=page,
        page_size=page_size,
    )
    return Page[AnnouncementView](
        items=[AnnouncementView.model_validate(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.post("/announcements", response_model=AnnouncementView, status_code=201)
async def create_announcement(
    payload: AnnouncementCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
) -> AnnouncementView:
    ensure_publish_permission(principal.permissions, payload.status)
    data = payload.model_dump()
    data["content_html"] = sanitize_html(payload.content_html)
    if payload.status == "published" and not payload.published_at:
        data["published_at"] = datetime.now(UTC)
    item = Announcement(id=new_id(), created_by_id=principal.user.id, **data)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="announcement.created",
        resource_type="announcement",
        resource_id=item.id,
        topic="announcements",
        payload={"announcement_id": str(item.id), "priority": item.priority},
    )
    if item.status == "published":
        await deliver_announcement_notifications(
            db,
            item,
            context=event_context(request, principal),
        )
    await db.commit()
    return AnnouncementView.model_validate(item)


@router.patch("/announcements/{announcement_id}", response_model=AnnouncementView)
async def update_announcement(
    announcement_id: UUID,
    payload: AnnouncementCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> AnnouncementView:
    item = await db.get(Announcement, announcement_id)
    if item is None:
        raise ApiError(404, "announcement_not_found", "Announcement not found")
    if if_match != f'"{item.version}"':
        raise ApiError(412, "version_conflict", "Refresh this announcement before saving")
    ensure_publish_permission(principal.permissions, payload.status)
    previous_status = item.status
    data = payload.model_dump()
    data["content_html"] = sanitize_html(payload.content_html)
    if payload.status == "published" and not payload.published_at:
        data["published_at"] = datetime.now(UTC)
    for key, value in data.items():
        setattr(item, key, value)
    item.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="announcement.updated",
        resource_type="announcement",
        resource_id=item.id,
        topic="announcements",
        payload={"announcement_id": str(item.id), "version": item.version},
    )
    if previous_status != "published" and item.status == "published":
        await deliver_announcement_notifications(
            db,
            item,
            context=event_context(request, principal),
        )
    await db.commit()
    return AnnouncementView.model_validate(item)


@router.delete("/announcements/{announcement_id}", response_model=MessageResponse)
async def archive_announcement(
    announcement_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.publish"))],
) -> MessageResponse:
    item = await db.get(Announcement, announcement_id)
    if item is None:
        raise ApiError(404, "announcement_not_found", "Announcement not found")
    item.status = "archived"
    item.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="announcement.archived",
        resource_type="announcement",
        resource_id=item.id,
        topic="announcements",
        payload={"announcement_id": str(item.id), "version": item.version},
    )
    await db.commit()
    return MessageResponse(message="Announcement archived")


@router.delete(
    "/announcements/{announcement_id}/permanent",
    response_model=MessageResponse,
)
async def delete_announcement_permanently(
    announcement_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[
        Principal,
        Depends(require_mutation_permissions("records.delete", "content.publish")),
    ],
) -> MessageResponse:
    item = await db.get(Announcement, announcement_id, with_for_update=True)
    if item is None:
        raise ApiError(404, "announcement_not_found", "Announcement not found")
    notification_count = await count_rows(
        db,
        Notification,
        Notification.resource_type == "announcement",
        Notification.resource_id == item.id,
    )
    block_delete_if_referenced(
        "announcement",
        [DeleteBlocker("member delivery", notification_count, "member deliveries")],
        guidance=(
            "Delivered announcements must be archived so members' communication history "
            "remains valid"
        ),
    )
    record_change(
        db,
        context=event_context(request, principal),
        action="announcement.deleted",
        resource_type="announcement",
        resource_id=item.id,
        topic="announcements",
        payload={"announcement_id": str(item.id)},
    )
    await db.delete(item)
    await commit_permanent_delete(db, "announcement")
    return MessageResponse(message="Announcement deleted permanently")
