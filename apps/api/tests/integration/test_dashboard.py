from datetime import UTC, date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import Document, Event, FeatureFlag, Role, User, UserRole
from utag_api.security import hash_password

MEMBER_EMAIL = "kofi.member@example.edu.gh"


async def seed_role_account(session_factory, email: str, role_key: str) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        role = await session.scalar(select(Role).where(Role.key == role_key))
        assert role is not None
        user = User(
            id=new_id(),
            email=email,
            password_hash=hash_password("StrongPassword123"),
            status="active",
            email_verified=True,
            other_name="Kofi",
            surname="Boateng",
        )
        session.add(user)
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=user.id,
                role_id=role.id,
                assigned_by_id=user.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def seed_overview_records(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        session.add_all(
            [
                Event(
                    id=new_id(),
                    slug="published-congregation",
                    title="Published congregation",
                    start_date=date.today() + timedelta(days=3),
                    status="upcoming",
                    publication_status="published",
                    published_at=datetime.now(UTC),
                ),
                Event(
                    id=new_id(),
                    slug="unpublished-negotiation",
                    title="Unpublished negotiation briefing",
                    start_date=date.today() + timedelta(days=4),
                    status="upcoming",
                    publication_status="draft",
                ),
                Document(
                    id=new_id(),
                    public_id="UTAG-RESTRICTED",
                    title="Administrator only memorandum",
                    audiences=[{"type": "role", "value": "administrator"}],
                ),
            ]
        )
        await session.commit()


async def login(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "StrongPassword123"}
    )
    assert response.status_code == 200


async def test_overview_scopes_privileged_blocks_to_permitted_roles(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    await seed_role_account(session_factory, MEMBER_EMAIL, "member")
    await seed_overview_records(session_factory)

    await login(client, "admin@example.edu.gh")
    administrator = (await client.get("/api/v1/dashboard/overview")).json()

    assert {"activity", "pulse", "members", "documents"} <= set(administrator["sections"])
    assert [metric["key"] for metric in administrator["metrics"]] == [
        "members",
        "documents",
        "events",
        "unread",
    ]
    assert len(administrator["pulse"]) == 14
    assert {event["title"] for event in administrator["upcoming_events"]} == {
        "Published congregation",
        "Unpublished negotiation briefing",
    }

    async with session_factory() as session:
        session.add(
            FeatureFlag(
                id=new_id(),
                key="association-pulse",
                description="Dashboard activity chart",
                enabled=False,
            )
        )
        await session.commit()
    administrator_without_pulse = (await client.get("/api/v1/dashboard/overview")).json()
    assert "pulse" not in administrator_without_pulse["sections"]
    assert administrator_without_pulse["pulse"] == []

    await login(client, MEMBER_EMAIL)
    member = (await client.get("/api/v1/dashboard/overview")).json()

    assert "activity" not in member["sections"]
    assert "pulse" not in member["sections"]
    assert "members" not in member["sections"]
    assert member["recent_activity"] == []
    assert member["pulse"] == []
    assert member["executive_appointment"] is None
    # A member must never learn about unpublished events from the overview.
    assert [event["title"] for event in member["upcoming_events"]] == ["Published congregation"]

    metrics = {metric["key"]: metric for metric in member["metrics"]}
    assert "members" not in metrics
    assert metrics["events"]["value"] == 1
    # The memorandum is restricted to administrators, so it must not be counted.
    assert metrics["documents"]["label"] == "Available documents"
    assert metrics["documents"]["value"] == 0
