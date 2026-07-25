from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import AdCampaign, AdOrder, AdPlan, AdSlot, MediaAsset, User
from utag_api.rate_limit import enforce_rate_limit
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import (
    AdCampaignCreate,
    AdCampaignUpdate,
    AdCampaignView,
    AdOrderCreate,
    AdOrderUpdate,
    AdOrderView,
    AdPlanCreate,
    AdPlanUpdate,
    AdPlanView,
    AdSlotCreate,
    AdSlotView,
)
from utag_api.services.events import record_change

router = APIRouter(prefix="/adverts", tags=["advertising"])


def model_values(item: object) -> dict[str, object]:
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


async def campaign_views(db: DbSession, campaigns: list[AdCampaign]) -> list[AdCampaignView]:
    slot_ids = {item.slot_id for item in campaigns}
    media_ids = {item.media_asset_id for item in campaigns if item.media_asset_id is not None}
    slots = {
        item.id: item.name
        for item in (await db.scalars(select(AdSlot).where(AdSlot.id.in_(slot_ids)))).all()
    }
    media = {
        item.id: item.original_filename
        for item in (await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids)))).all()
    }
    return [
        AdCampaignView.model_validate(
            {
                **model_values(item),
                "placement_name": slots.get(item.slot_id),
                "media_name": (media.get(item.media_asset_id) if item.media_asset_id else None),
            }
        )
        for item in campaigns
    ]


async def order_views(db: DbSession, orders: list[AdOrder]) -> list[AdOrderView]:
    user_ids = {item.user_id for item in orders}
    plan_ids = {item.plan_id for item in orders}
    campaign_ids = {item.campaign_id for item in orders if item.campaign_id is not None}
    users = {
        item.id: item.full_name
        for item in (await db.scalars(select(User).where(User.id.in_(user_ids)))).all()
    }
    plans = {
        item.id: item.name
        for item in (await db.scalars(select(AdPlan).where(AdPlan.id.in_(plan_ids)))).all()
    }
    campaigns = {
        item.id: item.title
        for item in (
            await db.scalars(select(AdCampaign).where(AdCampaign.id.in_(campaign_ids)))
        ).all()
    }
    return [
        AdOrderView.model_validate(
            {
                **model_values(item),
                "advertiser_name": users.get(item.user_id),
                "plan_name": plans.get(item.plan_id),
                "campaign_name": (campaigns.get(item.campaign_id) if item.campaign_id else None),
            }
        )
        for item in orders
    ]


@router.get("/slots", response_model=list[AdSlotView])
async def slots(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdSlotView]:
    return [
        AdSlotView.model_validate(item)
        for item in (await db.scalars(select(AdSlot).order_by(AdSlot.key))).all()
    ]


@router.post("/slots", response_model=AdSlotView, status_code=201)
async def create_slot(
    payload: AdSlotCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdSlotView:
    if await db.scalar(select(AdSlot.id).where(AdSlot.key == payload.key)):
        raise ApiError(409, "ad_slot_exists", "This advertising slot already exists")
    item = AdSlot(id=new_id(), **payload.model_dump())
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.slot.created",
        resource_type="ad_slot",
        resource_id=item.id,
        topic="adverts",
        payload={"slot_id": str(item.id), "key": item.key},
    )
    await db.commit()
    return AdSlotView.model_validate(item)


@router.put("/slots/{slot_id}", response_model=AdSlotView)
async def update_slot(
    slot_id: UUID,
    payload: AdSlotCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdSlotView:
    item = await db.get(AdSlot, slot_id)
    if item is None:
        raise ApiError(404, "ad_slot_not_found", "Advertising slot not found")
    duplicate = await db.scalar(
        select(AdSlot.id).where(AdSlot.key == payload.key, AdSlot.id != item.id)
    )
    if duplicate:
        raise ApiError(409, "ad_slot_exists", "This advertising slot already exists")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.slot.updated",
        resource_type="ad_slot",
        resource_id=item.id,
        topic="adverts",
        payload={"slot_id": str(item.id), "is_active": item.is_active},
    )
    await db.commit()
    return AdSlotView.model_validate(item)


@router.get("/campaigns", response_model=list[AdCampaignView])
async def campaigns(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdCampaignView]:
    rows = list((await db.scalars(select(AdCampaign).order_by(AdCampaign.created_at.desc()))).all())
    return await campaign_views(db, rows)


