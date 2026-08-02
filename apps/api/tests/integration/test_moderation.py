from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import func, select

from utag_api.database import new_id
from utag_api.models import AuditEvent, MediaAsset, Role, User, UserRole
from utag_api.routers.public import public_document_media_is_referenced
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
    document_asset_id = new_id()
    member_asset_id = new_id()
    gallery_asset_id = new_id()
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        session.add_all(
            [
                MediaAsset(
                    id=asset_id,
                    owner_id=administrator.id,
                    storage_key=f"moderation/{asset_id}.png",
                    original_filename=filename,
                    content_type="image/png",
                    byte_size=128,
                    sha256=checksum * 64,
                    status="ready",
                    is_private=is_private,
                    alt_text="UG UTAG public resource",
                    metadata_json={},
                )
                for asset_id, filename, checksum, is_private in (
                    (document_asset_id, "approved-public-file.png", "1", True),
                    (member_asset_id, "member-only-file.png", "2", True),
                    (gallery_asset_id, "approved-gallery-image.png", "3", False),
                )
            ]
        )
        await session.commit()

    invalid_internal_public = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Invalid public committee minutes",
            "category": "internal",
            "audiences": [{"type": "general_public", "value": "all"}],
            "status": "review",
            "media_asset_id": str(document_asset_id),
        },
    )
    assert invalid_internal_public.status_code == 422
    assert invalid_internal_public.json()["error"]["code"] == "invalid_document_audience"

    document = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Public policy brief",
            "category": "external",
            "description_html": "<p>Public policy resource.</p>",
            "audiences": [{"type": "general_public", "value": "all"}],
            "status": "review",
            "media_asset_id": str(document_asset_id),
        },
    )
    assert document.status_code == 201
    invalid_internal_update = await client.patch(
        f"/api/v1/documents/{document.json()['id']}",
        headers={**headers, "If-Match": f'"{document.json()["version"]}"'},
        json={"category": "internal"},
    )
    assert invalid_internal_update.status_code == 422
    assert invalid_internal_update.json()["error"]["code"] == "invalid_document_audience"
    member_document = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Member-only external circular",
            "category": "external",
            "audiences": [{"type": "role", "value": "member"}],
            "status": "review",
            "media_asset_id": str(member_asset_id),
        },
    )
    assert member_document.status_code == 201
    internal = await client.post(
        "/api/v1/documents",
        headers=headers,
        json={
            "title": "Internal committee minutes",
            "category": "internal",
            "status": "review",
            "media_asset_id": str(document_asset_id),
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
            "media_asset_ids": [str(gallery_asset_id)],
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
            "media_asset_ids": [str(gallery_asset_id)],
        },
    )
    assert stale_gallery.status_code == 412

    queue = (await client.get("/api/v1/moderation", params={"status": "review"})).json()
    assert {item["title"] for item in queue} == {
        "Public policy brief",
        "Member-only external circular",
        "Annual member forum",
    }

    for kind, item in (
        ("document", document.json()),
        ("document", member_document.json()),
        ("gallery", gallery.json()),
    ):
        approved = await client.post(
            f"/api/v1/moderation/{kind}/{item['id']}",
            headers=headers,
            json={"decision": "approve", "expected_version": item.get("version")},
        )
        assert approved.status_code == 200

    documents = (await client.get("/api/v1/public/documents")).json()
    galleries = (await client.get("/api/v1/public/galleries")).json()
    assert [item["title"] for item in documents] == ["Public policy brief"]
    assert documents[0]["files"][0]["media_asset_id"] == str(document_asset_id)
    assert documents[0]["files"][0]["content_url"] == (f"/api/v1/public/media/{document_asset_id}")
    public_document = await client.get(f"/api/v1/public/documents/{document.json()['id']}")
    assert public_document.status_code == 200
    assert public_document.json()["title"] == "Public policy brief"
    assert (
        await client.get(f"/api/v1/public/documents/{member_document.json()['id']}")
    ).status_code == 404
    assert [item["title"] for item in galleries] == ["Annual member forum"]
    assert galleries[0]["image_count"] == 1
    assert galleries[0]["description"] == (
        "<p>Approved <strong>photographs</strong> from the forum.</p>"
    )
    member_search = (await client.get("/api/v1/public/search", params={"q": "Member-only"})).json()
    assert all(item["title"] != "Member-only external circular" for item in member_search)
    assert (await client.get(f"/api/v1/public/media/{member_asset_id}")).status_code == 404

    async with session_factory() as session:
        assert await public_document_media_is_referenced(session, document_asset_id)
        assert not await public_document_media_is_referenced(session, member_asset_id)
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
            == 3
        )
