from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import (
    AdAdvertiser,
    AdCampaign,
    AdOrder,
    AdPlan,
    AdSlot,
    Announcement,
    Article,
    Document,
    Event,
    EventRegistration,
    ExecutiveAppointment,
    Gallery,
    GalleryItem,
    MediaAsset,
    MediaVariant,
    Notification,
    OrganizationUnit,
    OutboxEvent,
    Role,
    User,
    UserRole,
)
from utag_api.security import hash_password


async def admin_headers(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


async def test_permanent_delete_is_administrator_only(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    target_id = new_id()
    async with session_factory() as session:
        secretary_role = await session.scalar(select(Role).where(Role.key == "secretary"))
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert secretary_role is not None
        assert administrator is not None
        secretary = User(
            id=new_id(),
            email="delete-denied@example.edu.gh",
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            other_name="Delete",
            surname="Denied",
        )
        session.add_all(
            [
                secretary,
                Article(
                    id=target_id,
                    slug="administrator-only-delete",
                    title="Administrator-only delete",
                    content_json={},
                    content_html="Temporary article",
                ),
            ]
        )
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=secretary.id,
                role_id=secretary_role.id,
                assigned_by_id=administrator.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "delete-denied@example.edu.gh",
            "password": "StrongPassword123",
        },
    )
    assert login.status_code == 200
    assert "content.publish" in login.json()["user"]["permissions"]
    assert "records.delete" not in login.json()["user"]["permissions"]

    denied = await client.delete(
        f"/api/v1/content/articles/{target_id}/permanent",
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["details"]["missing"] == ["records.delete"]
    async with session_factory() as session:
        assert await session.get(Article, target_id) is not None


async def test_member_delete_is_permanent_but_blocks_shared_history(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    headers = await admin_headers(client)
    deletable_id = new_id()
    linked_id = new_id()
    appointment_id = new_id()
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    id=deletable_id,
                    email="delete.me@example.edu.gh",
                    password_hash=hash_password("StrongPassword123"),
                    status="invited",
                    other_name="Delete",
                    surname="Me",
                ),
                User(
                    id=linked_id,
                    email="keep.history@example.edu.gh",
                    password_hash=hash_password("StrongPassword123"),
                    status="active",
                    other_name="Keep",
                    surname="History",
                ),
            ]
        )
        session.add(
            ExecutiveAppointment(
                id=appointment_id,
                user_id=linked_id,
                position="Treasurer",
            )
        )
        await session.commit()

    deleted = await client.delete(
        f"/api/v1/members/{deletable_id}/permanent",
        headers=headers,
    )
    assert deleted.status_code == 200
    async with session_factory() as session:
        assert await session.get(User, deletable_id) is None

    blocked = await client.delete(
        f"/api/v1/members/{linked_id}/permanent",
        headers=headers,
    )
    assert blocked.status_code == 409
    error = blocked.json()["error"]
    assert error["code"] == "member_delete_blocked"
    assert "executive appointment" in error["message"]
    assert error["details"]["dependencies"] == [{"label": "executive appointment", "count": 1}]
    async with session_factory() as session:
        assert await session.get(User, linked_id) is not None
        assert await session.get(ExecutiveAppointment, appointment_id) is not None

    appointment_deleted = await client.delete(
        f"/api/v1/executives/{appointment_id}/permanent",
        headers=headers,
    )
    assert appointment_deleted.status_code == 200
    member_deleted = await client.delete(
        f"/api/v1/members/{linked_id}/permanent",
        headers=headers,
    )
    assert member_deleted.status_code == 200