@router.post("/campaigns", response_model=AdCampaignView, status_code=201)
async def create_campaign(
    payload: AdCampaignCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdCampaignView:
    slot = await db.get(AdSlot, payload.slot_id)
    if slot is None:
        raise ApiError(422, "ad_slot_invalid", "Advertising slot not found")
    asset: MediaAsset | None = None
    if payload.media_asset_id:
        asset = await db.get(MediaAsset, payload.media_asset_id)
        if (
            asset is None
            or asset.status != "ready"
            or asset.is_private
            or not asset.content_type.startswith("image/")
        ):
            raise ApiError(
                422,
                "campaign_media_invalid",
                "Choose a ready public image for the campaign",
            )
    if payload.ends_at and payload.starts_at and payload.ends_at <= payload.starts_at:
        raise ApiError(422, "campaign_dates_invalid", "End time must be after start time")
    data = payload.model_dump()
    data["target_url"] = str(payload.target_url) if payload.target_url else None
    item = AdCampaign(id=new_id(), created_by_id=principal.user.id, **data)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.campaign.created",
        resource_type="ad_campaign",
        resource_id=item.id,
        topic="adverts",
        payload={"campaign_id": str(item.id), "status": item.status},
    )
    await db.commit()
    return AdCampaignView.model_validate(
        {
            **model_values(item),
            "placement_name": slot.name,
            "media_name": asset.original_filename if asset else None,
        }
    )


