from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import MediaAsset, Role, User, UserRole
from utag_api.security import hash_password


async def login(client: AsyncClient, email: str, password: str) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


async def create_chat_member(session_factory, suffix: str) -> tuple[User, str]:  # type: ignore[no-untyped-def]
    password = f"StrongMemberPassword{suffix}23"
    async with session_factory() as session:
        member_role = await session.scalar(select(Role).where(Role.key == "member"))
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert member_role is not None
        assert administrator is not None
        member = User(
            id=new_id(),
            email=f"chat-member-{suffix}@example.edu.gh",
            password_hash=hash_password(password),
            status="active",
            email_verified=True,
            title="Dr.",
            other_name=f"Chat {suffix}",
            surname="Member",
        )
        session.add(member)
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=member.id,
                role_id=member_role.id,
                assigned_by_id=administrator.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()
        return member, password


async def test_chat_attachments_and_secure_group_invites(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    member_rows: list[tuple[User, str]] = []
    asset_id = new_id()
    async with session_factory() as session:
        member_role = await session.scalar(select(Role).where(Role.key == "member"))
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert member_role is not None
        assert administrator is not None
        for index in (1, 2):
            password = f"StrongMemberPassword{index}23"
            member = User(
                id=new_id(),
                email=f"member{index}@example.edu.gh",
                password_hash=hash_password(password),
                status="active",
                email_verified=True,
                title="Dr.",
                other_name=f"Member {index}",
                surname="Tester",
            )
            session.add(member)
            await session.flush()
            session.add(
                UserRole(
                    id=new_id(),
                    user_id=member.id,
                    role_id=member_role.id,
                    assigned_by_id=administrator.id,
                    assigned_at=datetime.now(UTC),
                )
            )
            member_rows.append((member, password))
        session.add(
            MediaAsset(
                id=asset_id,
                owner_id=administrator.id,
                storage_key=f"media/{asset_id}/agenda.pdf",
                original_filename="meeting-agenda.pdf",
                content_type="application/pdf",
                byte_size=512,
                sha256="a" * 64,
                status="ready",
                is_private=True,
                metadata_json={},
            )
        )
        await session.commit()

    admin_headers = await login(client, "admin@example.edu.gh", "StrongPassword123")
    group = await client.post(
        "/api/v1/chat/conversations",
        headers=admin_headers,
        json={
            "kind": "group",
            "title": "Council planning",
            "member_ids": [str(member_rows[0][0].id)],
        },
    )
    assert group.status_code == 201
    group_id = group.json()["id"]

    message = await client.post(
        f"/api/v1/chat/conversations/{group_id}/messages",
        headers=admin_headers,
        json={
            "text": "",
            "client_message_id": "chat-test-attachment-1",
            "attachment_media_ids": [str(asset_id)],
        },
    )
    assert message.status_code == 201
    assert message.json()["attachments"][0]["filename"] == "meeting-agenda.pdf"
    listed = await client.get(f"/api/v1/chat/conversations/{group_id}/messages")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["attachments"][0]["content_url"].endswith("/content")

    invite = await client.post(
        f"/api/v1/chat/conversations/{group_id}/invites",
        headers=admin_headers,
        json={"expires_in_hours": 24, "max_uses": 1},
    )
    assert invite.status_code == 201
    token = invite.json()["join_url"].split("invite=", 1)[1]

    joining_member, joining_password = member_rows[1]
    member_headers = await login(client, joining_member.email, joining_password)
    accepted = await client.post(
        f"/api/v1/chat/invites/{token}/accept",
        headers=member_headers,
    )
    assert accepted.status_code == 200
    assert accepted.json()["id"] == group_id
    conversations = await client.get("/api/v1/chat/conversations")
    joined_conversation = next(item for item in conversations.json() if item["id"] == group_id)
    assert joined_conversation["unread_count"] == 1

    joined_messages = await client.get(f"/api/v1/chat/conversations/{group_id}/messages")
    assert joined_messages.json()["items"][0]["read_by"] == 0
    marked_read = await client.post(
        f"/api/v1/chat/conversations/{group_id}/read",
        headers=member_headers,
    )
    assert marked_read.status_code == 200

    admin_headers = await login(client, "admin@example.edu.gh", "StrongPassword123")
    read_messages = await client.get(f"/api/v1/chat/conversations/{group_id}/messages")
    assert read_messages.json()["items"][0]["read_by"] == 1
    transferred = await client.patch(
        f"/api/v1/chat/conversations/{group_id}/owner",
        headers=admin_headers,
        json={"user_id": str(joining_member.id)},
    )
    assert transferred.status_code == 200

    members = await client.get(f"/api/v1/chat/conversations/{group_id}/members")
    roles = {item["user_id"]: item["role"] for item in members.json()}
    assert roles[str(joining_member.id)] == "owner"
    assert roles[group.json()["created_by_id"]] == "admin"


async def test_direct_chat_summaries_replies_edits_and_preferences(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    member, password = await create_chat_member(session_factory, "features")
    member_name = member.full_name

    admin_headers = await login(client, "admin@example.edu.gh", "StrongPassword123")
    created = await client.post(
        "/api/v1/chat/conversations",
        headers=admin_headers,
        json={"kind": "direct", "member_ids": [str(member.id)]},
    )
    assert created.status_code == 201
    conversation = created.json()
    assert conversation["display_title"] == member_name
    assert conversation["direct_member_id"] == str(member.id)
    assert conversation["last_message_preview"] is None

    first = await client.post(
        f"/api/v1/chat/conversations/{conversation['id']}/messages",
        headers=admin_headers,
        json={"text": "Please review the agenda", "client_message_id": "chat-feature-1"},
    )
    assert first.status_code == 201
    reply = await client.post(
        f"/api/v1/chat/conversations/{conversation['id']}/messages",
        headers=admin_headers,
        json={
            "text": "The revised agenda is ready",
            "client_message_id": "chat-feature-2",
            "reply_to_id": first.json()["id"],
        },
    )
    assert reply.status_code == 201
    assert reply.json()["reply_to"]["text"] == "Please review the agenda"

    edited = await client.patch(
        f"/api/v1/chat/messages/{reply.json()['id']}",
        headers=admin_headers,
        json={"text": "The final agenda is ready"},
    )
    assert edited.status_code == 200
    assert edited.json()["text"] == "The final agenda is ready"
    assert edited.json()["edited_at"] is not None

    muted = await client.patch(
        f"/api/v1/chat/conversations/{conversation['id']}/preferences",
        headers=admin_headers,
        json={"is_muted": True},
    )
    assert muted.status_code == 200
    assert muted.json()["is_muted"] is True
    assert muted.json()["last_message_preview"] == "The final agenda is ready"
    assert muted.json()["last_message_sender"] == "You"

    member_headers = await login(client, member.email, password)
    listed = await client.get("/api/v1/chat/conversations")
    direct = next(item for item in listed.json() if item["id"] == conversation["id"])
    assert direct["display_title"] != "Direct conversation"
    assert direct["last_message_preview"] == "The final agenda is ready"
    assert direct["last_message_sender"] != "You"
    assert direct["unread_count"] == 2

    messages = await client.get(f"/api/v1/chat/conversations/{conversation['id']}/messages")
    assert messages.status_code == 200
    assert messages.json()["items"][1]["reply_to"]["id"] == first.json()["id"]
    denied = await client.patch(
        f"/api/v1/chat/messages/{reply.json()['id']}",
        headers=member_headers,
        json={"text": "Changed by somebody else"},
    )
    assert denied.status_code == 403
    member_message = await client.post(
        f"/api/v1/chat/conversations/{conversation['id']}/messages",
        headers=member_headers,
        json={"text": "Member response", "client_message_id": "chat-feature-3"},
    )
    assert member_message.status_code == 201
    admin_headers = await login(client, "admin@example.edu.gh", "StrongPassword123")
    delete_denied = await client.delete(
        f"/api/v1/chat/messages/{member_message.json()['id']}",
        headers=admin_headers,
    )
    assert delete_denied.status_code == 403
