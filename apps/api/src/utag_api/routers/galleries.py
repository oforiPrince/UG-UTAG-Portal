from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import delete, select

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import Gallery, GalleryItem, MediaAsset
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import GalleryCreate
from utag_api.services.content import sanitize_html
from utag_api.services.events import record_change
from utag_api.services.moderation import ensure_publish_permission
from utag_api.services.query import unique_slug

router = APIRouter(prefix="/galleries", tags=["galleries"])


async def gallery_data(
    db: DbSession,
    gallery: Gallery,
    items: list[GalleryItem],
    media_names: dict[UUID, str] | None = None,
) -> dict[str, Any]:
    if media_names is None:
        asset_ids = {item.media_asset_id for item in items}
        media_names = {
            asset.id: asset.original_filename
            for asset in (
                await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
            ).all()
        }
    return {
        "id": gallery.id,
        "slug": gallery.slug,
        "title": gallery.title,
        "description": sanitize_html(gallery.description),
        "external_album_url": gallery.external_album_url,
        "status": gallery.status,
        "published_at": gallery.published_at,
        "created_at": gallery.created_at,
        "updated_at": gallery.updated_at,
        "version": gallery.version,
        "items": [
            {
                "id": item.id,
                "media_asset_id": item.media_asset_id,
                "media_name": media_names.get(item.media_asset_id),
                "position": item.position,
                "caption": item.caption,
                "allow_download": item.allow_download,
            }
            for item in items
        ],
    }


@router.get("")
async def list_galleries(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("content.view"))],
) -> list[dict[str, Any]]:
    galleries = (await db.scalars(select(Gallery).order_by(Gallery.created_at.desc()))).all()
    gallery_ids = {gallery.id for gallery in galleries}
    all_items = list(
        (
            await db.scalars(
                select(GalleryItem)
                .where(GalleryItem.gallery_id.in_(gallery_ids))
                .order_by(GalleryItem.position)
            )
        ).all()
    )
    asset_ids = {item.media_asset_id for item in all_items}
    media_names = {
        asset.id: asset.original_filename
        for asset in (
            await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))
        ).all()
    }
    items_by_gallery: dict[UUID, list[GalleryItem]] = {}
    for item in all_items:
        items_by_gallery.setdefault(item.gallery_id, []).append(item)
    return [
        await gallery_data(
            db,
            gallery,
            items_by_gallery.get(gallery.id, []),
            media_names,
        )
        for gallery in galleries
    ]


@router.post("", status_code=201)
async def create_gallery(
    payload: GalleryCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
) -> dict[str, Any]:
    ensure_publish_permission(principal.permissions, payload.status)
    unique_ids = list(dict.fromkeys(payload.media_asset_ids))
    assets = (
        await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(unique_ids)))
    ).all() if unique_ids else []
    if len(assets) != len(unique_ids) or any(
        asset.status != "ready" or asset.is_private or not asset.content_type.startswith("image/")
        for asset in assets
    ):
        raise ApiError(
            422,
            "gallery_media_invalid",
            "Choose only ready public images for the gallery",
        )
    gallery = Gallery(
        id=new_id(),
        slug=await unique_slug(db, Gallery, payload.title),
        title=payload.title,
        description=sanitize_html(payload.description),
        external_album_url=(
            str(payload.external_album_url) if payload.external_album_url else None
        ),
        status=payload.status,
        published_at=datetime.now(UTC) if payload.status == "published" else None,
    )
    db.add(gallery)
    await db.flush()
    blocked = set(payload.blocked_download_media_ids)
    items = [
        GalleryItem(
            id=new_id(),
            gallery_id=gallery.id,
            media_asset_id=asset_id,
            position=index,
            allow_download=asset_id not in blocked,
        )
        for index, asset_id in enumerate(unique_ids)
    ]
    db.add_all(items)
    record_change(
        db,
        context=event_context(request, principal),
        action="gallery.created",
        resource_type="gallery",
        resource_id=gallery.id,
        topic="galleries",
        payload={"gallery_id": str(gallery.id), "status": gallery.status},
    )
    await db.commit()
    return await gallery_data(db, gallery, items)


@router.put("/{gallery_id}")
async def update_gallery(
    gallery_id: UUID,
    payload: GalleryCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.edit"))],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> dict[str, Any]:
    gallery = await db.get(Gallery, gallery_id)
    if gallery is None:
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    if if_match != f'"{gallery.version}"':
        raise ApiError(412, "version_conflict", "Refresh this gallery before saving")
    ensure_publish_permission(principal.permissions, payload.status)
    unique_ids = list(dict.fromkeys(payload.media_asset_ids))
    assets = (
        await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(unique_ids)))
    ).all() if unique_ids else []
    if len(assets) != len(unique_ids) or any(
        asset.status != "ready" or asset.is_private or not asset.content_type.startswith("image/")
        for asset in assets
    ):
        raise ApiError(
            422,
            "gallery_media_invalid",
            "Choose only ready public images for the gallery",
        )
    gallery.title = payload.title
    gallery.description = sanitize_html(payload.description)
    gallery.external_album_url = (
        str(payload.external_album_url) if payload.external_album_url else None
    )
    if gallery.status != "published" and payload.status == "published":
        gallery.published_at = datetime.now(UTC)
    gallery.status = payload.status
    gallery.version += 1
    await db.execute(delete(GalleryItem).where(GalleryItem.gallery_id == gallery.id))
    blocked = set(payload.blocked_download_media_ids)
    items = [
        GalleryItem(
            id=new_id(),
            gallery_id=gallery.id,
            media_asset_id=asset_id,
            position=index,
            allow_download=asset_id not in blocked,
        )
        for index, asset_id in enumerate(unique_ids)
    ]
    db.add_all(items)
    record_change(
        db,
        context=event_context(request, principal),
        action="gallery.updated",
        resource_type="gallery",
        resource_id=gallery.id,
        topic="galleries",
        payload={"gallery_id": str(gallery.id), "status": gallery.status},
    )
    await db.commit()
    return await gallery_data(db, gallery, items)


@router.delete("/{gallery_id}", response_model=MessageResponse)
async def archive_gallery(
    gallery_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("content.publish"))],
) -> MessageResponse:
    gallery = await db.get(Gallery, gallery_id)
    if gallery is None:
        raise ApiError(404, "gallery_not_found", "Gallery not found")
    gallery.status = "archived"
    gallery.version += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="gallery.archived",
        resource_type="gallery",
        resource_id=gallery.id,
        topic="galleries",
        payload={"gallery_id": str(gallery.id)},
    )
    await db.commit()
    return MessageResponse(message="Gallery archived")
