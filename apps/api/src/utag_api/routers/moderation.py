import re
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import Field
from sqlalchemy import select

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
    Document,
    DocumentFile,
    Event,
    EventAttachment,
    Gallery,
    GalleryItem,
)
from utag_api.schemas.common import ApiModel
from utag_api.services.events import record_change

router = APIRouter(prefix="/moderation", tags=["content moderation"])

ContentKind = Literal["news", "announcement", "event", "document", "gallery"]
ModeratedModel = Article | Announcement | Event | Document | Gallery
ModerationStatus = Literal[
    "draft",
    "review",
    "scheduled",
    "published",
    "archived",
    "withdrawn",
]


class ModerationItem(ApiModel):
    id: UUID
    kind: ContentKind
    title: str
    summary: str
    status: str
    updated_at: datetime
    version: int | None = None
    public_url: str | None = None
    workspace_url: str


class ModerationDecision(ApiModel):
    decision: Literal["approve", "changes_requested", "withdraw"]
    note: str = Field(default="", max_length=2_000)
    expected_version: int | None = Field(default=None, ge=1)


class ModerationPreview(ApiModel):
    id: UUID
    kind: ContentKind
    title: str
    summary: str
    body_html: str
    status: str
    media_asset_ids: list[UUID] = Field(default_factory=list)
    details: dict[str, str] = Field(default_factory=dict)


def _status(item: ModeratedModel) -> str:
    if isinstance(item, Event):
        return item.publication_status
    return item.status


def _set_status(item: ModeratedModel, value: str) -> None:
    if isinstance(item, Event):
        item.publication_status = value
    else:
        item.status = value


def _summary(item: ModeratedModel) -> str:
    if isinstance(item, Article):
        value = item.excerpt
    elif isinstance(item, Announcement):
        value = item.content_html
    elif isinstance(item, Event):
        value = item.short_description
    elif isinstance(item, Document):
        value = item.description_html
    else:
        value = item.description
    return " ".join(re.sub(r"<[^>]+>", " ", value).split())[:320]


def _public_url(item: ModeratedModel) -> str | None:
    if isinstance(item, Article):
        return f"/news/{item.slug}"
    if isinstance(item, Event):
        return f"/events/{item.slug}"
    if isinstance(item, Gallery):
        return f"/gallery/{item.slug}"
    if isinstance(item, Document):
        return f"/resources#{item.id}"
    return None


def _kind(item: ModeratedModel) -> ContentKind:
    if isinstance(item, Article):
        return "news"
    if isinstance(item, Announcement):
        return "announcement"
    if isinstance(item, Event):
        return "event"
    if isinstance(item, Document):
        return "document"
    return "gallery"


def _workspace_url(kind: ContentKind) -> str:
    return {
        "news": "/dashboard/news",
        "announcement": "/dashboard/announcements",
        "event": "/dashboard/events",
        "document": "/dashboard/documents",
        "gallery": "/dashboard/galleries",
    }[kind]


def moderation_item(item: ModeratedModel) -> ModerationItem:
    kind = _kind(item)
    return ModerationItem(
        id=item.id,
        kind=kind,
        title=item.title,
        summary=_summary(item),
        status=_status(item),
        updated_at=item.updated_at,
        version=item.version,
        public_url=_public_url(item),
        workspace_url=_workspace_url(kind),
    )


async def _all_items(db: DbSession) -> list[ModerationItem]:
    articles = (
        await db.scalars(select(Article).order_by(Article.updated_at.desc()).limit(200))
    ).all()
    announcements = (
        await db.scalars(select(Announcement).order_by(Announcement.updated_at.desc()).limit(200))
    ).all()
    events = (await db.scalars(select(Event).order_by(Event.updated_at.desc()).limit(200))).all()
    documents = (
        await db.scalars(
            select(Document)
            .where(Document.category == "external")
            .order_by(Document.updated_at.desc())
            .limit(200)
        )
    ).all()
    galleries = (
        await db.scalars(select(Gallery).order_by(Gallery.updated_at.desc()).limit(200))
    ).all()
    items = [
        moderation_item(item)
        for rows in (articles, announcements, events, documents, galleries)
        for item in rows
    ]
    return sorted(items, key=lambda item: item.updated_at, reverse=True)


@router.get("", response_model=list[ModerationItem])
async def moderation_queue(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
    status: ModerationStatus | None = None,
    kind: Annotated[
        ContentKind | None,
        Query(),
    ] = None,
) -> list[ModerationItem]:
    del principal
    items = await _all_items(db)
    return [
        item
        for item in items
        if (status is None or item.status == status) and (kind is None or item.kind == kind)
    ]


async def _load_item(db: DbSession, kind: ContentKind, item_id: UUID) -> ModeratedModel:
    if kind == "news":
        article = await db.get(Article, item_id)
        if article is not None:
            return article
    elif kind == "announcement":
        announcement = await db.get(Announcement, item_id)
        if announcement is not None:
            return announcement
    elif kind == "event":
        event = await db.get(Event, item_id)
        if event is not None:
            return event
    elif kind == "document":
        document = await db.get(Document, item_id)
        if document is not None:
            return document
    else:
        gallery = await db.get(Gallery, item_id)
        if gallery is not None:
            return gallery
    raise ApiError(404, "moderation_item_not_found", "Content item not found")


