from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import AuditEvent, MediaAsset, Role, User, UserRole
from utag_api.security import hash_password


async def login_headers(client: AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    return {"X-CSRF-Token": login.json()["csrf_token"]}


async def test_news_review_preview_publish_and_withdraw(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    headers = await login_headers(client)
    created = await client.post(
        "/api/v1/content/articles",
        headers=headers,
        json={
            "title": "Council statement on academic work",
            "excerpt": "A reviewed statement for the public website.",
            "content_html": "<p>Approved association statement.</p>",
            "tags": ["statement"],
            "status": "review",
        },
    )
    assert created.status_code == 201
    article = created.json()

    queue = await client.get("/api/v1/moderation", params={"status": "review"})
    assert queue.status_code == 200
    assert [(item["kind"], item["title"]) for item in queue.json()] == [
        ("news", "Council statement on academic work")
    ]

    preview = await client.get(f"/api/v1/moderation/news/{article['id']}/preview")
    assert preview.status_code == 200
    assert preview.json()["body_html"] == "<p>Approved association statement.</p>"

    stale = await client.post(
        f"/api/v1/moderation/news/{article['id']}",
        headers=headers,
        json={"decision": "approve", "expected_version": article["version"] + 1},
    )
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "version_conflict"

    approved = await client.post(
        f"/api/v1/moderation/news/{article['id']}",
        headers=headers,
        json={"decision": "approve", "expected_version": article["version"]},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "published"

    public = await client.get(f"/api/v1/public/articles/{article['slug']}")
    assert public.status_code == 200

    missing_note = await client.post(
        f"/api/v1/moderation/news/{article['id']}",
        headers=headers,
        json={"decision": "withdraw", "expected_version": approved.json()["version"]},
    )
    assert missing_note.status_code == 422

    withdrawn = await client.post(
        f"/api/v1/moderation/news/{article['id']}",
        headers=headers,
        json={
            "decision": "withdraw",
            "note": "The statement has been superseded.",
            "expected_version": approved.json()["version"],
        },
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["status"] == "withdrawn"
    assert (await client.get(f"/api/v1/public/articles/{article['slug']}")).status_code == 404

    async with session_factory() as session:
        reason = await session.scalar(
            select(AuditEvent.reason)
            .where(AuditEvent.action == "news.moderation.withdraw")
            .order_by(AuditEvent.created_at.desc())
        )
        assert reason == "The statement has been superseded."


async def test_editor_can_submit_for_review_but_cannot_publish(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        editor_role = await session.scalar(select(Role).where(Role.key == "editor"))
        assert editor_role is not None
        editor = User(
            id=new_id(),
            email="editor@example.edu.gh",
            password_hash=hash_password("StrongEditorPassword123"),
            status="active",
            email_verified=True,
            title="Dr.",
            other_name="Akua",
            surname="Editor",
        )
        session.add(editor)
        await session.flush()
        session.add(
            UserRole(
                id=new_id(),
                user_id=editor.id,
                role_id=editor_role.id,
                assigned_by_id=editor.id,
                assigned_at=datetime.now(UTC),
            )
        )
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "editor@example.edu.gh", "password": "StrongEditorPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    review = await client.post(
        "/api/v1/content/articles",
        headers=headers,
        json={"title": "Editorial review draft", "status": "review"},
    )
    assert review.status_code == 201

    published = await client.post(
        "/api/v1/content/articles",
        headers=headers,
        json={"title": "Unauthorized direct publication", "status": "published"},
    )
    assert published.status_code == 403
    assert published.json()["error"]["code"] == "permission_denied"


async def test_only_moderated_external_documents_and_galleries_are_public(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    headers = await login_headers(client)
    asset_id = new_id()
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        session.add(
            MediaAsset(
                id=asset_id,
                owner_id=administrator.id,
                storage_key=f"moderation/{asset_id}.png",
                original_filename="approved-public-file.png",
                content_type="image/png",
                byte_size=128,
                sha256="1" * 64,
                status="ready",
                is_private=False,
                alt_text="UG UTAG public resource",
                metadata_json={},
            )
        )
        await session.commit()

    document = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Public policy brief",
            "category": "external",
            "description_html": "<p>Public policy resource.</p>",
            "status": "review",
            "media_asset_id": str(asset_id),
        },
    )
    assert document.status_code == 201
    internal = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Internal committee minutes",
            "category": "internal",
            "status": "review",
            "media_asset_id": str(asset_id),
        },
    )
    assert internal.status_code == 201
    gallery = await client.post(
        "/api/v1/galleries",
        headers=headers,
        json={
            "title": "Annual member forum",
            "description": (
                "<p>Approved <strong>photographs</strong> from the forum.</p>"
                "<script>alert('unsafe')</script>"
            ),
            "status": "review",
            "media_asset_ids": [str(asset_id)],
        },
    )
    assert gallery.status_code == 201
    assert gallery.json()["description"] == (
        "<p>Approved <strong>photographs</strong> from the forum.</p>"
    )

    stale_document = await client.patch(
        f"/api/v1/documents/{document.json()['id']}",
        headers=headers,
        json={"title": "Changed without a version"},
    )
    assert stale_document.status_code == 412
    stale_gallery = await client.put(
        f"/api/v1/galleries/{gallery.json()['id']}",
        headers=headers,
        json={
            "title": "Changed without a version",
            "status": "review",
            "media_asset_ids": [str(asset_id)],
        },
    )
    assert stale_gallery.status_code == 412

    queue = (await client.get("/api/v1/moderation", params={"status": "review"})).json()
    assert {item["title"] for item in queue} == {
        "Public policy brief",
        "Annual member forum",
    }

    for kind, item in (("document", document.json()), ("gallery", gallery.json())):
        approved = await client.post(
            f"/api/v1/moderation/{kind}/{item['id']}",
            headers=headers,
            json={"decision": "approve", "expected_version": item.get("version")},
        )
        assert approved.status_code == 200

    documents = (await client.get("/api/v1/public/documents")).json()
    galleries = (await client.get("/api/v1/public/galleries")).json()
    assert [item["title"] for item in documents] == ["Public policy brief"]
    assert [item["title"] for item in galleries] == ["Annual member forum"]
    assert galleries[0]["image_count"] == 1
    assert galleries[0]["description"] == (
        "<p>Approved <strong>photographs</strong> from the forum.</p>"
    )

    async with session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action.in_(
                        ["document.moderation.approve", "gallery.moderation.approve"]
                    )
                )
            )
            == 2
        )
