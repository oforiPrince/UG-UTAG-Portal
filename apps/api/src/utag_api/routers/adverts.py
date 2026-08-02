from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    client_ip,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import (
    AdAdvertiser,
    AdCampaign,
    AdOrder,
    AdPlan,
    AdSlot,
    MediaAsset,
    MediaVariant,
    User,
)
from utag_api.rate_limit import enforce_rate_limit
from utag_api.schemas.common import MessageResponse
from utag_api.schemas.domain import (
    AdAdvertiserCreate,
    AdAdvertiserUpdate,
    AdAdvertiserView,
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
from utag_api.services.adverts import (
    apply_order_side_effects,
    create_fulfilment_campaign,
    default_order_end,
    ensure_campaign_available_for_order,
    ensure_campaign_can_go_live,
    ensure_order_can_be_active,
    order_authorizes_live_campaign,
)
from utag_api.services.events import record_change

router = APIRouter(prefix="/adverts", tags=["advertising"])

# Allow modest creative resizing while still catching wrong-placement assets.
_CREATIVE_DIM_TOLERANCE = 0.08


def model_values(item: object) -> dict[str, object]:
    return {key: value for key, value in vars(item).items() if not key.startswith("_")}


def slot_view(item: AdSlot) -> AdSlotView:
    return AdSlotView.model_validate(
        {
            **model_values(item),
            "size": f"{item.width}×{item.height}",
        }
    )


def fulfilment_label(*, is_house_ad: bool, order: AdOrder | None) -> str:
    if is_house_ad:
        return "House ad"
    if order is None:
        return "Needs order"
    if order_authorizes_live_campaign(order):
        return "Paid · ready"
    if order.payment_status != "paid":
        return f"Order · {order.payment_status}"
    return f"Order · {order.status}"


async def campaign_views(db: DbSession, campaigns: list[AdCampaign]) -> list[AdCampaignView]:
    slot_ids = {item.slot_id for item in campaigns}
    media_ids = {item.media_asset_id for item in campaigns if item.media_asset_id is not None}
    campaign_ids = {item.id for item in campaigns}
    slots = {
        item.id: item
        for item in (await db.scalars(select(AdSlot).where(AdSlot.id.in_(slot_ids)))).all()
    }
    media = {
        item.id: item.original_filename
        for item in (await db.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids)))).all()
    }
    orders = list(
        (
            await db.scalars(select(AdOrder).where(AdOrder.campaign_id.in_(campaign_ids)))
        ).all()
    )
    order_by_campaign = {item.campaign_id: item for item in orders if item.campaign_id}
    advertiser_ids = {item.advertiser_id for item in orders}
    advertisers = {
        item.id: item.organization_name
        for item in (
            await db.scalars(select(AdAdvertiser).where(AdAdvertiser.id.in_(advertiser_ids)))
        ).all()
    }
    return [
        AdCampaignView.model_validate(
            {
                **model_values(item),
                "placement_name": (slots[item.slot_id].name if item.slot_id in slots else None),
                "media_name": (media.get(item.media_asset_id) if item.media_asset_id else None),
                "slot_key": (slots[item.slot_id].key if item.slot_id in slots else None),
                "width": (slots[item.slot_id].width if item.slot_id in slots else None),
                "height": (slots[item.slot_id].height if item.slot_id in slots else None),
                "order_id": (
                    order_by_campaign[item.id].id if item.id in order_by_campaign else None
                ),
                "order_status": (
                    order_by_campaign[item.id].status if item.id in order_by_campaign else None
                ),
                "payment_status": (
                    order_by_campaign[item.id].payment_status
                    if item.id in order_by_campaign
                    else None
                ),
                "advertiser_name": (
                    advertisers.get(order_by_campaign[item.id].advertiser_id)
                    if item.id in order_by_campaign
                    else None
                ),
                "fulfilment": fulfilment_label(
                    is_house_ad=item.is_house_ad,
                    order=order_by_campaign.get(item.id),
                ),
            }
        )
        for item in campaigns
    ]


