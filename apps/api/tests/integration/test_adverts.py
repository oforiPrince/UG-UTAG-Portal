from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import AdAdvertiser, AdCampaign, AdOrder, AdPlan, AdSlot, MediaAsset, User
from utag_api.seed_data import seed_portal_defaults


async def _login(client: AsyncClient) -> str:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    return login.json()["csrf_token"]


async def test_public_ads_include_placement_dimensions(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        await seed_portal_defaults(session)
        slot = await session.scalar(select(AdSlot).where(AdSlot.key == "footer"))
        assert slot is not None
        admin = await session.scalar(select(User).where(User.email == "admin@example.edu.gh"))
        assert admin is not None
        media = MediaAsset(
            id=new_id(),
            owner_id=admin.id,
            original_filename="footer-ad.png",
            content_type="image/png",
            byte_size=1200,
            sha256="a" * 64,
            storage_key=f"media/{new_id()}.png",
            status="ready",
            is_private=False,
        )
        session.add(media)
        await session.flush()
        session.add(
            AdCampaign(
                id=new_id(),
                slot_id=slot.id,
                created_by_id=admin.id,
                title="Footer sponsor",
                media_asset_id=media.id,
                target_url="https://example.edu.gh/sponsor",
                status="active",
                is_house_ad=True,
                priority=10,
                starts_at=datetime.now(UTC) - timedelta(days=1),
                ends_at=datetime.now(UTC) + timedelta(days=30),
            )
        )
        await session.commit()

    response = await client.get("/api/v1/public/ads/footer")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["slot_key"] == "footer"
    assert payload[0]["width"] == 970
    assert payload[0]["height"] == 90
    assert payload[0]["title"] == "Footer sponsor"

    inactive = await client.get("/api/v1/public/ads/retired-not-a-slot")
    assert inactive.status_code == 200
    assert inactive.json() == []


async def test_plan_requires_placement_and_order_matches_campaign_slot(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    csrf = await _login(client)
    headers = {"X-CSRF-Token": csrf}

    async with session_factory() as session:
        await seed_portal_defaults(session)
        footer = await session.scalar(select(AdSlot).where(AdSlot.key == "footer"))
        news = await session.scalar(select(AdSlot).where(AdSlot.key == "news-sidebar"))
        assert footer is not None and news is not None
        admin = await session.scalar(select(User).where(User.email == "admin@example.edu.gh"))
        assert admin is not None
        footer_plan = await session.scalar(select(AdPlan).where(AdPlan.slot_id == footer.id))
        assert footer_plan is not None
        campaign = AdCampaign(
            id=new_id(),
            slot_id=news.id,
            created_by_id=admin.id,
            title="News rail campaign",
            status="draft",
            priority=0,
        )
        session.add(campaign)
        await session.commit()
        footer_plan_id = str(footer_plan.id)
        campaign_id = str(campaign.id)
        footer_id = str(footer.id)

    missing_slot = await client.post(
        "/api/v1/adverts/plans",
        headers=headers,
        json={
            "name": "Broken plan",
            "price": "100.00",
            "duration_days": 30,
        },
    )
    assert missing_slot.status_code == 422

    created = await client.post(
        "/api/v1/adverts/plans",
        headers=headers,
        json={
            "slot_id": footer_id,
            "name": "Custom footer plan",
            "price": "500.00",
            "duration_days": 14,
            "is_active": True,
        },
    )
    assert created.status_code == 201
    assert created.json()["slot_id"] == footer_id
    assert created.json()["placement_name"] == "Site footer strip"
    assert created.json()["width"] == 970

    advertiser = await client.post(
        "/api/v1/adverts/advertisers",
        headers=headers,
        json={
            "organization_name": "Acme Sponsors Ltd",
            "contact_name": "Kojo Mensah",
            "email": "ads@acme.example",
            "phone": "+233200000000",
            "is_active": True,
        },
    )
    assert advertiser.status_code == 201
    advertiser_id = advertiser.json()["id"]

    mismatched = await client.post(
        "/api/v1/adverts/orders",
        headers=headers,
        json={
            "advertiser_id": advertiser_id,
            "plan_id": footer_plan_id,
            "campaign_id": campaign_id,
            "status": "pending",
            "payment_status": "unpaid",
        },
    )
    assert mismatched.status_code == 422
    assert mismatched.json()["error"]["code"] == "order_campaign_slot_mismatch"


async def test_paid_campaign_cannot_go_live_without_paid_order(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    csrf = await _login(client)
    headers = {"X-CSRF-Token": csrf}

    async with session_factory() as session:
        await seed_portal_defaults(session)
        footer = await session.scalar(select(AdSlot).where(AdSlot.key == "footer"))
        assert footer is not None
        admin = await session.scalar(select(User).where(User.email == "admin@example.edu.gh"))
        assert admin is not None
        media = MediaAsset(
            id=new_id(),
            owner_id=admin.id,
            original_filename="paid.png",
            content_type="image/png",
            byte_size=100,
            sha256="b" * 64,
            storage_key=f"media/{new_id()}.png",
            status="ready",
            is_private=False,
        )
        session.add(media)
        await session.commit()
        footer_id = str(footer.id)
        media_id = str(media.id)
        plan = await session.scalar(select(AdPlan).where(AdPlan.slot_id == footer.id))
        assert plan is not None
        plan_id = str(plan.id)

    blocked = await client.post(
        "/api/v1/adverts/campaigns",
        headers=headers,
        json={
            "slot_id": footer_id,
            "title": "Orphan paid campaign",
            "media_asset_id": media_id,
            "status": "active",
            "is_house_ad": False,
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "campaign_order_required"

    house = await client.post(
        "/api/v1/adverts/campaigns",
        headers=headers,
        json={
            "slot_id": footer_id,
            "title": "House promo",
            "media_asset_id": media_id,
            "status": "active",
            "is_house_ad": True,
        },
    )
    assert house.status_code == 201
    assert house.json()["is_house_ad"] is True
    assert house.json()["fulfilment"] == "House ad"

    advertiser = await client.post(
        "/api/v1/adverts/advertisers",
        headers=headers,
        json={
            "organization_name": "Campus Bank",
            "contact_name": "Sales Desk",
            "email": "ads@campusbank.example",
            "is_active": True,
        },
    )
    assert advertiser.status_code == 201

    order = await client.post(
        "/api/v1/adverts/orders",
        headers=headers,
        json={
            "advertiser_id": advertiser.json()["id"],
            "plan_id": plan_id,
            "status": "pending",
            "payment_status": "unpaid",
            "starts_on": str(date.today()),
        },
    )
    assert order.status_code == 201
    body = order.json()
    assert body["campaign_id"]
    assert body["advertiser_name"] == "Campus Bank"
    campaign_id = body["campaign_id"]
    order_id = body["id"]

    async with session_factory() as session:
        campaign = await session.get(AdCampaign, UUID(campaign_id))
        assert campaign is not None
        assert campaign.status == "draft"
        media = await session.get(MediaAsset, UUID(media_id))
        assert media is not None
        campaign.media_asset_id = media.id
        await session.commit()

    still_blocked = await client.patch(
        f"/api/v1/adverts/campaigns/{campaign_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert still_blocked.status_code == 422
    assert still_blocked.json()["error"]["code"] == "campaign_order_not_ready"

    paid = await client.patch(
        f"/api/v1/adverts/orders/{order_id}",
        headers=headers,
        json={"payment_status": "paid", "status": "approved"},
    )
    assert paid.status_code == 200

    live = await client.patch(
        f"/api/v1/adverts/campaigns/{campaign_id}",
        headers=headers,
        json={"status": "active"},
    )
    assert live.status_code == 200
    assert live.json()["status"] == "active"
    assert live.json()["fulfilment"] == "Paid · ready"

    cancel = await client.delete(
        f"/api/v1/adverts/orders/{order_id}",
        headers=headers,
    )
    assert cancel.status_code == 200
    async with session_factory() as session:
        campaign = await session.get(AdCampaign, UUID(campaign_id))
        assert campaign is not None
        assert campaign.status == "paused"
        order_row = await session.get(AdOrder, UUID(order_id))
        assert order_row is not None
        assert order_row.status == "cancelled"
