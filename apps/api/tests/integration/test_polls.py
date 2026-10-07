from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from utag_api.database import new_id
from utag_api.dependencies import Principal
from utag_api.models import (
    AuditEvent,
    Conversation,
    ConversationMember,
    Notification,
    OrganizationUnit,
    OutboxEvent,
    Role,
    Session,
    User,
    UserRole,
)
from utag_api.models.polls import Poll, PollDelivery, PollSelection, PollVote
from utag_api.schemas.polls import PollAudience
from utag_api.security import hash_password
from utag_api.services.polls import (
    authorized_poll_topics,
    poll_state,
    reconcile_poll_lifecycle,
    resolve_audience_ids,
)

PASSWORD = "StrongPassword123"  # noqa: S105 - disposable test credentials


async def login(client: AsyncClient, email: str = "admin@example.edu.gh") -> dict[str, str]:
    result = await client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert result.status_code == 200
    return {"X-CSRF-Token": result.json()["csrf_token"]}


async def add_member(
    factory: async_sessionmaker[AsyncSession], email: str, *, role: str = "member", **fields: Any
) -> UUID:
    async with factory() as db:
        user = User(
            id=new_id(),
            email=email,
            password_hash=hash_password(PASSWORD),
            status="active",
            email_verified=True,
            other_name="Ama",
            surname=email.split("@")[0],
            **fields,
        )
        db.add(user)
        await db.flush()
        role_id = await db.scalar(select(Role.id).where(Role.key == role))
        assert role_id
        db.add(
            UserRole(id=new_id(), user_id=user.id, role_id=role_id, assigned_at=datetime.now(UTC))
        )
        await db.commit()
        return user.id


async def create_poll(
    client: AsyncClient, headers: dict[str, str], *, publish: bool = True, **changes: Any
) -> dict[str, Any]:
    data = {
        "title": "Industrial action consultation",
        "question": "Do you support the proposed industrial action?",
        "options": [
            "YES, I support the industrial action",
            "NO, I do not support the industrial action",
        ],
        "audiences": [{"type": "all_members"}],
        "closes_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        **changes,
    }
    response = await client.post("/api/v1/polls", json=data, headers=headers)
    assert response.status_code == 201, response.text
    poll = response.json()
    if publish:
        response = await client.post(f"/api/v1/polls/{poll['id']}/publish", headers=headers)
        assert response.status_code == 200, response.text
        poll = response.json()
    return poll


