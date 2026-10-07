from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.errors import ApiError
from utag_api.models import AdAdvertiser, AdCampaign, AdOrder, AdPlan

LIVE_CAMPAIGN_STATUSES = frozenset({"active", "scheduled"})
FULFILLING_ORDER_STATUSES = frozenset({"approved", "active"})
PAID_PAYMENT = "paid"


def order_window_to_campaign_datetimes(
    starts_on: date | None,
    ends_on: date | None,
) -> tuple[datetime | None, datetime | None]:
    starts_at = (
        datetime.combine(starts_on, time.min, tzinfo=UTC) if starts_on is not None else None
    )
    ends_at = (
        datetime.combine(ends_on, time(23, 59, 59), tzinfo=UTC) if ends_on is not None else None
    )
    return starts_at, ends_at


def sync_campaign_flight_from_order(campaign: AdCampaign, order: AdOrder) -> None:
    starts_at, ends_at = order_window_to_campaign_datetimes(order.starts_on, order.ends_on)
    if starts_at is not None:
        campaign.starts_at = starts_at
    if ends_at is not None:
        campaign.ends_at = ends_at


async def linked_order_for_campaign(
    db: AsyncSession, campaign_id: UUID
) -> AdOrder | None:
    order: AdOrder | None = await db.scalar(
        select(AdOrder).where(AdOrder.campaign_id == campaign_id)
    )
    return order


def order_authorizes_live_campaign(order: AdOrder) -> bool:
    return (
        order.payment_status == PAID_PAYMENT
        and order.status in FULFILLING_ORDER_STATUSES
    )


async def ensure_campaign_can_go_live(
    db: AsyncSession,
    *,
    campaign: AdCampaign,
    intended_status: str,
) -> AdOrder | None:
    if intended_status not in LIVE_CAMPAIGN_STATUSES:
        return await linked_order_for_campaign(db, campaign.id)

    if campaign.media_asset_id is None:
        raise ApiError(
            422,
            "campaign_creative_required",
            "Upload a creative before scheduling or activating a campaign",
        )

    if campaign.is_house_ad:
        return None

    order = await linked_order_for_campaign(db, campaign.id)
    if order is None:
        raise ApiError(
            422,
            "campaign_order_required",
            "Paid campaigns need a linked order before they can go live. "
            "Mark the campaign as a house ad only for UG UTAG's own promotions.",
        )
    if not order_authorizes_live_campaign(order):
        raise ApiError(
            422,
            "campaign_order_not_ready",
            "Linked order must be approved or active and marked paid before the "
            "campaign can go live",
        )
    return order


async def ensure_campaign_available_for_order(
    db: AsyncSession,
    *,
    plan: AdPlan,
    campaign_id: UUID,
    order_id: UUID | None = None,
) -> AdCampaign:
    campaign = await db.get(AdCampaign, campaign_id)
    if campaign is None:
        raise ApiError(422, "campaign_not_found", "Campaign not found")
    if campaign.is_house_ad:
        raise ApiError(
            422,
            "campaign_is_house_ad",
            "House ads cannot be linked to advertiser orders",
        )
    if campaign.slot_id != plan.slot_id:
        raise ApiError(
            422,
            "order_campaign_slot_mismatch",
            "Campaign placement must match the selected plan placement",
        )
    existing = await linked_order_for_campaign(db, campaign.id)
    if existing is not None and (order_id is None or existing.id != order_id):
        raise ApiError(
            422,
            "campaign_already_ordered",
            "This campaign is already linked to another order",
        )
    return campaign


async def create_fulfilment_campaign(
    db: AsyncSession,
    *,
    plan: AdPlan,
    advertiser: AdAdvertiser,
    created_by_id: UUID | None,
    starts_on: date | None,
    ends_on: date | None,
) -> AdCampaign:
    starts_at, ends_at = order_window_to_campaign_datetimes(starts_on, ends_on)
    campaign = AdCampaign(
        id=new_id(),
        slot_id=plan.slot_id,
        created_by_id=created_by_id,
        title=f"{plan.name} · {advertiser.organization_name}",
        status="draft",
        is_house_ad=False,
        priority=0,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    db.add(campaign)
    await db.flush()
    return campaign


def ensure_order_can_be_active(*, campaign_id: UUID | None, payment_status: str) -> None:
    if campaign_id is None:
        raise ApiError(
            422,
            "order_campaign_required",
            "An active order must be linked to a fulfilment campaign",
        )
    if payment_status != PAID_PAYMENT:
        raise ApiError(
            422,
            "order_payment_required",
            "An active order must be marked paid",
        )


def apply_order_side_effects(campaign: AdCampaign | None, order: AdOrder) -> None:
    if campaign is None:
        return
    if order.status == "cancelled" or order.payment_status == "refunded":
        if campaign.status in LIVE_CAMPAIGN_STATUSES:
            campaign.status = "paused"
        return
    sync_campaign_flight_from_order(campaign, order)
    if order.status == "completed" and campaign.status != "completed":
        campaign.status = "completed"


def default_order_end(starts_on: date | None, duration_days: int) -> date | None:
    if starts_on is None:
        return None
    return starts_on + timedelta(days=duration_days)
