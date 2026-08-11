from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from utag_api.config import Settings, get_settings
from utag_api.database import new_id
from utag_api.models import (
    BackgroundJob,
    Gallery,
    GoogleDriveConnection,
    Session,
    User,
)
from utag_api.security import encrypt_text
from utag_api.services.google_drive import sign_oauth_state


async def _login(client):  # type: ignore[no-untyped-def]
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.edu.gh", "password": "StrongPassword123"},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _configure_google(monkeypatch) -> Settings:  # type: ignore[no-untyped-def]
    settings = Settings(
        _env_file=None,
        google_oauth_client_id="test-client-id",
        google_oauth_client_secret="test-client-secret-value",  # noqa: S106
        app_secret_key="session-secret-with-more-than-32-characters",  # noqa: S106
        field_encryption_key_version="v1",
        field_encryption_keys={"v1": "field-secret-with-more-than-32-characters"},
    )
    monkeypatch.setattr("utag_api.config.get_settings", lambda: settings)
    monkeypatch.setattr("utag_api.services.google_drive.get_settings", lambda: settings)
    monkeypatch.setattr("utag_api.routers.integrations_google_drive.get_settings", lambda: settings)
    get_settings.cache_clear()
    return settings


async def _logged_in_identity(session_factory):  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        row = (
            await session.execute(
                select(User, Session)
                .join(Session, Session.user_id == User.id)
                .where(User.email == "admin@example.edu.gh")
                .order_by(Session.created_at.desc())
                .limit(1)
            )
        ).one()
        return row


@pytest.mark.asyncio
async def test_google_drive_status_unconfigured(client) -> None:  # type: ignore[no-untyped-def]
    await _login(client)
    response = await client.get("/api/v1/integrations/google-drive/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert payload["connected"] is False


@pytest.mark.asyncio
async def test_google_drive_import_requires_configuration(client) -> None:  # type: ignore[no-untyped-def]
    headers = await _login(client)
    create = await client.post(
        "/api/v1/galleries",
        headers=headers,
        json={
            "title": "Drive import gallery",
            "status": "draft",
        },
    )
    assert create.status_code == 201
    gallery_id = create.json()["id"]
    response = await client.post(
        f"/api/v1/galleries/{gallery_id}/import/google-drive",
        headers=headers,
        json={
            "folder_url": (
                "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
            )
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "google_drive_not_configured"


@pytest.mark.asyncio
async def test_google_drive_callback_rejects_another_session(
    client, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    _configure_google(monkeypatch)
    await _login(client)
    user, _ = await _logged_in_identity(session_factory)
    state = sign_oauth_state(
        user_id=user.id,
        session_id=uuid4(),
        nonce="session-bound-state",
    )

    response = await client.get(
        "/api/v1/integrations/google-drive/callback",
        params={"code": "unused-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].endswith("/dashboard/galleries?drive=error")
    async with session_factory() as session:
        connection = await session.scalar(
            select(GoogleDriveConnection).where(GoogleDriveConnection.user_id == user.id)
        )
        assert connection is None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_drive_callback_stores_current_users_connection(
    client, session_factory, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    _configure_google(monkeypatch)
    await _login(client)
    user, portal_session = await _logged_in_identity(session_factory)
    state = sign_oauth_state(
        user_id=user.id,
        session_id=portal_session.id,
        nonce="session-bound-state",
    )

    async def exchange(_code: str) -> dict[str, object]:
        return {
            "access_token": "google-access-token",
            "refresh_token": "google-refresh-token",
            "expires_in": 3600,
            "scope": "openid email https://www.googleapis.com/auth/drive.readonly",
        }

    async def userinfo(_access_token: str) -> dict[str, object]:
        return {"sub": "google-sub-current-user", "email": "editor@gmail.com"}

    monkeypatch.setattr(
        "utag_api.routers.integrations_google_drive.drive.exchange_code_for_tokens",
        exchange,
    )
    monkeypatch.setattr(
        "utag_api.routers.integrations_google_drive.drive.fetch_userinfo",
        userinfo,
    )

    response = await client.get(
        "/api/v1/integrations/google-drive/callback",
        params={"code": "valid-code", "state": state},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"].endswith("/dashboard/galleries?drive=connected")
    async with session_factory() as session:
        connection = await session.scalar(
            select(GoogleDriveConnection).where(GoogleDriveConnection.user_id == user.id)
        )
        assert connection is not None
        assert connection.google_sub == "google-sub-current-user"
        assert connection.google_email == "editor@gmail.com"
        assert connection.access_token_encrypted != b"google-access-token"
        assert connection.refresh_token_encrypted != b"google-refresh-token"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_drive_import_requires_connection(client, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _configure_google(monkeypatch)
    headers = await _login(client)
    create = await client.post(
        "/api/v1/galleries",
        headers=headers,
        json={
            "title": "Needs Drive connection",
            "status": "draft",
            "external_album_url": (
                "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
            ),
        },
    )
    assert create.status_code == 201
    gallery_id = create.json()["id"]

    status = await client.get("/api/v1/integrations/google-drive/status")
    assert status.status_code == 200
    assert status.json()["configured"] is True
    assert status.json()["connected"] is False

    response = await client.post(
        f"/api/v1/galleries/{gallery_id}/import/google-drive",
        headers=headers,
        json={
            "folder_url": (
                "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
            )
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "google_drive_not_connected"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_google_drive_import_queues_job(client, session_factory, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _configure_google(monkeypatch)
    headers = await _login(client)

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "admin@example.edu.gh"))
        assert user is not None
        access = encrypt_text("access-token")
        refresh = encrypt_text("refresh-token")
        assert access and refresh
        session.add(
            GoogleDriveConnection(
                id=new_id(),
                user_id=user.id,
                google_sub="google-sub-1",
                google_email="admin@gmail.com",
                access_token_encrypted=access,
                refresh_token_encrypted=refresh,
                token_expires_at=datetime.now(UTC),
                scopes="https://www.googleapis.com/auth/drive.readonly",
            )
        )
        await session.commit()

    create = await client.post(
        "/api/v1/galleries",
        headers=headers,
        json={
            "title": "Import queue gallery",
            "status": "draft",
            "external_album_url": (
                "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
            ),
        },
    )
    assert create.status_code == 201
    gallery_id = create.json()["id"]

    response = await client.post(
        f"/api/v1/galleries/{gallery_id}/import/google-drive",
        headers=headers,
        json={
            "folder_url": (
                "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
            )
        },
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    assert job_id

    job_response = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_response.status_code == 200
    assert job_response.json()["kind"] == "gallery.google_drive_import"
    assert job_response.json()["status"] == "queued"

    async with session_factory() as session:
        job = await session.get(BackgroundJob, UUID(job_id))
        assert job is not None
        assert job.input_json["folder_id"] == "12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
        gallery = await session.get(Gallery, UUID(gallery_id))
        assert gallery is not None

    get_settings.cache_clear()
