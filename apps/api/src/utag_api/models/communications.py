from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from utag_api.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "read_at", "created_at"),
    )

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(80), default="general")
    priority: Mapped[str] = mapped_column(String(30), default="normal")
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    deep_link: Mapped[str | None] = mapped_column(String(1000))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    kind: Mapped[str] = mapped_column(String(30), default="direct", index=True)
    direct_key: Mapped[str | None] = mapped_column(String(80), unique=True, index=True)
    title: Mapped[str | None] = mapped_column(String(180))
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    encryption_key_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary)
    encryption_key_version: Mapped[str | None] = mapped_column(String(80))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ConversationMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_members"
    __table_args__ = (UniqueConstraint("conversation_id", "user_id", name="conversation_user"),)

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(30), default="member")
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversation_invites"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    use_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("sender_id", "client_message_id", name="sender_client_message"),
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
    )

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    client_message_id: Mapped[str] = mapped_column(String(100))
    reply_to_id: Mapped[UUID | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"))
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[str] = mapped_column(String(80), default="v1")
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MessageAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_attachments"

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(150))
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String(500))
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    encryption_key_version: Mapped[str] = mapped_column(String(80), default="legacy-fernet")
    status: Mapped[str] = mapped_column(String(30), default="ready", index=True)
