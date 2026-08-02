from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import or_, select

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import AuditEvent, BackgroundJob, FeatureFlag, MediaAsset, SiteSetting, User
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    CarouselSlideCreate,
    CarouselSlideUpdate,
    CarouselSlideView,
    FeatureFlagUpdate,
    SiteSettingUpdate,
)
from utag_api.services.content import sanitize_html
from utag_api.services.events import record_change
from utag_api.services.query import paginate

router = APIRouter(prefix="/admin", tags=["administration"])


def carousel_rows(setting: SiteSetting | None) -> list[dict[str, Any]]:
    if setting is None:
        return []
    slides = setting.value.get("slides", [])
    if not isinstance(slides, list):
        return []
    # Copy nested JSON rows so SQLAlchemy can detect each replacement reliably.
    return [dict(slide) for slide in slides if isinstance(slide, dict)]


async def validate_carousel_media(db: DbSession, asset_id: UUID) -> MediaAsset:
    asset = await db.get(MediaAsset, asset_id)
    if (
        asset is None
        or asset.status != "ready"
        or asset.is_private
        or not asset.content_type.startswith("image/")
    ):
        raise ApiError(
            422,
            "carousel_media_invalid",
            "Choose a ready public image from the media library",
        )
    return asset


@router.get("/carousel", response_model=list[CarouselSlideView])
async def carousel(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("settings.manage"))],
) -> list[CarouselSlideView]:
    setting = await db.scalar(select(SiteSetting).where(SiteSetting.key == "site.carousel"))
    rows = sorted(carousel_rows(setting), key=lambda row: int(row.get("order", 0)))
    slides = [CarouselSlideView.model_validate(row) for row in rows]
    asset_ids = {slide.media_asset_id for slide in slides}
    media_names = {
        item.id: item.original_filename
        for item in (await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(asset_ids)))).all()
    }
    return [
        slide.model_copy(update={"media_name": media_names.get(slide.media_asset_id)})
        for slide in slides
    ]


@router.post("/carousel", response_model=CarouselSlideView, status_code=201)
async def create_carousel_slide(
    payload: CarouselSlideCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("settings.manage"))],
) -> CarouselSlideView:
    asset = await validate_carousel_media(db, payload.media_asset_id)
    setting = await db.scalar(
        select(SiteSetting).where(SiteSetting.key == "site.carousel").with_for_update()
    )
    if setting is None:
        setting = SiteSetting(
            id=new_id(), key="site.carousel", value={"slides": []}, is_public=True
        )
        db.add(setting)
        await db.flush()
    rows = carousel_rows(setting)
    data = payload.model_dump(mode="json")
    data["description"] = sanitize_html(payload.description)
    slide = CarouselSlideView(id=new_id(), **data)
    rows.append(slide.model_dump(mode="json", exclude={"media_name"}))
    setting.value = {**setting.value, "slides": rows}
    setting.is_public = True
    record_change(
        db,
        context=event_context(request, principal),
        action="carousel.slide.created",
        resource_type="carousel_slide",
        resource_id=slide.id,
        topic="settings",
        payload={"slide_id": str(slide.id), "is_published": slide.is_published},
    )
    await db.commit()
    return slide.model_copy(update={"media_name": asset.original_filename})


@router.patch("/carousel/{slide_id}", response_model=CarouselSlideView)
async def update_carousel_slide(
    slide_id: UUID,
    payload: CarouselSlideUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("settings.manage"))],
) -> CarouselSlideView:
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if changes.get("media_asset_id"):
        await validate_carousel_media(db, UUID(changes["media_asset_id"]))
    if changes.get("description") is not None:
        changes["description"] = sanitize_html(changes["description"])
    setting = await db.scalar(
        select(SiteSetting).where(SiteSetting.key == "site.carousel").with_for_update()
    )
    rows = carousel_rows(setting)
    for index, row in enumerate(rows):
        if str(row.get("id")) != str(slide_id):
            continue
        updated = CarouselSlideView.model_validate({**row, **changes})
        rows[index] = updated.model_dump(mode="json", exclude={"media_name"})
        assert setting is not None
        setting.value = {**setting.value, "slides": rows}
        record_change(
            db,
            context=event_context(request, principal),
            action="carousel.slide.updated",
            resource_type="carousel_slide",
            resource_id=updated.id,
            topic="settings",
            payload={"slide_id": str(updated.id), "is_published": updated.is_published},
            changes={key: {"to": str(value)} for key, value in changes.items()},
        )
        await db.commit()
        asset = await db.get(MediaAsset, updated.media_asset_id)
        return updated.model_copy(update={"media_name": asset.original_filename if asset else None})
    raise ApiError(404, "carousel_slide_not_found", "Carousel slide not found")