async def plan_views(db: DbSession, plans: list[AdPlan]) -> list[AdPlanView]:
    slot_ids = {item.slot_id for item in plans}
    slots = {
        item.id: item
        for item in (await db.scalars(select(AdSlot).where(AdSlot.id.in_(slot_ids)))).all()
    }
    return [
        AdPlanView.model_validate(
            {
                **model_values(item),
                "placement_name": (slots[item.slot_id].name if item.slot_id in slots else None),
                "width": (slots[item.slot_id].width if item.slot_id in slots else None),
                "height": (slots[item.slot_id].height if item.slot_id in slots else None),
            }
        )
        for item in plans
    ]


async def order_views(db: DbSession, orders: list[AdOrder]) -> list[AdOrderView]:
    advertiser_ids = {item.advertiser_id for item in orders}
    plan_ids = {item.plan_id for item in orders}
    campaign_ids = {item.campaign_id for item in orders if item.campaign_id is not None}
    advertisers = {
        item.id: item.organization_name
        for item in (
            await db.scalars(select(AdAdvertiser).where(AdAdvertiser.id.in_(advertiser_ids)))
        ).all()
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
                "advertiser_name": advertisers.get(item.advertiser_id),
                "plan_name": plans.get(item.plan_id),
                "campaign_name": (campaigns.get(item.campaign_id) if item.campaign_id else None),
            }
        )
        for item in orders
    ]


async def advertiser_views(
    db: DbSession, advertisers: list[AdAdvertiser]
) -> list[AdAdvertiserView]:
    member_ids = {
        item.member_user_id for item in advertisers if item.member_user_id is not None
    }
    members = {
        item.id: item.full_name
        for item in (await db.scalars(select(User).where(User.id.in_(member_ids)))).all()
    }
    return [
        AdAdvertiserView.model_validate(
            {
                **model_values(item),
                "website": str(item.website) if item.website else None,
                "member_name": (
                    members.get(item.member_user_id) if item.member_user_id else None
                ),
            }
        )
        for item in advertisers
    ]


async def require_active_advertiser(db: DbSession, advertiser_id: UUID) -> AdAdvertiser:
    advertiser = await db.get(AdAdvertiser, advertiser_id)
    if advertiser is None:
        raise ApiError(422, "advertiser_not_found", "Advertiser not found")
    if not advertiser.is_active:
        raise ApiError(
            422,
            "advertiser_inactive",
            "Choose an active advertiser client before creating an order",
        )
    return advertiser


async def require_active_slot(db: DbSession, slot_id: UUID) -> AdSlot:
    slot = await db.get(AdSlot, slot_id)
    if slot is None:
        raise ApiError(422, "ad_slot_invalid", "Advertising placement not found")
    if not slot.is_active:
        raise ApiError(
            422,
            "ad_slot_inactive",
            "Choose an active advertising placement that is mounted on the public site",
        )
    return slot


def dimensions_match(expected_w: int, expected_h: int, actual_w: int, actual_h: int) -> bool:
    return (
        abs(actual_w - expected_w) / expected_w <= _CREATIVE_DIM_TOLERANCE
        and abs(actual_h - expected_h) / expected_h <= _CREATIVE_DIM_TOLERANCE
    )


async def validate_campaign_media(
    db: DbSession,
    *,
    slot: AdSlot,
    media_asset_id: UUID | None,
) -> MediaAsset | None:
    if media_asset_id is None:
        return None
    asset = await db.get(MediaAsset, media_asset_id)
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
    variants = list(
        (
            await db.scalars(
                select(MediaVariant).where(MediaVariant.asset_id == asset.id)
            )
        ).all()
    )
    sized = next(
        (
            item
            for item in variants
            if item.variant == "original" and item.width and item.height
        ),
        None,
    )
    if sized is None:
        # Prefer the largest processed variant so wide banners are not
        # rejected against a downscaled thumbnail (e.g. w480).
        sized = max(
            (item for item in variants if item.width and item.height),
            key=lambda item: int(item.width) * int(item.height),
            default=None,
        )
    if sized is not None and sized.width and sized.height:
        if not dimensions_match(slot.width, slot.height, sized.width, sized.height):
            raise ApiError(
                422,
                "campaign_media_dimensions",
                (
                    f"Creative dimensions {sized.width}×{sized.height} do not match "
                    f"placement {slot.width}×{slot.height}"
                ),
            )
    return asset