@router.patch("/campaigns/{campaign_id}", response_model=AdCampaignView)
async def update_campaign(
    campaign_id: UUID,
    payload: AdCampaignUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdCampaignView:
    item = await db.get(AdCampaign, campaign_id)
    if item is None:
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    changes = payload.model_dump(exclude_unset=True)
    if "slot_id" in changes and await db.get(AdSlot, changes["slot_id"]) is None:
        raise ApiError(422, "ad_slot_invalid", "Advertising slot not found")
    if changes.get("media_asset_id"):
        asset = await db.get(MediaAsset, changes["media_asset_id"])
        if (
            asset is None
            or asset.status != "ready"
            or asset.is_private
            or not asset.content_type.startswith("image/")
        ):
            raise ApiError(
                422,
                "campaign_media_invalid",
                "Choose a ready public image for the campaign",
            )
    starts_at = changes.get("starts_at", item.starts_at)
    ends_at = changes.get("ends_at", item.ends_at)
    if ends_at and starts_at and ends_at <= starts_at:
        raise ApiError(422, "campaign_dates_invalid", "End time must be after start time")
    if "target_url" in changes:
        changes["target_url"] = str(changes["target_url"]) if changes["target_url"] else None
    for key, value in changes.items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.campaign.updated",
        resource_type="ad_campaign",
        resource_id=item.id,
        topic="adverts",
        payload={"campaign_id": str(item.id), "status": item.status},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return (await campaign_views(db, [item]))[0]


@router.delete("/campaigns/{campaign_id}", response_model=MessageResponse)
async def complete_campaign(
    campaign_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> MessageResponse:
    item = await db.get(AdCampaign, campaign_id)
    if item is None:
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    item.status = "completed"
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.campaign.completed",
        resource_type="ad_campaign",
        resource_id=item.id,
        topic="adverts",
        payload={"campaign_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Campaign completed")


@router.get("/plans", response_model=list[AdPlanView])
async def plans(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdPlanView]:
    rows = (await db.scalars(select(AdPlan).order_by(AdPlan.name))).all()
    return [AdPlanView.model_validate(item) for item in rows]


@router.post("/plans", response_model=AdPlanView, status_code=201)
async def create_plan(
    payload: AdPlanCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdPlanView:
    item = AdPlan(id=new_id(), **payload.model_dump())
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.plan.created",
        resource_type="ad_plan",
        resource_id=item.id,
        topic="adverts",
        payload={"plan_id": str(item.id)},
    )
    await db.commit()
    return AdPlanView.model_validate(item)


@router.patch("/plans/{plan_id}", response_model=AdPlanView)
async def update_plan(
    plan_id: UUID,
    payload: AdPlanUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdPlanView:
    item = await db.get(AdPlan, plan_id)
    if item is None:
        raise ApiError(404, "ad_plan_not_found", "Advertising plan not found")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.plan.updated",
        resource_type="ad_plan",
        resource_id=item.id,
        topic="adverts",
        payload={"plan_id": str(item.id), "is_active": item.is_active},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return AdPlanView.model_validate(item)


@router.delete("/plans/{plan_id}", response_model=MessageResponse)
async def deactivate_plan(
    plan_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> MessageResponse:
    item = await db.get(AdPlan, plan_id)
    if item is None:
        raise ApiError(404, "ad_plan_not_found", "Advertising plan not found")
    item.is_active = False
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.plan.deactivated",
        resource_type="ad_plan",
        resource_id=item.id,
        topic="adverts",
        payload={"plan_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Advertising plan deactivated")


@router.get("/orders", response_model=list[AdOrderView])
async def orders(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdOrderView]:
    rows = list((await db.scalars(select(AdOrder).order_by(AdOrder.created_at.desc()))).all())
    return await order_views(db, rows)


@router.post("/orders", response_model=AdOrderView, status_code=201)
async def create_order(
    payload: AdOrderCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdOrderView:
    user = await db.get(User, payload.user_id)
    plan = await db.get(AdPlan, payload.plan_id)
    if user is None:
        raise ApiError(422, "member_not_found", "Advertiser member not found")
    if plan is None:
        raise ApiError(422, "ad_plan_not_found", "Advertising plan not found")
    campaign = await db.get(AdCampaign, payload.campaign_id) if payload.campaign_id else None
    if payload.campaign_id and campaign is None:
        raise ApiError(422, "campaign_not_found", "Campaign not found")
    data = payload.model_dump()
    if data["starts_on"] and not data["ends_on"]:
        data["ends_on"] = data["starts_on"] + timedelta(days=plan.duration_days)
    item = AdOrder(id=new_id(), **data)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.order.created",
        resource_type="ad_order",
        resource_id=item.id,
        topic="adverts",
        payload={"order_id": str(item.id), "status": item.status},
    )
    await db.commit()
    return AdOrderView.model_validate(
        {
            **model_values(item),
            "advertiser_name": user.full_name,
            "plan_name": plan.name,
            "campaign_name": campaign.title if campaign else None,
        }
    )


@router.patch("/orders/{order_id}", response_model=AdOrderView)
async def update_order(
    order_id: UUID,
    payload: AdOrderUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdOrderView:
    item = await db.get(AdOrder, order_id)
    if item is None:
        raise ApiError(404, "ad_order_not_found", "Advertising order not found")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("campaign_id") and await db.get(AdCampaign, changes["campaign_id"]) is None:
        raise ApiError(422, "campaign_not_found", "Campaign not found")
    starts_on = changes.get("starts_on", item.starts_on)
    ends_on = changes.get("ends_on", item.ends_on)
    if starts_on and ends_on and ends_on < starts_on:
        raise ApiError(422, "order_dates_invalid", "Order end date cannot be before its start")
    for key, value in changes.items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.order.updated",
        resource_type="ad_order",
        resource_id=item.id,
        topic="adverts",
        payload={"order_id": str(item.id), "status": item.status},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return (await order_views(db, [item]))[0]


@router.delete("/orders/{order_id}", response_model=MessageResponse)
async def cancel_order(
    order_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> MessageResponse:
    item = await db.get(AdOrder, order_id)
    if item is None:
        raise ApiError(404, "ad_order_not_found", "Advertising order not found")
    item.status = "cancelled"
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.order.cancelled",
        resource_type="ad_order",
        resource_id=item.id,
        topic="adverts",
        payload={"order_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Advertising order cancelled")


@router.post("/track/{campaign_id}/impression", response_model=MessageResponse)
async def track_impression(campaign_id: UUID, request: Request, db: DbSession) -> MessageResponse:
    ip_address = request.client.host if request.client else "unknown"
    await enforce_rate_limit(
        f"ad-impression:{campaign_id}", ip_address, limit=50, period_seconds=3600
    )
    result = await db.execute(
        update(AdCampaign)
        .where(AdCampaign.id == campaign_id, AdCampaign.status == "active")
        .values(impressions=AdCampaign.impressions + 1)
    )
    if not result.rowcount:  # type: ignore[attr-defined]
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    await db.commit()
    return MessageResponse(message="Impression recorded")


@router.post("/track/{campaign_id}/click")
async def track_click(campaign_id: UUID, request: Request, db: DbSession) -> dict[str, str]:
    ip_address = request.client.host if request.client else "unknown"
    await enforce_rate_limit(f"ad-click:{campaign_id}", ip_address, limit=20, period_seconds=3600)
    item = await db.get(AdCampaign, campaign_id)
    if item is None or item.status != "active" or not item.target_url:
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    await db.execute(
        update(AdCampaign).where(AdCampaign.id == item.id).values(clicks=AdCampaign.clicks + 1)
    )
    await db.commit()
    return {"url": item.target_url}
