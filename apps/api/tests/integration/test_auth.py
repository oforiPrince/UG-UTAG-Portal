from datetime import UTC, datetime
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select

from utag_api.database import new_id
from utag_api.models import (
    AccountToken,
    AuditEvent,
    ExecutiveAppointment,
    MediaAsset,
    Role,
    User,
    UserPermissionGrant,
    UserRole,
)
from utag_api.security import hash_password


async def test_login_me_and_csrf_logout(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "ADMIN@example.edu.gh", "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["user"]["full_name"] == "Dr. Ama Mensah"
    assert "settings.manage" in payload["user"]["permissions"]
    assert client.cookies.get("utag_session")

    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.edu.gh"

    rejected = await client.post("/api/v1/auth/logout")
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "csrf_failed"

    logout = await client.post(
        "/api/v1/auth/logout", headers={"X-CSRF-Token": payload["csrf_token"]}
    )
    assert logout.status_code == 200


async def test_invalid_credentials_use_generic_message(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.edu.gh", "password": "WrongPassword123"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_profile_and_password_workflow(client: AsyncClient) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    csrf = login.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf}

    updated = await client.patch(
        "/api/v1/auth/profile",
        headers=headers,
        json={
            "title": "Prof.",
            "academic_rank": "Associate Professor",
            "phone_number": "+233 20 000 0000",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Prof. Ama Mensah"
    assert updated.json()["academic_rank"] == "Associate Professor"

    weak = await client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": "StrongPassword123", "new_password": "not-strong-enough"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"

    changed = await client.post(
        "/api/v1/auth/password",
        headers=headers,
        json={"current_password": "StrongPassword123", "new_password": "EvenStrongerPassword456"},
    )
    assert changed.status_code == 200
    assert (await client.get("/api/v1/auth/me")).json()["must_change_password"] is False


async def test_active_executive_can_update_own_public_profile(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert administrator is not None
        appointment_id = new_id()
        session.add(
            ExecutiveAppointment(
                id=appointment_id,
                user_id=administrator.id,
                position="President",
                biography_html="<p>Original biography.</p>",
                social_links={},
                is_active=True,
                is_public=True,
            )
        )
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    current = await client.get("/api/v1/auth/executive-profile")
    assert current.status_code == 200
    assert current.json()["position"] == "President"

    invalid_link = await client.patch(
        "/api/v1/auth/executive-profile",
        headers=headers,
        json={
            "biography_html": "<p>Biography.</p>",
            "social_links": {"linkedin": "javascript:alert('unsafe')"},
        },
    )
    assert invalid_link.status_code == 422

    updated = await client.patch(
        "/api/v1/auth/executive-profile",
        headers=headers,
        json={
            "biography_html": (
                "<p>Serving <strong>UG UTAG members</strong>.</p><script>alert('unsafe')</script>"
            ),
            "social_links": {
                "linkedin": "https://www.linkedin.com/in/ug-utag-test",
                "facebook": "",
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["biography_html"] == ("<p>Serving <strong>UG UTAG members</strong>.</p>")
    assert updated.json()["social_links"] == {
        "linkedin": "https://www.linkedin.com/in/ug-utag-test"
    }

    public = await client.get("/api/v1/public/leadership")
    assert public.status_code == 200
    profile = next(item for item in public.json() if item["id"] == str(appointment_id))
    assert profile["biography_html"] == updated.json()["biography_html"]

    async with session_factory() as session:
        event = await session.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.action == "executive.profile_updated",
                AuditEvent.resource_id == appointment_id,
            )
            .order_by(AuditEvent.created_at.desc())
        )
        assert event is not None


async def test_member_management_archives_without_deleting(
    client: AsyncClient, monkeypatch, session_factory
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    payload = login.json()
    headers = {"X-CSRF-Token": payload["csrf_token"]}

    created = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "new.member@example.edu.gh",
            "title": "Dr.",
            "other_name": "Kwame",
            "surname": "Asante",
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert created.status_code == 201
    member_id = created.json()["id"]

    profile_asset_id = new_id()
    invalid_profile_asset_id = new_id()
    async with session_factory() as session:
        administrator = await session.get(User, UUID(payload["user"]["id"]))
        assert administrator is not None
        session.add_all(
            [
                MediaAsset(
                    id=profile_asset_id,
                    owner_id=administrator.id,
                    storage_key=f"profile/{profile_asset_id}.png",
                    original_filename="executive-portrait.png",
                    content_type="image/png",
                    byte_size=128,
                    sha256="2" * 64,
                    status="ready",
                    is_private=False,
                    alt_text="Executive portrait",
                    metadata_json={},
                ),
                MediaAsset(
                    id=invalid_profile_asset_id,
                    owner_id=administrator.id,
                    storage_key=f"profile/{invalid_profile_asset_id}.pdf",
                    original_filename="not-a-portrait.pdf",
                    content_type="application/pdf",
                    byte_size=128,
                    sha256="3" * 64,
                    status="ready",
                    is_private=False,
                    alt_text=None,
                    metadata_json={},
                ),
            ],
        )
        await session.commit()

    updated = await client.patch(
        f"/api/v1/members/{member_id}",
        headers=headers,
        json={
            "academic_rank": "Senior Lecturer",
            "roles": ["member", "editor"],
            "profile_media_id": str(profile_asset_id),
        },
    )
    assert updated.status_code == 200
    assert updated.json()["roles"] == ["editor", "member"]
    assert updated.json()["profile_media_id"] == str(profile_asset_id)

    invalid_profile = await client.patch(
        f"/api/v1/members/{member_id}",
        headers=headers,
        json={"profile_media_id": str(invalid_profile_asset_id)},
    )
    assert invalid_profile.status_code == 422
    assert invalid_profile.json()["error"]["code"] == "profile_image_invalid"

    status_bypass = await client.patch(
        f"/api/v1/members/{member_id}",
        headers=headers,
        json={"status": "suspended"},
    )
    assert status_bypass.status_code == 409
    assert status_bypass.json()["error"]["code"] == "member_lifecycle_action_required"

    async with session_factory() as session:
        member = await session.get(User, UUID(member_id))
        assert member is not None
        member.email_verified = True
        await session.commit()

    monkeypatch.setattr("utag_api.worker.tasks.send_password_reset.delay", lambda *_: None)
    reset = await client.post(f"/api/v1/members/{member_id}/password-reset", headers=headers)
    assert reset.status_code == 200
    refreshed = await client.get(f"/api/v1/members/{member_id}")
    assert refreshed.json()["must_change_password"] is True
    async with session_factory() as session:
        reset_tokens = (
            await session.scalars(
                select(AccountToken).where(
                    AccountToken.user_id == UUID(member_id),
                    AccountToken.kind == "password_reset",
                    AccountToken.used_at.is_(None),
                )
            )
        ).all()
        assert len(reset_tokens) == 1

    deactivated = await client.post(
        f"/api/v1/members/{member_id}/deactivate",
        headers=headers,
        json={"reason": "Member is temporarily away from the association"},
    )
    assert deactivated.status_code == 200
    assert (await client.get(f"/api/v1/members/{member_id}")).json()["status"] == "suspended"
    access_while_suspended = await client.post(
        f"/api/v1/members/{member_id}/access-link", headers=headers
    )
    assert access_while_suspended.status_code == 409

    reactivated = await client.post(f"/api/v1/members/{member_id}/reactivate", headers=headers)
    assert reactivated.status_code == 200
    assert (await client.get(f"/api/v1/members/{member_id}")).json()["status"] == "active"

    exported = await client.get("/api/v1/members/exports/csv")
    assert exported.status_code == 200
    assert "new.member@example.edu.gh" in exported.text
    reference = await client.get("/api/v1/members/organization-reference.csv")
    assert reference.status_code == 200
    assert reference.text.startswith("college,school,department")

    archived = await client.delete(f"/api/v1/members/{member_id}", headers=headers)
    assert archived.status_code == 200
    retained = await client.get(f"/api/v1/members/{member_id}")
    assert retained.status_code == 200
    assert retained.json()["status"] == "archived"

    self_archive = await client.delete(f"/api/v1/members/{payload['user']['id']}", headers=headers)
    assert self_archive.status_code == 409
    assert self_archive.json()["error"]["code"] == "self_archive_denied"


async def test_member_and_executive_creation_accept_inline_profile_images(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    payload = login.json()
    headers = {"X-CSRF-Token": payload["csrf_token"]}
    public_image_id = new_id()
    private_image_id = new_id()
    async with session_factory() as session:
        administrator = await session.get(User, UUID(payload["user"]["id"]))
        assert administrator is not None
        session.add_all(
            [
                MediaAsset(
                    id=public_image_id,
                    owner_id=administrator.id,
                    storage_key=f"profile/{public_image_id}.png",
                    original_filename="new-executive.png",
                    content_type="image/png",
                    byte_size=256,
                    sha256="4" * 64,
                    status="ready",
                    is_private=False,
                    alt_text="New executive portrait",
                    metadata_json={},
                ),
                MediaAsset(
                    id=private_image_id,
                    owner_id=administrator.id,
                    storage_key=f"profile/{private_image_id}.png",
                    original_filename="private.png",
                    content_type="image/png",
                    byte_size=256,
                    sha256="5" * 64,
                    status="ready",
                    is_private=True,
                    alt_text="Private portrait",
                    metadata_json={},
                ),
            ]
        )
        await session.commit()

    media_status = await client.get(f"/api/v1/media/{public_image_id}")
    assert media_status.status_code == 200
    assert media_status.json()["status"] == "ready"

    created_member = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "inline.photo@example.edu.gh",
            "other_name": "Inline",
            "surname": "Photo",
            "profile_media_id": str(public_image_id),
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert created_member.status_code == 201
    assert created_member.json()["profile_media_id"] == str(public_image_id)

    missing_photo = await client.post(
        "/api/v1/executives",
        headers=headers,
        json={
            "user_id": created_member.json()["id"],
            "position": "Executive Member",
        },
    )
    assert missing_photo.status_code == 422

    created_executive = await client.post(
        "/api/v1/executives",
        headers=headers,
        json={
            "user_id": created_member.json()["id"],
            "profile_media_id": str(public_image_id),
            "position": "Executive Member",
        },
    )
    assert created_executive.status_code == 201
    assert created_executive.json()["profile_media_id"] == str(public_image_id)

    rejected_member = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "private.photo@example.edu.gh",
            "other_name": "Private",
            "surname": "Photo",
            "profile_media_id": str(private_image_id),
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert rejected_member.status_code == 422
    assert rejected_member.json()["error"]["code"] == "profile_image_invalid"


async def test_individual_permission_grants_merge_with_role_access(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    admin_headers = {"X-CSRF-Token": admin_login.json()["csrf_token"]}

    catalog = await client.get("/api/v1/members/permission-options")
    assert catalog.status_code == 200
    option_keys = {item["key"] for item in catalog.json()}
    assert {"content.edit", "media.manage"} <= option_keys
    assert "members.roles" not in option_keys
    assert "members.permissions" not in option_keys

    created = await client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={
            "email": "custom.access@example.edu.gh",
            "other_name": "Adwoa",
            "surname": "Owusu",
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert created.status_code == 201
    member_id = created.json()["id"]

    non_delegable = await client.put(
        f"/api/v1/members/{member_id}/permissions",
        headers=admin_headers,
        json={"permissions": ["members.roles"]},
    )
    assert non_delegable.status_code == 422
    assert non_delegable.json()["error"]["code"] == "permission_not_delegable"

    granted = await client.put(
        f"/api/v1/members/{member_id}/permissions",
        headers=admin_headers,
        json={"permissions": ["media.manage", "content.edit", "content.edit"]},
    )
    assert granted.status_code == 200
    grant_payload = granted.json()
    assert grant_payload["roles"] == ["member"]
    assert grant_payload["extra_permissions"] == ["content.edit", "media.manage"]
    assert {"chat.use", "dashboard.view", "documents.view"} <= set(
        grant_payload["role_permissions"]
    )
    assert set(grant_payload["effective_permissions"]) == set(grant_payload["role_permissions"]) | {
        "content.edit",
        "media.manage",
    }

    async with session_factory() as session:
        member = await session.get(User, UUID(member_id))
        assert member is not None
        member.password_hash = hash_password("CustomAccessPassword123")
        member.email_verified = True
        await session.commit()

    member_login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "custom.access@example.edu.gh",
            "password": "CustomAccessPassword123",
        },
    )
    assert member_login.status_code == 200
    assert {"content.edit", "media.manage"} <= set(member_login.json()["user"]["permissions"])
    member_headers = {"X-CSRF-Token": member_login.json()["csrf_token"]}
    denied = await client.put(
        f"/api/v1/members/{member_id}/permissions",
        headers=member_headers,
        json={"permissions": []},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"

    admin_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    cleared = await client.put(
        f"/api/v1/members/{member_id}/permissions",
        headers={"X-CSRF-Token": admin_login.json()["csrf_token"]},
        json={"permissions": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["extra_permissions"] == []
    assert cleared.json()["effective_permissions"] == cleared.json()["role_permissions"]

    async with session_factory() as session:
        remaining_grants = (
            await session.scalars(
                select(UserPermissionGrant).where(UserPermissionGrant.user_id == UUID(member_id))
            )
        ).all()
        audit_events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.resource_id == UUID(member_id),
                    AuditEvent.action == "member.permissions.updated",
                )
            )
        ).all()
        assert remaining_grants == []
        assert len(audit_events) == 2


async def test_secretary_cannot_assign_roles_or_manage_administrators(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        secretary_role = await session.scalar(select(Role).where(Role.key == "secretary"))
        administrator = await session.scalar(
            select(User).where(User.email == "admin@example.edu.gh")
        )
        assert secretary_role is not None
        assert administrator is not None
        secretary = User(
            id=new_id(),
            email="secretary@example.edu.gh",
            password_hash=hash_password("SecretaryPassword123"),
            status="active",
            email_verified=True,
            other_name="Akosua",
            surname="Boateng",
        )
        session.add(secretary)
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
        administrator_id = administrator.id
        await session.commit()

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "secretary@example.edu.gh",
            "password": "SecretaryPassword123",
        },
    )
    assert login.status_code == 200
    permissions = login.json()["user"]["permissions"]
    assert "members.create" in permissions
    assert "members.credentials" in permissions
    assert "members.roles" not in permissions
    assert "members.permissions" not in permissions
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}

    created = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "ordinary.member@example.edu.gh",
            "other_name": "Kojo",
            "surname": "Addo",
            "roles": ["member"],
            "send_invitation": False,
        },
    )
    assert created.status_code == 201

    escalated = await client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "unauthorized.admin@example.edu.gh",
            "other_name": "Bad",
            "surname": "Grant",
            "roles": ["administrator"],
            "send_invitation": False,
        },
    )
    assert escalated.status_code == 403
    assert escalated.json()["error"]["code"] == "role_assignment_denied"

    administrator_update = await client.patch(
        f"/api/v1/members/{administrator_id}",
        headers=headers,
        json={"phone_number": "+233200000001"},
    )
    assert administrator_update.status_code == 403
    assert administrator_update.json()["error"]["code"] == "administrator_management_denied"


async def test_member_import_previews_then_creates_invited_accounts(
    client: AsyncClient, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
    file_content = (
        b"email,staff_id,other_name,surname,academic_rank,roles\n"
        b"bulk.member@example.edu.gh,UG-BULK-1,Efua,Owusu,Lecturer,member;editor\n"
    )

    preview = await client.post(
        "/api/v1/members/import",
        headers=headers,
        data={"dry_run": "true"},
        files={"file": ("members.csv", file_content, "text/csv")},
    )
    assert preview.status_code == 200
    assert preview.json()["valid_rows"] == 1
    assert preview.json()["imported_rows"] == 0
    assert preview.json()["issues"] == []

    monkeypatch.setattr("utag_api.worker.tasks.send_invitation.delay", lambda *_: None)
    committed = await client.post(
        "/api/v1/members/import",
        headers=headers,
        data={"dry_run": "false"},
        files={"file": ("members.csv", file_content, "text/csv")},
    )
    assert committed.status_code == 200
    assert committed.json()["imported_rows"] == 1

    members = await client.get("/api/v1/members", params={"q": "bulk.member"})
    assert members.status_code == 200
    imported = members.json()["items"][0]
    assert imported["status"] == "invited"
    assert imported["roles"] == ["editor", "member"]


async def test_carousel_requires_public_media_and_archives_without_erasing(
    client: AsyncClient, session_factory
) -> None:  # type: ignore[no-untyped-def]
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    headers = {"X-CSRF-Token": login.json()["csrf_token"]}
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
                storage_key=f"carousel/{asset_id}.png",
                original_filename="homepage.png",
                content_type="image/png",
                byte_size=128,
                sha256="0" * 64,
                status="ready",
                is_private=False,
                alt_text="UG UTAG members",
                metadata_json={},
            )
        )
        await session.commit()

    media_search = await client.get(
        "/api/v1/media", params={"status": "ready", "q": "UTAG members"}
    )
    assert media_search.status_code == 200
    assert media_search.json()["items"][0]["id"] == str(asset_id)
    no_media_match = await client.get("/api/v1/media", params={"q": "not-present"})
    assert no_media_match.status_code == 200
    assert no_media_match.json()["items"] == []

    created = await client.post(
        "/api/v1/admin/carousel",
        headers=headers,
        json={
            "title": "Member solidarity",
            "description": (
                "<p>A <strong>public homepage</strong> highlight."
                "<script>alert('unsafe')</script></p>"
            ),
            "media_asset_id": str(asset_id),
            "order": 1,
            "is_published": True,
        },
    )
    assert created.status_code == 201
    slide_id = created.json()["id"]
    assert "<strong>public homepage</strong>" in created.json()["description"]
    assert "script" not in created.json()["description"]

    listing = await client.get("/api/v1/admin/carousel")
    assert listing.status_code == 200
    assert listing.json()[0]["title"] == "Member solidarity"

    public_settings = await client.get("/api/v1/public/settings")
    assert public_settings.status_code == 200
    assert public_settings.json()["site.carousel"]["slides"][0]["id"] == slide_id

    updated = await client.patch(
        f"/api/v1/admin/carousel/{slide_id}",
        headers=headers,
        json={
            "title": "Updated member solidarity",
            "description": '<p onclick="bad()">Updated message.</p>',
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated member solidarity"
    assert updated.json()["description"] == "<p>Updated message.</p>"

    archived = await client.delete(f"/api/v1/admin/carousel/{slide_id}", headers=headers)
    assert archived.status_code == 200
    assert (await client.get("/api/v1/public/settings")).json()["site.carousel"]["slides"] == []
    retained = (await client.get("/api/v1/admin/carousel")).json()[0]
    assert retained["archived"] is True
    assert retained["is_published"] is False
