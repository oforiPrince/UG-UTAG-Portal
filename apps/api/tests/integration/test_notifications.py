from datetime import UTC, datetime
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import BackgroundJob, Notification, Role, User, UserRole
from utag_api.security import hash_password


async def test_notification_messages_preserve_safe_formatting(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    async with session_factory() as session:
        recipient_id = await session.scalar(
            select(User.id).where(User.email == "admin@example.edu.gh")
        )
    assert recipient_id is not None

    sent = await client.post(
        "/api/v1/notifications/send",
        headers=headers,
        json={
            "user_ids": [str(recipient_id)],
            "title": "Formatted member update",
            "body": (
                "<p>Please read the <strong>member update</strong>.</p>"
                "<script>alert('unsafe')</script>"
            ),
        },
    )
    assert sent.status_code == 200

    inbox = await client.get("/api/v1/notifications")
    assert inbox.status_code == 200
    notice = inbox.json()["items"][0]
    assert notice["title"] == "Formatted member update"
    assert notice["body"] == ("<p>Please read the <strong>member update</strong>.</p>")

    async with session_factory() as session:
        email_job = await session.scalar(
            select(BackgroundJob).where(BackgroundJob.kind == "email.notification")
        )
        assert email_job is not None
        assert email_job.status == "queued"
        assert email_job.input_json["notification_ids"] == [notice["id"]]


async def test_publishing_announcement_delivers_once_to_targeted_active_roles(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        member_role = await session.scalar(select(Role).where(Role.key == "member"))
        executive_role = await session.scalar(select(Role).where(Role.key == "executive"))
        assert member_role is not None
        assert executive_role is not None

        member = User(
            id=new_id(),
            email="member@example.edu.gh",
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            other_name="Kojo",
            surname="Asare",
        )
        executive = User(
            id=new_id(),
            email="executive@example.edu.gh",
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            other_name="Akua",
            surname="Owusu",
        )
        session.add_all([member, executive])
        await session.flush()
        session.add_all(
            [
                UserRole(
                    id=new_id(),
                    user_id=member.id,
                    role_id=member_role.id,
                    assigned_at=datetime.now(UTC),
                ),
                UserRole(
                    id=new_id(),
                    user_id=executive.id,
                    role_id=executive_role.id,
                    assigned_at=datetime.now(UTC),
                ),
            ]
        )
        await session.commit()
        member_id = member.id

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = await client.post(
        "/api/v1/content/announcements",
        headers=headers,
        json={
            "title": "Members-only notice",
            "content_html": "<p>Official member information.</p>",
            "priority": "high",
            "audiences": [{"type": "role", "value": "member"}],
            "status": "published",
        },
    )
    assert created.status_code == 201
    announcement = created.json()
    announcement_id = UUID(announcement["id"])

    async with session_factory() as session:
        deliveries = (
            await session.scalars(
                select(Notification).where(
                    Notification.resource_type == "announcement",
                    Notification.resource_id == announcement_id,
                )
            )
        ).all()
        assert [delivery.user_id for delivery in deliveries] == [member_id]
        assert deliveries[0].category == "announcement"
        assert deliveries[0].body == "<p>Official member information.</p>"
        email_job = await session.scalar(
            select(BackgroundJob).where(BackgroundJob.kind == "email.announcement")
        )
        assert email_job is not None
        assert email_job.status == "queued"

    updated = await client.patch(
        f"/api/v1/content/announcements/{announcement['id']}",
        headers={**headers, "If-Match": f'"{announcement["version"]}"'},
        json={
            "title": "Members-only notice",
            "content_html": "<p>Corrected official member information.</p>",
            "priority": "high",
            "audiences": [{"type": "role", "value": "member"}],
            "status": "published",
        },
    )
    assert updated.status_code == 200

    async with session_factory() as session:
        delivery_count = await session.scalar(
            select(func.count(Notification.id)).where(
                Notification.resource_type == "announcement",
                Notification.resource_id == announcement_id,
            )
        )
        assert delivery_count == 1


async def test_moderation_approve_delivers_announcement_notifications(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        member_role = await session.scalar(select(Role).where(Role.key == "member"))
        assert member_role is not None
        member = User(
            id=new_id(),
            email="review-member@example.edu.gh",
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            other_name="Yaw",
            surname="Boateng",
        )
        session.add(member)
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=member.id,
                role_id=member_role.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()
        member_id = member.id

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    created = await client.post(
        "/api/v1/content/announcements",
        headers=headers,
        json={
            "title": "Review queue notice",
            "content_html": "<p>Awaiting approval.</p>",
            "priority": "normal",
            "audiences": [{"type": "role", "value": "member"}],
            "status": "review",
        },
    )
    assert created.status_code == 201
    announcement = created.json()
    announcement_id = UUID(announcement["id"])

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count(Notification.id)).where(
                    Notification.resource_type == "announcement",
                    Notification.resource_id == announcement_id,
                )
            )
            == 0
        )

    approved = await client.post(
        f"/api/v1/moderation/announcement/{announcement['id']}",
        headers=headers,
        json={"decision": "approve", "expected_version": announcement["version"]},
    )
    assert approved.status_code == 200

    async with session_factory() as session:
        deliveries = (
            await session.scalars(
                select(Notification).where(
                    Notification.resource_type == "announcement",
                    Notification.resource_id == announcement_id,
                )
            )
        ).all()
        assert [delivery.user_id for delivery in deliveries] == [member_id]


async def test_direct_send_cannot_impersonate_an_announcement(
    client: AsyncClient,
) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    response = await client.post(
        "/api/v1/notifications/send",
        headers={"X-CSRF-Token": login.json()["csrf_token"]},
        json={
            "user_ids": [login.json()["user"]["id"]],
            "category": "announcement",
            "title": "Not an official announcement",
            "body": "<p>Bypass attempt</p>",
        },
    )
    assert response.status_code == 422
