from datetime import UTC, date, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from utag_api.schemas.domain import (
    DocumentCreate,
    EventCreate,
    MessageCreateRequest,
    NotificationCreate,
    NotificationView,
)


def test_event_rejects_end_before_start() -> None:
    with pytest.raises(ValidationError):
        EventCreate(title="Invalid event", start_date=date(2026, 8, 10), end_date=date(2026, 8, 9))


def test_event_rejects_late_registration_deadline() -> None:
    with pytest.raises(ValidationError):
        EventCreate(
            title="Invalid registration",
            start_date=date(2026, 8, 10),
            registration_deadline=datetime(2026, 8, 11),
        )


def test_event_accepts_external_registration_link() -> None:
    event = EventCreate(
        title="Congregation ceremony",
        start_date=date(2026, 8, 10),
        registration_url="https://forms.ug.edu.gh/utag-registration",
    )
    assert str(event.registration_url) == "https://forms.ug.edu.gh/utag-registration"


def test_event_rejects_invalid_registration_link() -> None:
    with pytest.raises(ValidationError):
        EventCreate(
            title="Broken registration link",
            start_date=date(2026, 8, 10),
            registration_url="not-a-link",
        )


def test_gallery_requires_images_or_external_album() -> None:
    from utag_api.schemas.domain import GalleryCreate

    with pytest.raises(ValidationError):
        GalleryCreate(title="Empty gallery")


def test_gallery_accepts_external_album_without_images() -> None:
    from utag_api.schemas.domain import GalleryCreate

    gallery = GalleryCreate(
        title="Drive album",
        external_album_url="https://drive.google.com/drive/folders/example",
    )
    assert gallery.media_asset_ids == []
    assert str(gallery.external_album_url).startswith("https://drive.google.com/")


def test_gallery_rejects_blocked_download_ids_outside_selection() -> None:
    from utag_api.schemas.domain import GalleryCreate

    selected = UUID("35a55a4e-9482-4ce9-9f66-dfc328f97aec")
    other = UUID("45a55a4e-9482-4ce9-9f66-dfc328f97aed")
    with pytest.raises(ValidationError):
        GalleryCreate(
            title="Mixed gallery",
            media_asset_ids=[selected],
            blocked_download_media_ids=[other],
        )


def test_gallery_accepts_per_image_download_blocks() -> None:
    from utag_api.schemas.domain import GalleryCreate

    selected = UUID("35a55a4e-9482-4ce9-9f66-dfc328f97aec")
    gallery = GalleryCreate(
        title="Protected gallery",
        media_asset_ids=[selected],
        blocked_download_media_ids=[selected],
    )
    assert gallery.blocked_download_media_ids == [selected]


def test_document_requires_at_least_one_file() -> None:
    with pytest.raises(ValidationError):
        DocumentCreate(title="Document without a file")


def test_chat_message_accepts_an_attachment_without_text() -> None:
    asset_id = "35a55a4e-9482-4ce9-9f66-dfc328f97aec"
    message = MessageCreateRequest(
        client_message_id="client-message-1",
        attachment_media_ids=[UUID(asset_id)],
    )
    assert str(message.attachment_media_ids[0]) == asset_id


def test_notification_view_sanitizes_legacy_stored_html() -> None:
    notification = NotificationView(
        id=UUID("35a55a4e-9482-4ce9-9f66-dfc328f97aec"),
        category="general",
        priority="normal",
        title="Member update",
        body="<p>Safe <strong>formatting</strong>.</p><script>alert('unsafe')</script>",
        resource_type=None,
        resource_id=None,
        deep_link=None,
        read_at=None,
        created_at=datetime.now(UTC),
    )

    assert notification.body == "<p>Safe <strong>formatting</strong>.</p>"


@pytest.mark.parametrize(
    "deep_link",
    ["https://example.org/phishing", "//example.org/phishing", r"/\\example.org"],
)
def test_notification_rejects_external_deep_links(deep_link: str) -> None:
    with pytest.raises(ValidationError):
        NotificationCreate(
            user_ids=[UUID("35a55a4e-9482-4ce9-9f66-dfc328f97aec")],
            title="Member update",
            deep_link=deep_link,
        )


def test_notification_accepts_internal_deep_link() -> None:
    notification = NotificationCreate(
        user_ids=[UUID("35a55a4e-9482-4ce9-9f66-dfc328f97aec")],
        title="Member update",
        deep_link=" /dashboard/events?tab=upcoming ",
    )

    assert notification.deep_link == "/dashboard/events?tab=upcoming"