@router.get("/slots", response_model=list[AdSlotView])
async def slots(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdSlotView]:
    return [
        slot_view(item)
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
        raise ApiError(409, "ad_slot_exists", "This advertising placement already exists")
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
    return slot_view(item)


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
        raise ApiError(404, "ad_slot_not_found", "Advertising placement not found")
    duplicate = await db.scalar(
        select(AdSlot.id).where(AdSlot.key == payload.key, AdSlot.id != item.id)
    )
    if duplicate:
        raise ApiError(409, "ad_slot_exists", "This advertising placement already exists")
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
    return slot_view(item)


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
    slot = await require_active_slot(db, payload.slot_id)
    asset = await validate_campaign_media(db, slot=slot, media_asset_id=payload.media_asset_id)
    if payload.ends_at and payload.starts_at and payload.ends_at <= payload.starts_at:
        raise ApiError(422, "campaign_dates_invalid", "End time must be after start time")
    data = payload.model_dump()
    data["target_url"] = str(payload.target_url) if payload.target_url else None
    item = AdCampaign(id=new_id(), created_by_id=principal.user.id, **data)
    await ensure_campaign_can_go_live(db, campaign=item, intended_status=item.status)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.campaign.created",
        resource_type="ad_campaign",
        resource_id=item.id,
        topic="adverts",
        payload={
            "campaign_id": str(item.id),
            "status": item.status,
            "is_house_ad": item.is_house_ad,
        },
    )
    await db.commit()
    return (await campaign_views(db, [item]))[0]


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
    if "slot_id" in changes:
        slot = await require_active_slot(db, changes["slot_id"])
    else:
        slot = await db.get(AdSlot, item.slot_id)
        if slot is None:
            raise ApiError(422, "ad_slot_invalid", "Advertising placement not found")
    media_asset_id = changes.get("media_asset_id", item.media_asset_id)
    if "media_asset_id" in changes or "slot_id" in changes:
        await validate_campaign_media(db, slot=slot, media_asset_id=media_asset_id)
    starts_at = changes.get("starts_at", item.starts_at)
    ends_at = changes.get("ends_at", item.ends_at)
    if ends_at and starts_at and ends_at <= starts_at:
        raise ApiError(422, "campaign_dates_invalid", "End time must be after start time")
    if "target_url" in changes:
        changes["target_url"] = str(changes["target_url"]) if changes["target_url"] else None
    for key, value in changes.items():
        setattr(item, key, value)
    if item.is_house_ad:
        linked_order = await db.scalar(select(AdOrder).where(AdOrder.campaign_id == item.id))
        if linked_order is not None:
            raise ApiError(
                422,
                "campaign_house_has_order",
                "Unlink the advertiser order before marking this campaign as a house ad",
            )
    await ensure_campaign_can_go_live(db, campaign=item, intended_status=item.status)
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
    order = await db.scalar(select(AdOrder).where(AdOrder.campaign_id == item.id))
    if order is not None and order.status in {"approved", "active"}:
        order.status = "completed"
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
    rows = list((await db.scalars(select(AdPlan).order_by(AdPlan.name))).all())
    return await plan_views(db, rows)


@router.post("/plans", response_model=AdPlanView, status_code=201)
async def create_plan(
    payload: AdPlanCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdPlanView:
    slot = await require_active_slot(db, payload.slot_id)
    item = AdPlan(id=new_id(), **payload.model_dump())
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.plan.created",
        resource_type="ad_plan",
        resource_id=item.id,
        topic="adverts",
        payload={"plan_id": str(item.id), "slot_id": str(item.slot_id)},
    )
    await db.commit()
    return AdPlanView.model_validate(
        {
            **model_values(item),
            "placement_name": slot.name,
            "width": slot.width,
            "height": slot.height,
        }
    )


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
    if "slot_id" in changes:
        await require_active_slot(db, changes["slot_id"])
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
    return (await plan_views(db, [item]))[0]


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


