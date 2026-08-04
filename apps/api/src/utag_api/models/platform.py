from datetime import date, datetime
from decimal import Decimal
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
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column

from utag_api.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_resource_created", "resource_type", "resource_id", "created_at"),
    )

    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(150), index=True)
    resource_type: Mapped[str] = mapped_column(String(100), index=True)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    outcome: Mapped[str] = mapped_column(String(30), default="success")
    request_id: Mapped[str | None] = mapped_column(String(80), index=True)
    reason: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OutboxEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(160), index=True)
    topic: Mapped[str] = mapped_column(String(250), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(100))
    aggregate_id: Mapped[UUID] = mapped_column(Uuid)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class IdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("user_id", "key", name="user_idempotency_key"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(150))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, object] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class BackgroundJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "background_jobs"

    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    kind: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    input_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)


class GoogleDriveConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-user Google OAuth tokens for Drive folder imports."""

    __tablename__ = "google_drive_connections"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    google_sub: Mapped[str] = mapped_column(String(128), index=True)
    google_email: Mapped[str] = mapped_column(String(255), default="")
    access_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[str] = mapped_column(Text, default="")


class FeatureFlag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_flags"

    key: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rules: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)


class SiteSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(150), unique=True)
    value: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MigrationDisposition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "migration_dispositions"
    __table_args__ = (
        UniqueConstraint("source_table", "source_pk", name="migration_source_record"),
    )

    batch_id: Mapped[str] = mapped_column(String(100), index=True)
    source_table: Mapped[str] = mapped_column(String(180), index=True)
    source_pk: Mapped[str] = mapped_column(String(180))
    source_hash: Mapped[str] = mapped_column(String(64))
    disposition: Mapped[str] = mapped_column(String(30), index=True)
    target_type: Mapped[str | None] = mapped_column(String(100))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    reason: Mapped[str | None] = mapped_column(Text)
    archive_key: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LegacyArchiveRecord(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "legacy_archive_records"
    __table_args__ = (
        UniqueConstraint("source_table", "source_pk", name="legacy_archive_source_record"),
    )

    batch_id: Mapped[str] = mapped_column(String(100), index=True)
    source_table: Mapped[str] = mapped_column(String(180), index=True)
    source_pk: Mapped[str] = mapped_column(String(180))
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    classification: Mapped[str] = mapped_column(String(30), default="captured", index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AdSlot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_slots"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(180))
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdAdvertiser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External commercial client buying ad inventory (not required to be a member)."""

    __tablename__ = "ad_advertisers"

    organization_name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(180), default="")
    email: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(40), default="")
    website: Mapped[str | None] = mapped_column(String(1000))
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    member_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )


class AdPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_plans"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    slot_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_slots.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    duration_days: Mapped[int] = mapped_column(Integer, default=30)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AdCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_campaigns"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    slot_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_slots.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    media_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL")
    )
    target_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    is_house_ad: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)


class AdOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_orders"
    __table_args__ = (
        Index(
            "uq_ad_orders_campaign_id",
            "campaign_id",
            unique=True,
            postgresql_where=sa_text("campaign_id IS NOT NULL"),
            sqlite_where=sa_text("campaign_id IS NOT NULL"),
        ),
    )

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    advertiser_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_advertisers.id", ondelete="RESTRICT"), index=True
    )
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("ad_plans.id", ondelete="RESTRICT"))
    campaign_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("ad_campaigns.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    payment_status: Mapped[str] = mapped_column(String(30), default="unpaid")
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")