@router.delete("/carousel/{slide_id}", response_model=MessageResponse)
async def archive_carousel_slide(
    slide_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("settings.manage"))],
) -> MessageResponse:
    setting = await db.scalar(
        select(SiteSetting).where(SiteSetting.key == "site.carousel").with_for_update()
    )
    rows = carousel_rows(setting)
    for row in rows:
        if str(row.get("id")) != str(slide_id):
            continue
        row["archived"] = True
        row["is_published"] = False
        assert setting is not None
        setting.value = {**setting.value, "slides": rows}
        record_change(
            db,
            context=event_context(request, principal),
            action="carousel.slide.archived",
            resource_type="carousel_slide",
            resource_id=slide_id,
            topic="settings",
            payload={"slide_id": str(slide_id)},
        )
        await db.commit()
        return MessageResponse(message="Carousel slide archived")
    raise ApiError(404, "carousel_slide_not_found", "Carousel slide not found")


@router.get("/settings")
async def settings(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("settings.manage"))],
) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(SiteSetting).order_by(SiteSetting.key))).all()
    return [
        {"key": row.key, "value": row.value, "is_public": row.is_public, "id": row.id}
        for row in rows
    ]


@router.put("/settings/{key}")
async def update_setting(
    key: str,
    payload: SiteSettingUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("settings.manage"))],
) -> dict[str, Any]:
    item = await db.scalar(select(SiteSetting).where(SiteSetting.key == key))
    if item is None:
        item = SiteSetting(id=new_id(), key=key, value=payload.value, is_public=payload.is_public)
        db.add(item)
    else:
        item.value = payload.value
        item.is_public = payload.is_public
    record_change(
        db,
        context=event_context(request, principal),
        action="setting.updated",
        resource_type="site_setting",
        resource_id=item.id,
        topic="settings",
        payload={"key": key, "is_public": item.is_public},
    )
    await db.commit()
    return {"key": item.key, "value": item.value, "is_public": item.is_public}


@router.get("/feature-flags")
async def feature_flags(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("settings.manage"))],
) -> list[dict[str, Any]]:
    rows = (await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))).all()
    return [
        {
            "id": row.id,
            "key": row.key,
            "description": row.description,
            "enabled": row.enabled,
            "rules": row.rules,
        }
        for row in rows
    ]


@router.put("/feature-flags/{key}")
async def update_feature_flag(
    key: str,
    payload: FeatureFlagUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("settings.manage"))],
) -> dict[str, Any]:
    item = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    if item is None:
        item = FeatureFlag(id=new_id(), key=key)
        db.add(item)
    item.description = payload.description
    item.enabled = payload.enabled
    item.rules = payload.rules
    record_change(
        db,
        context=event_context(request, principal),
        action="feature_flag.updated",
        resource_type="feature_flag",
        resource_id=item.id,
        topic="settings",
        payload={"key": key, "enabled": item.enabled},
    )
    await db.commit()
    return {"key": item.key, "enabled": item.enabled, "rules": item.rules}


@router.get("/audit", response_model=Page[dict[str, Any]])
async def audit_log(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("audit.view"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    action: str | None = None,
    q: str | None = None,
) -> Page[dict[str, Any]]:
    statement = select(AuditEvent).order_by(AuditEvent.created_at.desc())
    if action:
        statement = statement.where(AuditEvent.action == action)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                AuditEvent.action.ilike(pattern),
                AuditEvent.resource_type.ilike(pattern),
                AuditEvent.request_id.ilike(pattern),
                AuditEvent.reason.ilike(pattern),
            )
        )
    result = await paginate(db, statement, page=page, page_size=page_size)
    actor_ids = {row.actor_id for row in result.items if row.actor_id}
    users = {
        user.id: user.full_name
        for user in (await db.scalars(select(User).where(User.id.in_(actor_ids)))).all()
    }
    return Page[dict[str, Any]](
        items=[
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "actor_name": users.get(row.actor_id, "System"),
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "outcome": row.outcome,
                "request_id": row.request_id,
                "reason": row.reason,
                "changes": row.changes,
                "metadata": row.metadata_json,
                "created_at": row.created_at,
            }
            for row in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )


@router.get("/jobs", response_model=Page[dict[str, Any]])
async def jobs(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("jobs.manage"))],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    status: str | None = None,
    q: str | None = None,
) -> Page[dict[str, Any]]:
    statement = select(BackgroundJob)
    if status:
        statement = statement.where(BackgroundJob.status == status)
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                BackgroundJob.kind.ilike(pattern),
                BackgroundJob.error_message.ilike(pattern),
            )
        )
    result = await paginate(
        db,
        statement.order_by(BackgroundJob.created_at.desc()),
        page=page,
        page_size=page_size,
    )
    return Page[dict[str, Any]](
        items=[
            {key: value for key, value in row.__dict__.items() if not key.startswith("_")}
            for row in result.items
        ],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
        pages=result.pages,
    )