async def test_organization_delete_blocks_every_known_linkage(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    headers = await admin_headers(client)
    empty_id = new_id()
    parent_id = new_id()
    child_id = new_id()
    announcement_id = new_id()
    async with session_factory() as session:
        session.add_all(
            [
                OrganizationUnit(
                    id=empty_id,
                    unit_type="committee",
                    name="Temporary Committee",
                    slug="temporary-committee",
                ),
                OrganizationUnit(
                    id=parent_id,
                    unit_type="college",
                    name="Linked College",
                    slug="linked-college",
                ),
                OrganizationUnit(
                    id=child_id,
                    unit_type="school",
                    name="Linked School",
                    slug="linked-school",
                    parent_id=parent_id,
                ),
                Announcement(
                    id=announcement_id,
                    title="College notice",
                    content_json={},
                    content_html="Notice",
                    audiences=[{"type": "unit", "value": str(parent_id)}],
                ),
            ]
        )
        await session.commit()

    deleted = await client.delete(
        f"/api/v1/organization/units/{empty_id}/permanent",
        headers=headers,
    )
    assert deleted.status_code == 200

    blocked = await client.delete(
        f"/api/v1/organization/units/{parent_id}/permanent",
        headers=headers,
    )
    assert blocked.status_code == 409
    message = blocked.json()["error"]["message"]
    assert "child organization unit" in message
    assert "announcement audience" in message
    async with session_factory() as session:
        assert await session.get(OrganizationUnit, empty_id) is None
        assert await session.get(OrganizationUnit, parent_id) is not None


async def test_content_deletes_owned_links_and_blocks_member_history(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    headers = await admin_headers(client)
    article_id = new_id()
    announcement_id = new_id()
    notification_id = new_id()
    event_id = new_id()
    document_id = new_id()
    gallery_id = new_id()
    media_id = new_id()
    gallery_item_id = new_id()
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        session.add_all(
            [
                MediaAsset(
                    id=media_id,
                    owner_id=administrator.id,
                    storage_key=f"tests/{media_id}.png",
                    original_filename="shared.png",
                    content_type="image/png",
                    byte_size=100,
                    sha256="a" * 64,
                    status="ready",
                    is_private=False,
                ),
                Article(
                    id=article_id,
                    slug="temporary-article",
                    title="Temporary article",
                    content_json={},
                    content_html="Article",
                ),
                Announcement(
                    id=announcement_id,
                    title="Delivered notice",
                    content_json={},
                    content_html="Notice",
                ),
                Notification(
                    id=notification_id,
                    user_id=administrator.id,
                    category="announcement",
                    title="Delivered notice",
                    body="Notice",
                    resource_type="announcement",
                    resource_id=announcement_id,
                ),
                Event(
                    id=event_id,
                    slug="registered-event",
                    title="Registered event",
                    start_date=date.today(),
                ),
                EventRegistration(
                    id=new_id(),
                    event_id=event_id,
                    user_id=administrator.id,
                ),
                Document(
                    id=document_id,
                    public_id="LEGAL-HOLD-001",
                    title="Held document",
                    legal_hold=True,
                ),
                Gallery(
                    id=gallery_id,
                    slug="temporary-gallery",
                    title="Temporary gallery",
                ),
                GalleryItem(
                    id=gallery_item_id,
                    gallery_id=gallery_id,
                    media_asset_id=media_id,
                ),
            ]
        )
        await session.commit()

    assert (
        await client.delete(
            f"/api/v1/content/articles/{article_id}/permanent",
            headers=headers,
        )
    ).status_code == 200
    announcement = await client.delete(
        f"/api/v1/content/announcements/{announcement_id}/permanent",
        headers=headers,
    )
    assert announcement.status_code == 409
    assert "member delivery" in announcement.json()["error"]["message"]
    assert (
        await client.delete(
            f"/api/v1/notifications/{notification_id}/permanent",
            headers=headers,
        )
    ).status_code == 200
    assert (
        await client.delete(
            f"/api/v1/content/announcements/{announcement_id}/permanent",
            headers=headers,
        )
    ).status_code == 200
    event = await client.delete(
        f"/api/v1/events/{event_id}/permanent",
        headers=headers,
    )
    assert event.status_code == 409
    assert "registration record" in event.json()["error"]["message"]
    document = await client.delete(
        f"/api/v1/documents/{document_id}/permanent",
        headers=headers,
    )
    assert document.status_code == 409
    assert "legal hold" in document.json()["error"]["message"]
    assert (
        await client.delete(
            f"/api/v1/galleries/{gallery_id}/permanent",
            headers=headers,
        )
    ).status_code == 200

    async with session_factory() as session:
        assert await session.get(Article, article_id) is None
        assert await session.get(Announcement, announcement_id) is None
        assert await session.get(Event, event_id) is not None
        assert await session.get(Document, document_id) is not None
        assert await session.get(Gallery, gallery_id) is None
        assert await session.get(GalleryItem, gallery_item_id) is None
        assert await session.get(MediaAsset, media_id) is not None


async def test_media_delete_removes_storage_only_when_unreferenced(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    headers = await admin_headers(client)
    blocked_asset_id = new_id()
    processing_asset_id = new_id()
    deletable_asset_id = new_id()
    variant_id = new_id()
    article_id = new_id()
    async with session_factory() as session:
        session.add_all(
            [
                MediaAsset(
                    id=blocked_asset_id,
                    storage_key=f"tests/{blocked_asset_id}.png",
                    original_filename="linked.png",
                    content_type="image/png",
                    byte_size=100,
                    sha256="b" * 64,
                    status="ready",
                    is_private=False,
                ),
                MediaAsset(
                    id=deletable_asset_id,
                    storage_key=f"tests/{deletable_asset_id}.png",
                    original_filename="delete.png",
                    content_type="image/png",
                    byte_size=100,
                    sha256="c" * 64,
                    status="ready",
                    is_private=False,
                ),
                MediaAsset(
                    id=processing_asset_id,
                    storage_key=f"tests/{processing_asset_id}.png",
                    original_filename="processing.png",
                    content_type="image/png",
                    byte_size=100,
                    sha256="e" * 64,
                    status="scanning",
                    is_private=False,
                ),
                MediaVariant(
                    id=variant_id,
                    asset_id=deletable_asset_id,
                    variant="thumb",
                    storage_key=f"tests/{deletable_asset_id}-thumb.png",
                    content_type="image/png",
                    byte_size=50,
                    sha256="d" * 64,
                ),
                Article(
                    id=article_id,
                    slug="linked-media-article",
                    title="Linked media article",
                    content_json={},
                    content_html="Article",
                    featured_media_id=blocked_asset_id,
                ),
            ]
        )
        await session.commit()

    blocked = await client.delete(
        f"/api/v1/media/{blocked_asset_id}/permanent",
        headers=headers,
    )
    assert blocked.status_code == 409
    assert "featured article" in blocked.json()["error"]["message"]
    processing = await client.delete(
        f"/api/v1/media/{processing_asset_id}/permanent",
        headers=headers,
    )
    assert processing.status_code == 409
    assert "security processing" in processing.json()["error"]["message"]
    async with session_factory() as session:
        assert await session.scalar(
            select(OutboxEvent.id).where(
                OutboxEvent.event_type == "task.dispatch",
                OutboxEvent.aggregate_id == blocked_asset_id,
            )
        ) is None
        assert await session.get(MediaAsset, processing_asset_id) is not None

    deleted = await client.delete(
        f"/api/v1/media/{deletable_asset_id}/permanent",
        headers=headers,
    )
    assert deleted.status_code == 200
    async with session_factory() as session:
        assert await session.get(MediaAsset, deletable_asset_id) is None
        assert await session.get(MediaVariant, variant_id) is None
        cleanup = await session.scalar(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "task.dispatch",
                OutboxEvent.aggregate_id == deletable_asset_id,
            )
        )
        assert cleanup is not None
        assert cleanup.payload["task_name"] == "utag.media.delete_storage"
        assert set(cleanup.payload["args"][0]) == {
            f"tests/{deletable_asset_id}.png",
            f"tests/{deletable_asset_id}-thumb.png",
        }


async def test_advert_delete_blocks_dependencies_and_financial_history(
    client: AsyncClient,
    session_factory,
) -> None:  # type: ignore[no-untyped-def]
    headers = await admin_headers(client)
    slot_id = new_id()
    plan_id = new_id()
    advertiser_id = new_id()
    campaign_id = new_id()
    order_id = new_id()
    empty_advertiser_id = new_id()
    async with session_factory() as session:
        session.add_all(
            [
                AdSlot(
                    id=slot_id,
                    key="test-placement",
                    name="Test placement",
                    width=1200,
                    height=300,
                ),
                AdPlan(
                    id=plan_id,
                    slot_id=slot_id,
                    name="Test plan",
                    price=Decimal("100"),
                ),
                AdAdvertiser(
                    id=advertiser_id,
                    organization_name="Linked Client",
                    email="linked.client@example.com",
                ),
                AdAdvertiser(
                    id=empty_advertiser_id,
                    organization_name="Temporary Client",
                    email="temporary.client@example.com",
                ),
                AdCampaign(
                    id=campaign_id,
                    slot_id=slot_id,
                    title="Paid campaign",
                    impressions=10,
                ),
                AdOrder(
                    id=order_id,
                    advertiser_id=advertiser_id,
                    plan_id=plan_id,
                    campaign_id=campaign_id,
                    status="active",
                    payment_status="paid",
                    starts_on=datetime.now(UTC).date(),
                ),
            ]
        )
        await session.commit()

    slot = await client.delete(
        f"/api/v1/adverts/slots/{slot_id}/permanent",
        headers=headers,
    )
    assert slot.status_code == 409
    assert "advertising plan" in slot.json()["error"]["message"]
    plan = await client.delete(
        f"/api/v1/adverts/plans/{plan_id}/permanent",
        headers=headers,
    )
    assert plan.status_code == 409
    assert "advertising order" in plan.json()["error"]["message"]
    campaign = await client.delete(
        f"/api/v1/adverts/campaigns/{campaign_id}/permanent",
        headers=headers,
    )
    assert campaign.status_code == 409
    assert "advertising order" in campaign.json()["error"]["message"]
    order = await client.delete(
        f"/api/v1/adverts/orders/{order_id}/permanent",
        headers=headers,
    )
    assert order.status_code == 409
    assert "payment history" in order.json()["error"]["message"]
    advertiser = await client.delete(
        f"/api/v1/adverts/advertisers/{advertiser_id}/permanent",
        headers=headers,
    )
    assert advertiser.status_code == 409

    deleted = await client.delete(
        f"/api/v1/adverts/advertisers/{empty_advertiser_id}/permanent",
        headers=headers,
    )
    assert deleted.status_code == 200
    async with session_factory() as session:
        assert await session.get(AdAdvertiser, empty_advertiser_id) is None
        assert await session.get(AdOrder, order_id) is not None