@router.get("/{kind}/{item_id}/preview", response_model=ModerationPreview)
async def preview(
    kind: ContentKind,
    item_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
) -> ModerationPreview:
    del principal
    item = await _load_item(db, kind, item_id)
    media_asset_ids: list[UUID] = []
    details: dict[str, str] = {}
    body_html = ""

    if isinstance(item, Article):
        body_html = item.content_html
        if item.featured_media_id:
            media_asset_ids.append(item.featured_media_id)
        media_asset_ids.extend(
            (
                await db.scalars(
                    select(ArticleAttachment.media_asset_id).where(
                        ArticleAttachment.article_id == item_id
                    )
                )
            ).all()
        )
        details["Tags"] = ", ".join(item.tags) or "Association news"
    elif isinstance(item, Announcement):
        body_html = item.content_html
        details["Priority"] = item.priority
    elif isinstance(item, Event):
        body_html = item.description_html
        if item.featured_media_id:
            media_asset_ids.append(item.featured_media_id)
        media_asset_ids.extend(
            (
                await db.scalars(
                    select(EventAttachment.media_asset_id).where(
                        EventAttachment.event_id == item_id
                    )
                )
            ).all()
        )
        details["Date"] = str(item.start_date)
        details["Venue"] = item.venue or "Online"
        details["Type"] = item.event_type
        if item.photos_url:
            details["Photos"] = item.photos_url
    elif isinstance(item, Document):
        body_html = item.description_html
        latest_version = await db.scalar(
            select(DocumentFile.version_number)
            .where(DocumentFile.document_id == item_id)
            .order_by(DocumentFile.version_number.desc())
            .limit(1)
        )
        if latest_version is not None:
            media_asset_ids.extend(
                (
                    await db.scalars(
                        select(DocumentFile.media_asset_id)
                        .where(
                            DocumentFile.document_id == item_id,
                            DocumentFile.version_number == latest_version,
                        )
                        .order_by(DocumentFile.position)
                    )
                ).all()
            )
        details["Category"] = item.category
        details["Document date"] = str(item.document_date or "Not provided")
    else:
        gallery_items = (
            await db.scalars(
                select(GalleryItem)
                .where(GalleryItem.gallery_id == item_id)
                .order_by(GalleryItem.position)
            )
        ).all()
        media_asset_ids.extend(row.media_asset_id for row in gallery_items)
        details["Images"] = str(len(gallery_items))
        if item.external_album_url:
            details["External album"] = item.external_album_url

    return ModerationPreview(
        id=item_id,
        kind=kind,
        title=item.title,
        summary=_summary(item),
        body_html=body_html,
        status=_status(item),
        media_asset_ids=media_asset_ids,
        details=details,
    )


@router.post("/{kind}/{item_id}", response_model=ModerationItem)
async def decide(
    kind: ContentKind,
    item_id: UUID,
    payload: ModerationDecision,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.publish"))],
) -> ModerationItem:
    item = await _load_item(db, kind, item_id)
    current_version = item.version
    if (
        payload.expected_version is not None
        and current_version is not None
        and payload.expected_version != current_version
    ):
        raise ApiError(
            412,
            "version_conflict",
            "This content changed after the moderation queue loaded. Refresh and review it again",
            details={"current_version": current_version},
        )

    previous_status = _status(item)
    if payload.decision == "approve":
        if previous_status != "review":
            raise ApiError(
                409,
                "moderation_transition_invalid",
                "Only content awaiting review can be approved",
            )
        next_status = "published"
    elif payload.decision == "changes_requested":
        if previous_status != "review":
            raise ApiError(
                409,
                "moderation_transition_invalid",
                "Only content awaiting review can be returned for changes",
            )
        if not payload.note.strip():
            raise ApiError(422, "moderation_note_required", "Explain the changes being requested")
        next_status = "draft"
    else:
        if previous_status != "published":
            raise ApiError(
                409,
                "moderation_transition_invalid",
                "Only published content can be withdrawn",
            )
        if not payload.note.strip():
            raise ApiError(
                422,
                "moderation_note_required",
                "Explain why this item is being withdrawn",
            )
        next_status = "withdrawn" if kind == "news" else "archived"

    _set_status(item, next_status)
    if (
        next_status == "published"
        and not isinstance(item, Document)
        and (item.published_at is None or item.published_at > datetime.now(UTC))
    ):
        item.published_at = datetime.now(UTC)
    item.version += 1

    record_change(
        db,
        context=event_context(request, principal),
        action=f"{kind}.moderation.{payload.decision}",
        resource_type=kind,
        resource_id=item_id,
        topic="moderation",
        payload={
            "kind": kind,
            "item_id": str(item_id),
            "status": next_status,
        },
        changes={"status": {"from": previous_status, "to": next_status}},
        reason=payload.note.strip() or None,
    )
    await db.commit()
    return moderation_item(item)
