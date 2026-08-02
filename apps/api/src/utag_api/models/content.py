from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from utag_api.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PublicationStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    WITHDRAWN = "withdrawn"


class MediaStatus(StrEnum):
    QUARANTINED = "quarantined"
    SCANNING = "scanning"
    READY = "ready"
    REJECTED = "rejected"


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            name="fk_media_assets_owner_id_users",
            ondelete="SET NULL",
            use_alter=True,
        )
    )
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(150))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default=MediaStatus.QUARANTINED, index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(Text)
    credit: Mapped[str | None] = mapped_column(String(250))
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class MediaVariant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "media_variants"
    __table_args__ = (UniqueConstraint("asset_id", "variant", name="asset_variant"),)

    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    variant: Mapped[str] = mapped_column(String(80))
    storage_key: Mapped[str] = mapped_column(String(500), unique=True)
    content_type: Mapped[str] = mapped_column(String(150))
    byte_size: Mapped[int] = mapped_column(Integer)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))


class Article(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "articles"
    __table_args__ = (Index("ix_articles_status_published", "status", "published_at"),)

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    excerpt: Mapped[str] = mapped_column(Text, default="")
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    content_html: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    featured_media_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), default=PublicationStatus.DRAFT, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    citations: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ArticleAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "article_attachments"
    __table_args__ = (
        UniqueConstraint("article_id", "position", name="article_attachment_position"),
        UniqueConstraint("article_id", "media_asset_id", name="article_attachment_asset"),
    )

    article_id: Mapped[UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "announcements"
    __table_args__ = (Index("ix_announcements_status_published", "status", "published_at"),)

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(250))
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    content_html: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default=PublicationStatus.DRAFT, index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal")
    audiences: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class Event(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_status_start", "status", "start_date"),)

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    short_description: Mapped[str] = mapped_column(Text, default="")
    description_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    description_html: Mapped[str] = mapped_column(Text, default="")
    featured_media_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    start_date: Mapped[date] = mapped_column(Date, index=True)
    end_date: Mapped[date | None] = mapped_column(Date)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Accra")
    event_type: Mapped[str] = mapped_column(String(40), default="meeting")
    status: Mapped[str] = mapped_column(String(40), default="upcoming", index=True)
    publication_status: Mapped[str] = mapped_column(
        String(30), default=PublicationStatus.DRAFT, index=True
    )
    venue: Mapped[str | None] = mapped_column(String(250))
    address: Mapped[str | None] = mapped_column(String(500))
    location_url: Mapped[str | None] = mapped_column(String(1000))
    photos_url: Mapped[str | None] = mapped_column(String(1000))
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    online_platform: Mapped[str | None] = mapped_column(String(120))
    online_link_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    access_code_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    registration_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    registration_url: Mapped[str | None] = mapped_column(String(1000))
    registration_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    max_participants: Mapped[int | None] = mapped_column(Integer)
    expected_participants: Mapped[int | None] = mapped_column(Integer)
    cpd_credits: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    organizer: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    speakers: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    schedule: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class EventAttachment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "event_attachments"
    __table_args__ = (
        UniqueConstraint("event_id", "position", name="event_attachment_position"),
        UniqueConstraint("event_id", "media_asset_id", name="event_attachment_asset"),
    )

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    media_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)


class EventRegistration(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "event_registrations"
    __table_args__ = (UniqueConstraint("event_id", "user_id", name="event_user_registration"),)

    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="registered")
    attended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_status_category", "status", "category"),)

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    public_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(50), default="internal")
    sender: Mapped[str | None] = mapped_column(String(250))
    receiver: Mapped[str | None] = mapped_column(String(250))
    description_html: Mapped[str] = mapped_column(Text, default="")
    document_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default=PublicationStatus.DRAFT, index=True)
    audiences: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    retention_class: Mapped[str | None] = mapped_column(String(80))
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DocumentFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "document_files"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            "position",
            name="document_version_position",
        ),
        UniqueConstraint(
            "document_id",
            "version_number",
            "media_asset_id",
            name="document_version_asset",
        ),
    )

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer, default=0)
    change_note: Mapped[str | None] = mapped_column(Text)
    uploaded_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Gallery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "galleries"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    external_album_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default=PublicationStatus.DRAFT, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class GalleryItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gallery_items"
    __table_args__ = (UniqueConstraint("gallery_id", "position", name="gallery_position"),)

    gallery_id: Mapped[UUID] = mapped_column(
        ForeignKey("galleries.id", ondelete="CASCADE"), index=True
    )
    media_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    caption: Mapped[str | None] = mapped_column(Text)
    allow_download: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
