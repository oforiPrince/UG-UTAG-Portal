from datetime import date, datetime
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
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from utag_api.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrganizationUnitType(StrEnum):
    SCHOOL = "school"
    COLLEGE = "college"
    DEPARTMENT = "department"
    COMMITTEE = "committee"


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class OrganizationUnit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_units"
    __table_args__ = (
        UniqueConstraint("unit_type", "name", "parent_id", name="unit_identity"),
        UniqueConstraint("unit_type", "legacy_id", name="organization_legacy_identity"),
        Index("ix_organization_units_parent_type", "parent_id", "unit_type"),
        Index(
            "uq_organization_root_identity",
            "unit_type",
            "name",
            unique=True,
            postgresql_where=text("parent_id IS NULL"),
            sqlite_where=text("parent_id IS NULL"),
        ),
    )

    legacy_id: Mapped[int | None] = mapped_column(Integer)
    unit_type: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(180))
    slug: Mapped[str] = mapped_column(String(180), unique=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_name", "surname", "other_name"),
        Index("ix_users_status_created", "status", "created_at"),
    )

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    staff_id: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=UserStatus.INVITED, index=True)

    title: Mapped[str] = mapped_column(String(30), default="")
    other_name: Mapped[str] = mapped_column(String(120))
    surname: Mapped[str] = mapped_column(String(120))
    gender: Mapped[str | None] = mapped_column(String(30))
    academic_rank: Mapped[str | None] = mapped_column(String(120))
    phone_number: Mapped[str | None] = mapped_column(String(40))
    profile_media_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"), nullable=True
    )

    school_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    college_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organization_units.id", ondelete="SET NULL"), index=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.title, self.other_name, self.surname) if part)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Permission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class UserRole(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="user_role"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), index=True)
    assigned_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str | None] = mapped_column(String(180))


class UserPermissionGrant(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "user_permission_grants"
    __table_args__ = (UniqueConstraint("user_id", "permission_id", name="user_permission_grant"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), index=True
    )
    granted_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Session(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sessions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    ip_prefix: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AccountToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "account_tokens"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ExecutiveAppointment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "executive_appointments"
    __table_args__ = (Index("ix_executive_active_position", "position", "is_active"),)

    legacy_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    position: Mapped[str] = mapped_column(String(120), index=True)
    portfolio: Mapped[str | None] = mapped_column(String(180))
    summary: Mapped[str | None] = mapped_column(String(500))
    biography_html: Mapped[str | None] = mapped_column(Text)
    social_links: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    appointed_on: Mapped[date | None] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date)
    term_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_acting: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    show_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    show_phone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
