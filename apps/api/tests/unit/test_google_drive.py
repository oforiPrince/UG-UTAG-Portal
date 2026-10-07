import asyncio
import threading
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest

from utag_api.errors import ApiError
from utag_api.services import google_drive as drive
from utag_api.services.google_drive import (
    download_file,
    parse_drive_folder_id,
    sign_oauth_state,
    verify_oauth_state,
)
from utag_api.worker import tasks as worker_tasks


def test_parse_drive_folder_id_from_url() -> None:
    folder_id = parse_drive_folder_id(
        "https://drive.google.com/drive/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S?usp=drive_link"
    )
    assert folder_id == "12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"


def test_parse_drive_folder_id_raw() -> None:
    assert (
        parse_drive_folder_id("12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S")
        == "12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S"
    )


def test_parse_drive_folder_id_rejects_non_drive_host() -> None:
    with pytest.raises(ApiError) as exc:
        parse_drive_folder_id("https://example.com/folders/12OsdYhfgIBs5XXbheCEP5S44A3Fp9a-S")
    assert exc.value.code == "invalid_drive_folder_url"


def test_oauth_state_round_trip() -> None:
    user_id = uuid4()
    session_id = uuid4()
    state = sign_oauth_state(
        user_id=user_id,
        session_id=session_id,
        nonce="nonce-value",
    )
    verified = verify_oauth_state(state)
    assert verified.user_id == user_id
    assert verified.session_id == session_id


def test_oauth_state_rejects_tampering() -> None:
    user_id = uuid4()
    state = sign_oauth_state(
        user_id=user_id,
        session_id=uuid4(),
        nonce="nonce-value",
    )
    body, signature = state.split(".", 1)
    with pytest.raises(ApiError) as exc:
        verify_oauth_state(f"{body}.{signature[:-1]}x")
    assert exc.value.code == "invalid_oauth_state"


def test_oauth_state_rejects_expired() -> None:
    user_id = uuid4()
    past = datetime.now(UTC) - timedelta(hours=1)
    state = sign_oauth_state(
        user_id=user_id,
        session_id=uuid4(),
        nonce="nonce-value",
        now=past,
    )
    with pytest.raises(ApiError) as exc:
        verify_oauth_state(state)
    assert exc.value.code == "oauth_state_expired"


@pytest.mark.asyncio
async def test_download_file_enforces_actual_byte_limit(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"12345", request=request)
    )

    def client_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        return original_client(transport=transport, timeout=kwargs.get("timeout"))

    monkeypatch.setattr(drive.httpx, "AsyncClient", client_factory)
    with pytest.raises(ApiError) as exc:
        await download_file("access-token", "drive-file-id", max_bytes=4)
    assert exc.value.code == "google_drive_file_too_large"


@pytest.mark.asyncio
async def test_import_media_processing_runs_outside_active_event_loop(
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    calling_thread = threading.get_ident()
    observed: dict[str, object] = {}

    def fake_process_media(asset_id: str) -> None:
        observed["asset_id"] = asset_id
        observed["thread_id"] = threading.get_ident()
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()

    monkeypatch.setattr(worker_tasks, "process_media", fake_process_media)
    asset_id = uuid4()

    await worker_tasks._process_media_for_import(asset_id)

    assert observed["asset_id"] == str(asset_id)
    assert observed["thread_id"] != calling_thread


@pytest.mark.asyncio
async def test_import_refreshes_only_processed_media() -> None:
    observed: dict[str, object] = {}

    class FakeSession:
        async def refresh(
            self, instance: object, attribute_names: list[str] | None = None
        ) -> None:
            observed["instance"] = instance
            observed["attribute_names"] = attribute_names
            instance.status = "ready"  # type: ignore[attr-defined]

    asset = cast(Any, type("Asset", (), {"status": "scanning"})())
    refreshed = await worker_tasks._refresh_processed_media(
        cast(Any, FakeSession()), asset
    )

    assert refreshed is asset
    assert observed == {
        "instance": asset,
        "attribute_names": ["status", "storage_key"],
    }