@router.get("/advertisers", response_model=list[AdAdvertiserView])
async def advertisers(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("adverts.manage"))],
) -> list[AdAdvertiserView]:
    rows = list(
        (
            await db.scalars(
                select(AdAdvertiser).order_by(
                    AdAdvertiser.organization_name.asc(), AdAdvertiser.created_at.desc()
                )
            )
        ).all()
    )
    return await advertiser_views(db, rows)


@router.post("/advertisers", response_model=AdAdvertiserView, status_code=201)
async def create_advertiser(
    payload: AdAdvertiserCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdAdvertiserView:
    data = payload.model_dump()
    if data.get("website") is not None:
        data["website"] = str(data["website"])
    if data.get("member_user_id") is not None:
        member = await db.get(User, data["member_user_id"])
        if member is None:
            raise ApiError(422, "member_not_found", "Linked member account not found")
    item = AdAdvertiser(id=new_id(), **data)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.advertiser.created",
        resource_type="ad_advertiser",
        resource_id=item.id,
        topic="adverts",
        payload={"advertiser_id": str(item.id), "organization_name": item.organization_name},
    )
    await db.commit()
    return (await advertiser_views(db, [item]))[0]


@router.patch("/advertisers/{advertiser_id}", response_model=AdAdvertiserView)
async def update_advertiser(
    advertiser_id: UUID,
    payload: AdAdvertiserUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdAdvertiserView:
    item = await db.get(AdAdvertiser, advertiser_id)
    if item is None:
        raise ApiError(404, "advertiser_not_found", "Advertiser not found")
    changes = payload.model_dump(exclude_unset=True)
    if "website" in changes and changes["website"] is not None:
        changes["website"] = str(changes["website"])
    if "member_user_id" in changes and changes["member_user_id"] is not None:
        member = await db.get(User, changes["member_user_id"])
        if member is None:
            raise ApiError(422, "member_not_found", "Linked member account not found")
    for key, value in changes.items():
        setattr(item, key, value)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.advertiser.updated",
        resource_type="ad_advertiser",
        resource_id=item.id,
        topic="adverts",
        payload={"advertiser_id": str(item.id)},
        changes={key: {"to": str(value)} for key, value in changes.items()},
    )
    await db.commit()
    return (await advertiser_views(db, [item]))[0]


@router.delete("/advertisers/{advertiser_id}", response_model=MessageResponse)
async def deactivate_advertiser(
    advertiser_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> MessageResponse:
    item = await db.get(AdAdvertiser, advertiser_id)
    if item is None:
        raise ApiError(404, "advertiser_not_found", "Advertiser not found")
    item.is_active = False
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.advertiser.deactivated",
        resource_type="ad_advertiser",
        resource_id=item.id,
        topic="adverts",
        payload={"advertiser_id": str(item.id)},
    )
    await db.commit()
    return MessageResponse(message="Advertiser deactivated")


async def ensure_order_campaign_matches_plan(
    db: DbSession,
    *,
    plan: AdPlan,
    campaign_id: UUID | None,
    order_id: UUID | None = None,
) -> AdCampaign | None:
    if campaign_id is None:
        return None
    return await ensure_campaign_available_for_order(
        db, plan=plan, campaign_id=campaign_id, order_id=order_id
    )