async def test_confidential_final_ballot_and_hidden_results(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    member_id = await add_member(session_factory, "member@example.edu.gh")
    admin_headers = await login(client)
    poll = await create_poll(client, admin_headers)
    assert poll["privacy"] == "confidential"
    assert poll["results_visibility"] == "after_close"
    assert poll["allow_vote_changes"] is False
    assert poll["eligible_count"] == 2
    assert "response_count" not in poll
    member_headers = await login(client, "member@example.edu.gh")
    hidden = await client.get(f"/api/v1/polls/{poll['id']}/results")
    assert hidden.status_code == 403
    assert (await client.get(f"/api/v1/polls/{poll['id']}/export")).status_code == 403
    options = [item["id"] for item in poll["options"]]
    no_csrf = await client.put(f"/api/v1/polls/{poll['id']}/vote", json={"option_ids": options[:1]})
    assert no_csrf.status_code == 403
    voted = await client.put(
        f"/api/v1/polls/{poll['id']}/vote", json={"option_ids": options[:1]}, headers=member_headers
    )
    assert voted.status_code == 200, voted.text
    assert voted.json()["my_vote"] == options[:1]
    assert voted.json()["can_vote"] is False
    retry = await client.put(
        f"/api/v1/polls/{poll['id']}/vote", json={"option_ids": options[:1]}, headers=member_headers
    )
    assert retry.status_code == 200
    changed = await client.put(
        f"/api/v1/polls/{poll['id']}/vote", json={"option_ids": options[1:]}, headers=member_headers
    )
    assert changed.status_code == 409
    assert (await client.get(f"/api/v1/polls/{poll['id']}/results")).status_code == 403
    admin_headers = await login(client)
    stats = (await client.get(f"/api/v1/polls/{poll['id']}/results")).json()
    assert stats["response_count"] == 1
    assert stats["turnout_percent"] == 50
    assert [option["votes"] for option in stats["options"]] == [1, 0]
    assert stats["named_voters"] is None
    assert sum(point["responses"] for point in stats["timeline"]) == 1
    csv = await client.get(f"/api/v1/polls/{poll['id']}/export")
    assert csv.status_code == 200
    assert "member@example" not in csv.text
    async with session_factory() as db:
        ballots = (await db.scalars(select(PollVote))).all()
        assert len(ballots) == 1 and ballots[0].user_id == member_id
        events = (
            await db.scalars(
                select(OutboxEvent).where(
                    OutboxEvent.event_type.in_(["poll.vote.recorded", "poll.results.changed"])
                )
            )
        ).all()
        for event in events:
            assert (
                not {"option_ids", "votes", "response_count", "user_id", "member_name"}
                & event.payload.keys()
            )
            assert all(option_id not in str(event.payload) for option_id in options)
        audits = (
            await db.scalars(select(AuditEvent).where(AuditEvent.action == "poll.vote.recorded"))
        ).all()
        assert len(audits) == 1
        assert not audits[0].changes
    closed = await client.post(
        f"/api/v1/polls/{poll['id']}/close",
        json={"reason": "Consultation completed"},
        headers=admin_headers,
    )
    assert closed.status_code == 200 and closed.json()["closed_at"]
    await login(client, "member@example.edu.gh")
    assert (await client.get(f"/api/v1/polls/{poll['id']}/results")).status_code == 200
    member_headers = await login(client, "member@example.edu.gh")
    retry_after_close = await client.put(
        f"/api/v1/polls/{poll['id']}/vote",
        headers=member_headers,
        json={"option_ids": options[:1]},
    )
    assert retry_after_close.status_code == 200


async def test_frozen_electorate_and_manager_cannot_bypass_voting_target(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    member_id = await add_member(session_factory, "selected@example.edu.gh")
    headers = await login(client)
    poll = await create_poll(
        client, headers, audiences=[{"type": "member", "value": str(member_id)}]
    )
    assert poll["can_manage"] is True and poll["can_vote"] is False
    forbidden = await client.put(
        f"/api/v1/polls/{poll['id']}/vote",
        json={"option_ids": [poll["options"][0]["id"]]},
        headers=headers,
    )
    assert forbidden.status_code == 403
    await add_member(session_factory, "late@example.edu.gh")
    selected_headers = await login(client, "selected@example.edu.gh")
    assert (await client.get(f"/api/v1/polls/{poll['id']}")).json()["eligible_count"] == 1
    async with session_factory() as db:
        user = await db.get(User, member_id)
        assert user
        user.status = "suspended"
        await db.commit()
    assert (
        await client.put(
            f"/api/v1/polls/{poll['id']}/vote",
            json={"option_ids": [poll["options"][0]["id"]]},
            headers=selected_headers,
        )
    ).status_code == 401
    await login(client, "late@example.edu.gh")
    assert (await client.get(f"/api/v1/polls/{poll['id']}")).status_code == 404
    assert (await client.get("/api/v1/polls")).json()["total"] == 0


async def test_multiple_choice_revision_after_vote_and_named_visibility(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await add_member(session_factory, "voter@example.edu.gh")
    headers = await login(client)
    poll = await create_poll(
        client,
        headers,
        kind="multiple",
        max_choices=2,
        options=["Option A", "Option B", "Option C"],
        allow_vote_changes=True,
        results_visibility="after_vote",
        privacy="named",
    )
    member_headers = await login(client, "voter@example.edu.gh")
    assert (await client.get(f"/api/v1/polls/{poll['id']}/results")).status_code == 403
    option_ids = [item["id"] for item in poll["options"]]
    too_many = await client.put(
        f"/api/v1/polls/{poll['id']}/vote", json={"option_ids": option_ids}, headers=member_headers
    )
    assert too_many.status_code == 422
    first = await client.put(
        f"/api/v1/polls/{poll['id']}/vote",
        json={"option_ids": option_ids[:2]},
        headers=member_headers,
    )
    assert first.status_code == 200
    assert first.json()["can_vote"] is True
    member_stats = (await client.get(f"/api/v1/polls/{poll['id']}/results")).json()
    assert member_stats["named_voters"] is None
    assert [item["percent"] for item in member_stats["options"]] == [100, 100, 0]
    changed = await client.put(
        f"/api/v1/polls/{poll['id']}/vote",
        json={"option_ids": option_ids[2:]},
        headers=member_headers,
    )
    assert changed.status_code == 200
    await login(client)
    stats = (await client.get(f"/api/v1/polls/{poll['id']}/results")).json()
    assert stats["response_count"] == 1
    assert [item["votes"] for item in stats["options"]] == [0, 0, 1]
    assert stats["named_voters"][0]["option_labels"] == ["Option C"]
    async with session_factory() as db:
        assert await db.scalar(select(func.count(PollVote.id))) == 1
        assert await db.scalar(select(func.count()).select_from(PollSelection)) == 1


async def test_schedule_boundaries_do_not_depend_on_worker_and_lifecycle_is_idempotent(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    headers = await login(client)
    now = datetime.now(UTC)
    poll = await create_poll(client, headers, opens_at=(now + timedelta(hours=1)).isoformat())
    assert poll["status"] == "scheduled" and not poll["can_vote"]
    options = [poll["options"][0]["id"]]
    assert (
        await client.put(
            f"/api/v1/polls/{poll['id']}/vote",
            headers=headers,
            json={"option_ids": [poll["options"][1]["id"]]},
        )
    ).status_code == 409
    assert (
        await client.post(
            f"/api/v1/polls/{poll['id']}/close", headers=headers, json={"reason": "Too early"}
        )
    ).status_code == 409
    async with session_factory() as db:
        row = await db.get(Poll, UUID(poll["id"]))
        assert row
        row.opens_at = now - timedelta(seconds=1)
        await db.commit()
    assert (
        await client.put(
            f"/api/v1/polls/{poll['id']}/vote", headers=headers, json={"option_ids": options}
        )
    ).status_code == 200
    async with session_factory() as db:
        assert await reconcile_poll_lifecycle(db) == 1
        await db.commit()
        assert await reconcile_poll_lifecycle(db) == 0
        await db.commit()
        row = await db.get(Poll, UUID(poll["id"]))
        assert row
        row.closes_at = now - timedelta(seconds=1)
        await db.commit()
    assert (
        await client.put(
            f"/api/v1/polls/{poll['id']}/vote",
            headers=headers,
            json={"option_ids": [poll["options"][1]["id"]]},
        )
    ).status_code == 409
    assert (await client.get(f"/api/v1/polls/{poll['id']}")).json()["status"] == "closed"
    async with session_factory() as db:
        assert await reconcile_poll_lifecycle(db) == 1
        await db.commit()
        assert await reconcile_poll_lifecycle(db) == 0
        await db.commit()
        assert await db.scalar(select(func.count(PollDelivery.id))) == 2
        assert (
            await db.scalar(
                select(func.count(Notification.id)).where(Notification.resource_type == "poll")
            )
            == 2
        )


async def test_reminders_nonvoters_retry_and_extension_notification(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await add_member(session_factory, "reminder@example.edu.gh")
    headers = await login(client)
    poll = await create_poll(client, headers)
    await client.put(
        f"/api/v1/polls/{poll['id']}/vote",
        headers=headers,
        json={"option_ids": [poll["options"][0]["id"]]},
    )
    preview = await client.get(f"/api/v1/polls/{poll['id']}/reminders/preview")
    assert preview.json()["recipient_count"] == 1
    reminder_headers = {**headers, "Idempotency-Key": "retryable-reminder-request"}
    for _ in range(2):
        result = await client.post(
            f"/api/v1/polls/{poll['id']}/reminders", headers=reminder_headers
        )
        assert result.status_code == 200 and result.json()["recipient_count"] == 1
    extension = await client.post(
        f"/api/v1/polls/{poll['id']}/extend",
        headers=headers,
        json={
            "closes_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "reason": "Allow more time for participation",
        },
    )
    assert extension.status_code == 200
    async with session_factory() as db:
        deliveries = (await db.scalars(select(PollDelivery))).all()
        assert len([row for row in deliveries if row.campaign.startswith("reminder:")]) == 1
        assert len([row for row in deliveries if row.campaign.startswith("extension:")]) == 2


async def test_draft_validation_edit_lock_duplicate_and_list_filter(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    member_id = await add_member(session_factory, "target@example.edu.gh")
    headers = await login(client)
    poll = await create_poll(client, headers, publish=False, closes_at=None)
    assert poll["status"] == "draft"
    assert (
        await client.post(f"/api/v1/polls/{poll['id']}/publish", headers=headers)
    ).status_code == 422
    patched = await client.patch(
        f"/api/v1/polls/{poll['id']}",
        headers={**headers, "If-Match": '"1"'},
        json={
            "closes_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
            "audiences": [{"type": "member", "value": str(member_id)}],
        },
    )
    assert patched.status_code == 200
    stale = await client.patch(
        f"/api/v1/polls/{poll['id']}",
        headers={**headers, "If-Match": '"1"'},
        json={"title": "Updated poll"},
    )
    assert stale.status_code == 412
    assert (
        await client.post(f"/api/v1/polls/{poll['id']}/publish", headers=headers)
    ).status_code == 200
    assert (
        await client.patch(
            f"/api/v1/polls/{poll['id']}", headers=headers, json={"title": "Another question"}
        )
    ).status_code == 409
    duplicate = await client.post(f"/api/v1/polls/{poll['id']}/duplicate", headers=headers)
    assert duplicate.status_code == 201
    assert duplicate.json()["published_at"] is None and duplicate.json()["closes_at"] is None
    assert duplicate.json()["has_voted"] is False
    assert (await client.get("/api/v1/polls?eligible_only=true&state=open")).json()["total"] == 0
    assert (await client.get("/api/v1/polls?state=open")).json()["total"] == 1
    assert (await client.get("/api/v1/polls?state=draft")).json()["total"] == 1
    other = await create_poll(client, headers)
    invalid_option = await client.put(
        f"/api/v1/polls/{other['id']}/vote",
        headers=headers,
        json={"option_ids": [poll["options"][0]["id"]]},
    )
    assert invalid_option.status_code == 422


async def test_partial_draft_update_preserves_schedule_and_rejects_naive_input(
    client: AsyncClient,
) -> None:
    headers = await login(client)
    poll = await create_poll(
        client,
        headers,
        publish=False,
        opens_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    )
    response = await client.patch(
        f"/api/v1/polls/{poll['id']}",
        headers=headers,
        json={"title": "Revised consultation title"},
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["title"] == "Revised consultation title"
    assert updated["opens_at"] == poll["opens_at"]
    assert updated["closes_at"] == poll["closes_at"]
    invalid = await client.patch(
        f"/api/v1/polls/{poll['id']}",
        headers=headers,
        json={
            "closes_at": (datetime.now(UTC) + timedelta(days=2)).replace(tzinfo=None).isoformat()
        },
    )
    assert invalid.status_code == 422
    saved = await client.get(f"/api/v1/polls/{poll['id']}")
    assert saved.json()["closes_at"] == poll["closes_at"]


async def test_every_target_selector_union_dedup_and_lookup_permissions(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    async with session_factory() as db:
        units = [
            OrganizationUnit(
                id=new_id(), unit_type=kind, name=f"{kind} alpha", slug=f"{kind}-alpha"
            )
            for kind in ("college", "school", "department")
        ]
        group = Conversation(id=new_id(), kind="group", title="Consultation committee")
        db.add_all([*units, group])
        await db.commit()
    member_id = await add_member(
        session_factory,
        "union@example.edu.gh",
        college_id=units[0].id,
        school_id=units[1].id,
        department_id=units[2].id,
        staff_id="UNION-42",
    )
    async with session_factory() as db:
        db.add(
            ConversationMember(
                id=new_id(), conversation_id=group.id, user_id=member_id, role="member"
            )
        )
        await db.commit()
        targets = [{"type": unit.unit_type, "value": str(unit.id)} for unit in units]
        targets += [
            {"type": "role", "value": "member"},
            {"type": "chat_group", "value": str(group.id)},
            {"type": "member", "value": str(member_id)},
        ]
        for target in targets:
            assert await resolve_audience_ids(db, [PollAudience.model_validate(target)]) == [
                member_id
            ]
        assert await resolve_audience_ids(
            db, [PollAudience.model_validate(target) for target in targets]
        ) == [member_id]
        assert len(await resolve_audience_ids(db, [PollAudience(type="all_members")])) == 2
    headers = await login(client)
    preview = await client.post(
        "/api/v1/polls/audience-preview", headers=headers, json={"audiences": targets}
    )
    assert preview.json()["eligible_count"] == 1
    for target_type in (
        "all_members",
        "college",
        "school",
        "department",
        "role",
        "chat_group",
        "member",
    ):
        result = await client.get(f"/api/v1/polls/audiences?type={target_type}")
        assert result.status_code == 200 and result.json()["items"]
    staff_lookup = await client.get("/api/v1/polls/audiences?type=member&q=UNION-42&page_size=1")
    assert staff_lookup.json()["total"] == 1
    assert staff_lookup.json()["items"][0]["value"] == str(member_id)
    invalid = await client.post(
        "/api/v1/polls/audience-preview",
        headers=headers,
        json={"audiences": [{"type": "school", "value": str(new_id())}]},
    )
    assert invalid.status_code == 422
    await login(client, "union@example.edu.gh")
    assert (await client.get("/api/v1/polls/audiences?type=member")).status_code == 403
    assert (await client.post("/api/v1/polls", headers=headers, json={})).status_code in {403, 422}


def test_poll_state_exact_open_and_close_boundaries() -> None:
    now = datetime.now(UTC)
    poll = Poll(
        id=new_id(),
        title="Test",
        question="Question",
        published_at=now,
        opens_at=now,
        closes_at=now + timedelta(hours=1),
    )
    assert poll_state(poll, now - timedelta(microseconds=1)) == "scheduled"
    assert poll_state(poll, now) == "open"
    assert poll_state(poll, now + timedelta(hours=1)) == "closed"


async def test_result_topics_follow_policy_and_do_not_accumulate_closed_history(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    member_id = await add_member(session_factory, "realtime-voter@example.edu.gh")
    admin_headers = await login(client)
    after_vote = await create_poll(client, admin_headers, results_visibility="after_vote")
    live = await create_poll(client, admin_headers, results_visibility="live")
    member_headers = await login(client, "realtime-voter@example.edu.gh")

    async def topics(permissions: set[str]) -> list[str]:
        async with session_factory() as db:
            user = await db.get(User, member_id)
            session = await db.scalar(select(Session).where(Session.user_id == member_id))
            assert user and session
            principal = Principal(
                user=user, session=session, roles={"member"}, permissions=permissions
            )
            return await authorized_poll_topics(db, principal)

    assert await topics(set()) == [f"poll:{live['id']}:results"]
    await client.put(
        f"/api/v1/polls/{after_vote['id']}/vote",
        headers=member_headers,
        json={"option_ids": [after_vote["options"][0]["id"]]},
    )
    assert set(await topics(set())) == {
        f"poll:{live['id']}:results",
        f"poll:{after_vote['id']}:results",
    }
    assert await topics({"polls.results"}) == ["polls:management"]
    admin_headers = await login(client)
    for poll in (after_vote, live):
        await client.post(
            f"/api/v1/polls/{poll['id']}/close",
            headers=admin_headers,
            json={"reason": "Voting completed"},
        )
    assert await topics(set()) == []
    assert await topics({"polls.manage", "polls.results"}) == ["polls:management"]