@router.post("/orders", response_model=AdOrderView, status_code=201)
async def create_order(
    payload: AdOrderCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("adverts.manage"))],
) -> AdOrderView:
    advertiser = await require_active_advertiser(db, payload.advertiser_id)
    plan = await db.get(AdPlan, payload.plan_id)
    if plan is None:
        raise ApiError(422, "ad_plan_not_found", "Advertising plan not found")
    data = payload.model_dump()
    if data["starts_on"] and not data["ends_on"]:
        data["ends_on"] = default_order_end(data["starts_on"], plan.duration_days)
    campaign = await ensure_order_campaign_matches_plan(
        db, plan=plan, campaign_id=payload.campaign_id
    )
    if campaign is None:
        campaign = await create_fulfilment_campaign(
            db,
            plan=plan,
            advertiser=advertiser,
            created_by_id=principal.user.id,
            starts_on=data["starts_on"],
            ends_on=data["ends_on"],
        )
        data["campaign_id"] = campaign.id
    if data["status"] == "active":
        ensure_order_can_be_active(
            campaign_id=data["campaign_id"],
            payment_status=data["payment_status"],
        )
    item = AdOrder(id=new_id(), **data)
    apply_order_side_effects(campaign, item)
    db.add(item)
    record_change(
        db,
        context=event_context(request, principal),
        action="advert.order.created",
        resource_type="ad_order",
        resource_id=item.id,
        topic="adverts",
        payload={
            "order_id": str(item.id),
            "status": item.status,
            "advertiser_id": str(item.advertiser_id),
            "campaign_id": str(item.campaign_id) if item.campaign_id else None,
        },
    )
    await db.commit()
    return AdOrderView.model_validate(
        {
            **model_values(item),
            "advertiser_name": advertiser.organization_name,
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
    if "advertiser_id" in changes:
        await require_active_advertiser(db, changes["advertiser_id"])
    plan = await db.get(AdPlan, item.plan_id)
    if plan is None:
        raise ApiError(422, "ad_plan_not_found", "Advertising plan not found")
    campaign_id = changes.get("campaign_id", item.campaign_id)
    if "campaign_id" in changes:
        campaign = await ensure_order_campaign_matches_plan(
            db, plan=plan, campaign_id=changes["campaign_id"], order_id=item.id
        )
    else:
        campaign = await db.get(AdCampaign, item.campaign_id) if item.campaign_id else None
    starts_on = changes.get("starts_on", item.starts_on)
    ends_on = changes.get("ends_on", item.ends_on)
    if starts_on and ends_on and ends_on < starts_on:
        raise ApiError(422, "order_dates_invalid", "Order end date cannot be before its start")
    next_status = changes.get("status", item.status)
    next_payment = changes.get("payment_status", item.payment_status)
    if next_status == "active":
        ensure_order_can_be_active(campaign_id=campaign_id, payment_status=next_payment)
    for key, value in changes.items():
        setattr(item, key, value)
    if campaign is None and item.campaign_id:
        campaign = await db.get(AdCampaign, item.campaign_id)
    apply_order_side_effects(campaign, item)
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
    campaign = await db.get(AdCampaign, item.campaign_id) if item.campaign_id else None
    apply_order_side_effects(campaign, item)
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
    ip_address = client_ip(request)
    await enforce_rate_limit(
        f"ad-impression:{campaign_id}", ip_address, limit=50, period_seconds=3600
    )
    now = datetime.now(UTC)
    result = await db.execute(
        update(AdCampaign)
        .where(
            AdCampaign.id == campaign_id,
            AdCampaign.status == "active",
            (AdCampaign.starts_at.is_(None) | (AdCampaign.starts_at <= now)),
            (AdCampaign.ends_at.is_(None) | (AdCampaign.ends_at >= now)),
        )
        .values(impressions=AdCampaign.impressions + 1)
    )
    if not result.rowcount:  # type: ignore[attr-defined]
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    await db.commit()
    return MessageResponse(message="Impression recorded")


@router.post("/track/{campaign_id}/click")
async def track_click(campaign_id: UUID, request: Request, db: DbSession) -> dict[str, str]:
    ip_address = client_ip(request)
    await enforce_rate_limit(f"ad-click:{campaign_id}", ip_address, limit=20, period_seconds=3600)
    item = await db.get(AdCampaign, campaign_id)
    now = datetime.now(UTC)
    if (
        item is None
        or item.status != "active"
        or not item.target_url
        or (item.starts_at is not None and item.starts_at > now)
        or (item.ends_at is not None and item.ends_at < now)
    ):
        raise ApiError(404, "campaign_not_found", "Campaign not found")
    await db.execute(
        update(AdCampaign).where(AdCampaign.id == item.id).values(clicks=AdCampaign.clicks + 1)
    )
    await db.commit()
    return {"url": item.target_url}
