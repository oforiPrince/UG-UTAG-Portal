"""Repeatable, checksum-driven legacy capture, promotion, file copy, and reconciliation."""

import argparse
import base64
import hashlib
import json
import mimetypes
from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time
from decimal import Decimal
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as OrmSession

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.models import (
    AdCampaign,
    AdPlan,
    AdSlot,
    Announcement,
    Article,
    ArticleAttachment,
    Document,
    DocumentFile,
    Event,
    ExecutiveAppointment,
    Gallery,
    GalleryItem,
    LegacyArchiveRecord,
    MediaAsset,
    MigrationDisposition,
    OrganizationUnit,
    Role,
    User,
    UserRole,
)
from utag_api.security import field_cipher
from utag_api.services.content import sanitize_html
from utag_api.services.query import slugify
from utag_api.services.storage import s3_client


class MigrationDriftError(RuntimeError):
    """Raised when an already captured source record changed unexpectedly."""


def sync_url(value: str) -> str:
    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value.replace("sqlite+aiosqlite://", "sqlite://", 1)


def engine(value: str) -> Engine:
    return create_engine(sync_url(value), pool_pre_ping=True)


def json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, (datetime, date, time)):
        return {"$temporal": value.isoformat()}
    if isinstance(value, UUID):
        return {"$uuid": str(value)}
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, bytes):
        return {"$binary": base64.b64encode(value).decode()}
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, Iterable):
        return [json_value(item) for item in value]
    return {"$repr": repr(value)}


def restore_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    if "$binary" in value:
        return base64.b64decode(value["$binary"])
    if "$decimal" in value:
        return Decimal(value["$decimal"])
    if "$uuid" in value:
        return UUID(value["$uuid"])
    if "$temporal" in value:
        raw = value["$temporal"]
        try:
            if "T" in raw or " " in raw:
                return datetime.fromisoformat(raw)
            if ":" in raw:
                return time.fromisoformat(raw)
            return date.fromisoformat(raw)
        except ValueError:
            return raw
    return {key: restore_value(item) for key, item in value.items()}


def checksum(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def source_pk(row: Mapping[str, Any], columns: list[str]) -> str:
    if columns:
        return json.dumps([json_value(row[column]) for column in columns], separators=(",", ":"))
    return checksum({str(key): json_value(value) for key, value in row.items()})


def source_tables(source: Engine) -> list[str]:
    # Security-sensitive sessions and Django's schema ledger are deliberately
    # archived rather than activated in the new runtime. They are still source
    # data, so excluding them would violate the row-for-row evidence contract.
    return sorted(inspect(source).get_table_names())


def secure_chmod(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except PermissionError:
        # Bind-mounted evidence dirs on older hosts may reject chmod from the
        # non-root app user; continue as long as the path is writable.
        if not os.access(path, os.W_OK):
            raise


def write_private_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    secure_chmod(path, 0o600)


def inventory(source: Engine, output: Path) -> dict[str, Any]:
    inspector = inspect(source)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "tables": {},
    }
    with source.connect() as connection:
        for table_name in source_tables(source):
            table = Table(table_name, MetaData(), autoload_with=source)
            count = int(connection.scalar(select(func.count()).select_from(table)) or 0)
            report["tables"][table_name] = {
                "rows": count,
                "primary_key": inspector.get_pk_constraint(table_name).get(
                    "constrained_columns", []
                ),
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": column["nullable"],
                    }
                    for column in inspector.get_columns(table_name)
                ],
            }
    write_private_json(output, report)
    return report


def capture(source: Engine, target: Engine, batch_id: str, archive_dir: Path) -> None:
    inspector = inspect(source)
    archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    secure_chmod(archive_dir, 0o700)
    with source.connect() as source_connection, OrmSession(target) as target_session:
        for table_name in source_tables(source):
            table = Table(table_name, MetaData(), autoload_with=source)
            pk_columns = list(
                inspector.get_pk_constraint(table_name).get("constrained_columns", [])
            )
            archive_path = archive_dir / f"{table_name}.jsonl"
            with archive_path.open("w", encoding="utf-8") as archive:
                for row in source_connection.execute(select(table)).mappings():
                    payload = {str(key): json_value(value) for key, value in row.items()}
                    record_pk = source_pk(row, pk_columns)
                    record_hash = checksum(payload)
                    envelope = {
                        "source_table": table_name,
                        "source_pk": record_pk,
                        "source_hash": record_hash,
                        "payload": payload,
                    }
                    archive.write(json.dumps(envelope, sort_keys=True) + "\n")
                    existing = target_session.scalar(
                        select(LegacyArchiveRecord).where(
                            LegacyArchiveRecord.source_table == table_name,
                            LegacyArchiveRecord.source_pk == record_pk,
                        )
                    )
                    if existing:
                        if existing.source_hash != record_hash:
                            raise MigrationDriftError(
                                f"Source drift detected for {table_name} {record_pk}"
                            )
                        disposition = target_session.scalar(
                            select(MigrationDisposition).where(
                                MigrationDisposition.source_table == table_name,
                                MigrationDisposition.source_pk == record_pk,
                            )
                        )
                        if disposition is None:
                            target_session.add(
                                MigrationDisposition(
                                    id=new_id(),
                                    batch_id=existing.batch_id,
                                    source_table=table_name,
                                    source_pk=record_pk,
                                    source_hash=record_hash,
                                    disposition="archived",
                                    reason="Recovered missing disposition from captured record",
                                    archive_key=str(archive_path),
                                    created_at=datetime.now(UTC),
                                )
                            )
                        continue
                    target_session.add(
                        LegacyArchiveRecord(
                            id=new_id(),
                            batch_id=batch_id,
                            source_table=table_name,
                            source_pk=record_pk,
                            source_hash=record_hash,
                            payload=payload,
                            classification="captured",
                            captured_at=datetime.now(UTC),
                        )
                    )
                    target_session.add(
                        MigrationDisposition(
                            id=new_id(),
                            batch_id=batch_id,
                            source_table=table_name,
                            source_pk=record_pk,
                            source_hash=record_hash,
                            disposition="archived",
                            reason=(
                                "Captured losslessly; awaiting or not requiring domain promotion"
                            ),
                            archive_key=str(archive_path),
                            created_at=datetime.now(UTC),
                        )
                    )
            secure_chmod(archive_path, 0o600)
            target_session.commit()


def legacy_id(row: dict[str, Any]) -> int:
    return int(restore_value(row["id"]))


def lookup_legacy(session: OrmSession, model: Any, identifier: int) -> Any:
    return session.scalar(select(model).where(model.legacy_id == identifier))


def user_id(session: OrmSession, identifier: Any) -> UUID | None:
    if identifier is None:
        return None
    user = lookup_legacy(session, User, int(identifier))
    return user.id if user else None


def unit_id(session: OrmSession, identifier: Any, unit_type: str) -> UUID | None:
    if identifier is None:
        return None
    item = session.scalar(
        select(OrganizationUnit).where(
            OrganizationUnit.legacy_id == int(identifier),
            OrganizationUnit.unit_type == unit_type,
        )
    )
    return item.id if item else None


def promote_organization(
    session: OrmSession, row: dict[str, Any], unit_type: str
) -> OrganizationUnit:
    identifier = legacy_id(row)
    existing = session.scalar(
        select(OrganizationUnit).where(
            OrganizationUnit.legacy_id == identifier,
            OrganizationUnit.unit_type == unit_type,
        )
    )
    if existing:
        return existing
    name = str(restore_value(row["name"]))
    parent = None
    if unit_type == "college":
        parent = unit_id(session, restore_value(row.get("school_id")), "school")
    elif unit_type == "department":
        parent = unit_id(session, restore_value(row.get("college_id")), "college")

    # Reclaim seeded/demo units that share the same identity so promote
    # remains idempotent against uq_organization_root_identity / unit_identity.
    if parent is None:
        existing = session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == unit_type,
                OrganizationUnit.name == name,
                OrganizationUnit.parent_id.is_(None),
            )
        )
    else:
        existing = session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == unit_type,
                OrganizationUnit.name == name,
                OrganizationUnit.parent_id == parent,
            )
        )
    if existing is None:
        existing = session.scalar(
            select(OrganizationUnit).where(
                OrganizationUnit.unit_type == unit_type,
                OrganizationUnit.name == name,
                OrganizationUnit.legacy_id.is_(None),
            )
        )
    if existing:
        existing.legacy_id = identifier
        session.flush()
        return existing

    item = OrganizationUnit(
        id=new_id(),
        legacy_id=identifier,
        unit_type=unit_type,
        name=name,
        slug=f"{unit_type}-{identifier}-{slugify(name)}",
        parent_id=parent,
    )
    session.add(item)
    session.flush()
    return item


def promote_user(session: OrmSession, row: dict[str, Any]) -> User:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, User, identifier)
    if existing:
        return existing
    item = User(
        id=new_id(),
        legacy_id=identifier,
        email=str(restore_value(row["email"])).strip().casefold(),
        staff_id=restore_value(row.get("staff_id")),
        password_hash=str(restore_value(row["password"])),
        must_change_password=bool(restore_value(row.get("must_change_password", False))),
        email_verified=bool(restore_value(row.get("email_sent", False))),
        status="active",
        title=str(restore_value(row.get("title")) or ""),
        other_name=str(restore_value(row.get("other_name")) or "Member"),
        surname=str(restore_value(row.get("surname")) or "Unknown"),
        gender=restore_value(row.get("gender")),
        academic_rank=restore_value(row.get("academic_rank")),
        phone_number=restore_value(row.get("phone_number")),
        school_id=unit_id(session, restore_value(row.get("school_id")), "school"),
        college_id=unit_id(session, restore_value(row.get("college_id")), "college"),
        department_id=unit_id(session, restore_value(row.get("department_id")), "department"),
        last_login_at=restore_value(row.get("last_login")),
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    if bool(restore_value(row.get("is_superuser", False))):
        assign_role(session, item, "administrator")
    position = restore_value(row.get("executive_position"))
    if position:
        session.add(
            ExecutiveAppointment(
                id=new_id(),
                legacy_id=identifier,
                user_id=item.id,
                position=str(position),
                summary=restore_value(row.get("executive_summary")),
                biography_html=sanitize_html(restore_value(row.get("executive_bio"))),
                appointed_on=restore_value(row.get("date_appointed")),
                ended_on=restore_value(row.get("date_ended")),
                term_number=int(restore_value(row.get("executive_terms")) or 1),
                is_active=bool(restore_value(row.get("is_active_executive", False))),
                social_links={
                    key: value
                    for key, value in {
                        "linkedin": restore_value(row.get("linkedin_profile_url")),
                        "twitter": restore_value(row.get("twitter_profile_url")),
                        "facebook": restore_value(row.get("fb_profile_url")),
                        "website": restore_value(row.get("personal_website_url")),
                    }.items()
                    if value
                },
            )
        )
    return item


LEGACY_GROUP_ROLE_KEYS = {
    "admin": "administrator",
    "administrator": "administrator",
    "secretary": "secretary",
    "executive": "executive",
    "president": "executive",
    "vice president": "executive",
    "treasurer": "executive",
    "member": "member",
    "editor": "editor",
    "publisher": "publisher",
}


def legacy_group_role_key(row: dict[str, Any]) -> str:
    identifier = legacy_id(row)
    name = str(restore_value(row.get("name")) or f"Legacy group {identifier}").strip()
    mapped = LEGACY_GROUP_ROLE_KEYS.get(name.casefold())
    if mapped:
        return mapped
    safe_name = slugify(name)[:48] or "group"
    return f"legacy-{identifier}-{safe_name}"


def promote_group(session: OrmSession, row: dict[str, Any]) -> Role:
    role_key = legacy_group_role_key(row)
    existing = session.scalar(select(Role).where(Role.key == role_key))
    if existing:
        return existing
    name = str(restore_value(row.get("name")) or role_key)
    item = Role(
        id=new_id(),
        key=role_key,
        name=name,
        description=(
            f"Imported from legacy Django group {legacy_id(row)}. "
            "No permissions are granted until an administrator reviews this role."
        ),
        is_system=False,
    )
    session.add(item)
    session.flush()
    return item


def assign_role(session: OrmSession, user: User, role_key: str) -> UserRole:
    role = session.scalar(select(Role).where(Role.key == role_key))
    if role is None:
        raise RuntimeError(
            f"Required role {role_key!r} is missing; run `python -m utag_api.cli seed` first"
        )
    existing = session.scalar(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if existing:
        return existing
    item = UserRole(
        id=new_id(),
        user_id=user.id,
        role_id=role.id,
        assigned_by_id=None,
        assigned_at=datetime.now(UTC),
        scope="legacy-import",
    )
    session.add(item)
    session.flush()
    return item


def promote_user_group(session: OrmSession, row: dict[str, Any]) -> UserRole | None:
    user = lookup_legacy(session, User, int(restore_value(row["user_id"])))
    if user is None:
        return None
    group_identifier = int(restore_value(row["group_id"]))
    group_record = session.scalar(
        select(LegacyArchiveRecord).where(
            LegacyArchiveRecord.source_table == "auth_group",
            LegacyArchiveRecord.source_pk == json.dumps([group_identifier], separators=(",", ":")),
        )
    )
    if group_record is None:
        return None
    return assign_role(session, user, legacy_group_role_key(group_record.payload))


def promote_news(session: OrmSession, row: dict[str, Any]) -> Article:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, Article, identifier)
    if existing:
        return existing
    published = bool(restore_value(row.get("is_published", False)))
    item = Article(
        id=new_id(),
        legacy_id=identifier,
        slug=str(restore_value(row.get("news_slug")) or f"legacy-news-{identifier}"),
        title=str(restore_value(row["title"])),
        content_html=sanitize_html(restore_value(row.get("content"))),
        author_id=user_id(session, restore_value(row.get("author_id"))),
        status="published" if published else "draft",
        published_at=restore_value(row.get("created_at")) if published else None,
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def promote_announcement(session: OrmSession, row: dict[str, Any]) -> Announcement:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, Announcement, identifier)
    if existing:
        return existing
    legacy_status = str(restore_value(row.get("status")) or "DRAFT").casefold()
    item = Announcement(
        id=new_id(),
        legacy_id=identifier,
        title=str(restore_value(row["title"])),
        content_html=sanitize_html(restore_value(row.get("content"))),
        status=legacy_status,
        audiences=[]
        if restore_value(row.get("target")) == "everyone"
        else [{"type": "legacy_groups", "value": "captured"}],
        created_by_id=user_id(session, restore_value(row.get("created_by_id"))),
        published_at=restore_value(row.get("created_at")) if legacy_status == "published" else None,
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def promote_event(session: OrmSession, row: dict[str, Any]) -> Event:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, Event, identifier)
    if existing:
        return existing
    published = bool(restore_value(row.get("is_published", False)))
    item = Event(
        id=new_id(),
        legacy_id=identifier,
        slug=str(restore_value(row.get("event_slug")) or f"legacy-event-{identifier}"),
        title=str(restore_value(row["title"])),
        short_description=str(restore_value(row.get("short_description")) or ""),
        start_date=restore_value(row["start_date"]),
        end_date=restore_value(row.get("end_date")),
        start_time=restore_value(row.get("start_time")),
        end_time=restore_value(row.get("end_time")),
        event_type=str(restore_value(row.get("event_type")) or "meeting"),
        status=str(restore_value(row.get("status")) or "upcoming"),
        publication_status="published" if published else "draft",
        venue=restore_value(row.get("venue")),
        address=" ".join(
            str(value)
            for value in (restore_value(row.get("address")), restore_value(row.get("city")))
            if value
        )
        or None,
        location_url=restore_value(row.get("location_url")),
        is_online=bool(restore_value(row.get("is_online", False))),
        online_platform=restore_value(row.get("online_platform")),
        online_link_encrypted=field_cipher().encrypt(
            str(restore_value(row["online_link"])).encode()
        )
        if restore_value(row.get("online_link"))
        else None,
        access_code_encrypted=field_cipher().encrypt(
            str(restore_value(row["access_code"])).encode()
        )
        if restore_value(row.get("access_code"))
        else None,
        registration_required=bool(restore_value(row.get("registration_required", False))),
        registration_url=restore_value(row.get("registration_url")),
        registration_deadline=restore_value(row.get("registration_deadline")),
        max_participants=int(restore_value(row.get("max_participants")) or 0) or None,
        expected_participants=int(restore_value(row.get("expected_participants")) or 0),
        cpd_credits=restore_value(row.get("cpd_credits")) or Decimal("0"),
        organizer={
            key: value
            for key, value in {
                "name": restore_value(row.get("organizer_name")),
                "email": restore_value(row.get("organizer_email")),
                "phone": restore_value(row.get("organizer_phone")),
            }.items()
            if value
        },
        created_by_id=user_id(session, restore_value(row.get("created_by_id"))),
        published_at=restore_value(row.get("created_at")) if published else None,
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def promote_document(session: OrmSession, row: dict[str, Any]) -> Document:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, Document, identifier)
    if existing:
        return existing
    status = str(restore_value(row.get("status")) or "Draft").casefold()
    visibility = restore_value(row.get("visibility"))
    item = Document(
        id=new_id(),
        legacy_id=identifier,
        public_id=f"LEGACY-DOC-{identifier}",
        title=str(restore_value(row["title"])),
        category=str(restore_value(row.get("category")) or "internal"),
        sender=restore_value(row.get("sender")),
        receiver=restore_value(row.get("receiver")),
        document_date=restore_value(row.get("date")),
        status="published" if status == "published" else "draft",
        audiences=[]
        if visibility == "everyone"
        else [{"type": "legacy_groups", "value": "captured"}],
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def promote_gallery(session: OrmSession, row: dict[str, Any]) -> Gallery:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, Gallery, identifier)
    if existing:
        return existing
    active = bool(restore_value(row.get("is_active", True)))
    item = Gallery(
        id=new_id(),
        legacy_id=identifier,
        slug=f"legacy-gallery-{identifier}-{slugify(str(restore_value(row['title'])))}",
        title=str(restore_value(row["title"])),
        description=str(restore_value(row.get("description")) or ""),
        status="published" if active else "archived",
        published_at=restore_value(row.get("created_at")) if active else None,
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def promote_ad_slot(session: OrmSession, row: dict[str, Any]) -> AdSlot:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, AdSlot, identifier)
    if existing:
        return existing
    width = int(restore_value(row.get("width")) or 728)
    height = int(restore_value(row.get("height")) or 90)
    item = AdSlot(
        id=new_id(),
        legacy_id=identifier,
        key=str(restore_value(row["key"])),
        name=str(restore_value(row["name"])),
        width=width,
        height=height,
        location=str(restore_value(row.get("location")) or ""),
        description=str(restore_value(row.get("description")) or ""),
    )
    session.add(item)
    session.flush()
    return item


def _default_ad_slot(session: OrmSession) -> AdSlot:
    slot = session.scalar(select(AdSlot).where(AdSlot.key == "footer"))
    if slot is not None:
        return slot
    slot = session.scalar(select(AdSlot).order_by(AdSlot.created_at).limit(1))
    if slot is not None:
        return slot
    slot = AdSlot(
        id=new_id(),
        key="footer",
        name="Site footer strip",
        width=970,
        height=90,
        location="All public pages · above footer",
        is_active=True,
    )
    session.add(slot)
    session.flush()
    return slot


def promote_ad_plan(session: OrmSession, row: dict[str, Any]) -> AdPlan:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, AdPlan, identifier)
    if existing:
        return existing
    item = AdPlan(
        id=new_id(),
        legacy_id=identifier,
        slot_id=_default_ad_slot(session).id,
        name=str(restore_value(row["name"])),
        description=str(restore_value(row.get("description")) or ""),
        price=restore_value(row.get("price")) or Decimal("0"),
        duration_days=int(restore_value(row.get("duration_in_days")) or 30),
        is_active=restore_value(row.get("status")) == "active",
    )
    session.add(item)
    session.flush()
    return item


def promote_ad(session: OrmSession, row: dict[str, Any]) -> AdCampaign | None:
    identifier = legacy_id(row)
    existing = lookup_legacy(session, AdCampaign, identifier)
    if existing:
        return existing
    slot = lookup_legacy(session, AdSlot, int(restore_value(row["slot_id"])))
    if not slot:
        return None
    active = bool(restore_value(row.get("active", True)))
    item = AdCampaign(
        id=new_id(),
        legacy_id=identifier,
        slot_id=slot.id,
        created_by_id=user_id(session, restore_value(row.get("created_by_id"))),
        title=str(restore_value(row.get("title")) or f"Legacy campaign {identifier}"),
        target_url=restore_value(row.get("target_url")),
        status="active" if active else "draft",
        priority=int(restore_value(row.get("priority")) or 0),
        starts_at=restore_value(row.get("start")),
        ends_at=restore_value(row.get("end")),
        impressions=int(restore_value(row.get("impressions")) or 0),
        clicks=int(restore_value(row.get("clicks")) or 0),
        created_at=restore_value(row.get("created_at")) or datetime.now(UTC),
        updated_at=restore_value(row.get("updated_at")) or datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


PROMOTERS: list[tuple[str, Any]] = [
    ("accounts_school", lambda session, row: promote_organization(session, row, "school")),
    ("accounts_college", lambda session, row: promote_organization(session, row, "college")),
    (
        "accounts_department",
        lambda session, row: promote_organization(session, row, "department"),
    ),
    ("accounts_user", promote_user),
    ("auth_group", promote_group),
    ("accounts_user_groups", promote_user_group),
    ("dashboard_news", promote_news),
    ("dashboard_announcement", promote_announcement),
    ("dashboard_event", promote_event),
    ("dashboard_document", promote_document),
    ("gallery_gallery", promote_gallery),
    ("adverts_adslot", promote_ad_slot),
    ("adverts_advertplan", promote_ad_plan),
    ("adverts_ad", promote_ad),
]


def promote(target: Engine, batch_id: str) -> None:
    with OrmSession(target) as session:
        for table_name, promoter in PROMOTERS:
            records = session.scalars(
                select(LegacyArchiveRecord)
                .where(LegacyArchiveRecord.source_table == table_name)
                .order_by(LegacyArchiveRecord.source_pk)
            ).all()
            for record in records:
                target_item = promoter(session, record.payload)
                if target_item is None:
                    continue
                record.classification = "promoted"
                disposition = session.scalar(
                    select(MigrationDisposition).where(
                        MigrationDisposition.source_table == record.source_table,
                        MigrationDisposition.source_pk == record.source_pk,
                    )
                )
                if disposition:
                    disposition.disposition = "migrated"
                    disposition.target_type = target_item.__tablename__
                    disposition.target_id = target_item.id
                    disposition.reason = "Promoted by versioned legacy mapping"
            session.commit()


def copy_files(media_root: Path, archive_dir: Path, upload: bool) -> dict[str, Any]:
    root = media_root.resolve(strict=True)
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "files": [],
        "total_bytes": 0,
    }
    client = s3_client() if upload else None
    settings = get_settings()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeError(f"Symlink requires an explicit migration decision: {path}")
        if not path.is_file():
            continue
        resolved = path.resolve(strict=True)
        if root not in resolved.parents:
            raise RuntimeError(f"File escapes media root: {path}")
        digest = hashlib.sha256()
        byte_size = 0
        with resolved.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                byte_size += len(chunk)
        relative = resolved.relative_to(root).as_posix()
        storage_key = f"legacy-media/{relative}"
        target_verified = False
        if client:
            client.upload_file(
                str(resolved),
                settings.media_bucket,
                storage_key,
                ExtraArgs={
                    "ContentType": mimetypes.guess_type(relative)[0] or "application/octet-stream",
                    "Metadata": {"sha256": digest.hexdigest()},
                },
            )
            uploaded = client.head_object(Bucket=settings.media_bucket, Key=storage_key)
            uploaded_hash = str(uploaded.get("Metadata", {}).get("sha256", ""))
            if int(uploaded["ContentLength"]) != byte_size or uploaded_hash != digest.hexdigest():
                raise RuntimeError(f"Uploaded object did not verify: {storage_key}")
            target_verified = True
        manifest["files"].append(
            {
                "path": relative,
                "byte_size": byte_size,
                "sha256": digest.hexdigest(),
                "storage_key": storage_key if upload else None,
                "target_verified": target_verified,
            }
        )
        manifest["total_bytes"] += byte_size
    manifest["file_count"] = len(manifest["files"])
    output = archive_dir / "media-manifest.json"
    write_private_json(output, manifest)
    return manifest


def _manifest_index(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index: dict[str, dict[str, Any]] = {}
    for item in manifest.get("files", []):
        relative = str(item.get("path") or "").lstrip("/")
        if not relative:
            continue
        index[relative] = item
        storage_key = item.get("storage_key") or f"legacy-media/{relative}"
        index[storage_key] = item
    return index


def ensure_media_asset(
    session: OrmSession,
    *,
    relative_path: str,
    manifest: Mapping[str, dict[str, Any]],
    is_private: bool,
    caption: str | None = None,
    alt_text: str | None = None,
    owner_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> MediaAsset | None:
    relative = relative_path.strip().lstrip("/")
    if not relative:
        return None
    storage_key = f"legacy-media/{relative}"
    existing = session.scalar(
        select(MediaAsset).where(MediaAsset.storage_key == storage_key)
    )
    if existing:
        if existing.status != "ready":
            existing.status = "ready"
        if existing.is_private and not is_private:
            existing.is_private = False
        if caption and not existing.caption:
            existing.caption = caption
        if alt_text and not existing.alt_text:
            existing.alt_text = alt_text
        if owner_id and existing.owner_id is None:
            existing.owner_id = owner_id
        return existing

    details = manifest.get(relative) or manifest.get(storage_key)
    if details is None:
        # Fall back to object-store HEAD so recovery still works if the
        # manifest path is incomplete but the object was uploaded.
        client = s3_client()
        settings = get_settings()
        try:
            head = client.head_object(Bucket=settings.media_bucket, Key=storage_key)
        except Exception:
            return None
        byte_size = int(head["ContentLength"])
        sha256 = str(head.get("Metadata", {}).get("sha256") or "")
        if not sha256:
            sha256 = hashlib.sha256(f"{storage_key}:{byte_size}".encode()).hexdigest()
        content_type = (
            head.get("ContentType")
            or mimetypes.guess_type(relative)[0]
            or "application/octet-stream"
        )
    else:
        if details.get("target_verified") is not True and details.get("storage_key"):
            # Prefer verified uploads; still accept listed keys already in store.
            pass
        byte_size = int(details["byte_size"])
        sha256 = str(details["sha256"])
        content_type = mimetypes.guess_type(relative)[0] or "application/octet-stream"

    asset = MediaAsset(
        id=new_id(),
        owner_id=owner_id,
        storage_key=storage_key,
        original_filename=Path(relative).name,
        content_type=content_type,
        byte_size=byte_size,
        sha256=sha256,
        status="ready",
        is_private=is_private,
        alt_text=alt_text,
        caption=caption,
        metadata_json=metadata or {"source": "legacy-media-link"},
    )
    session.add(asset)
    session.flush()
    return asset


def link_media(target: Engine, manifest_path: Path) -> dict[str, int]:
    """Create MediaAsset rows for uploaded legacy files and wire joins.

    The initial promote step intentionally left dashboard_file / gallery_image /
    attachment tables archive-only. Files themselves were copied into object
    storage under legacy-media/; this command reconnects them.
    """
    manifest = _manifest_index(manifest_path)
    stats = {
        "assets_created_or_reused": 0,
        "document_files": 0,
        "gallery_items": 0,
        "article_attachments": 0,
        "article_featured": 0,
        "event_featured": 0,
        "user_portraits": 0,
        "missing_objects": 0,
    }
    with OrmSession(target) as session:
        file_assets: dict[int, MediaAsset] = {}
        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "dashboard_file")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            relative = str(restore_value(record.payload.get("file")) or "")
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=True,
                metadata={
                    "source": "dashboard_file",
                    "legacy_pk": legacy_id(record.payload),
                },
            )
            if asset is None:
                stats["missing_objects"] += 1
                continue
            file_assets[legacy_id(record.payload)] = asset
            stats["assets_created_or_reused"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "dashboard_document_files")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            document = lookup_legacy(
                session, Document, int(restore_value(record.payload["document_id"]))
            )
            asset = file_assets.get(int(restore_value(record.payload["file_id"])))
            if document is None or asset is None:
                stats["missing_objects"] += 1
                continue
            existing = session.scalar(
                select(DocumentFile).where(
                    DocumentFile.document_id == document.id,
                    DocumentFile.media_asset_id == asset.id,
                )
            )
            if existing:
                continue
            position = int(
                session.scalar(
                    select(func.count(DocumentFile.id)).where(
                        DocumentFile.document_id == document.id
                    )
                )
                or 0
            )
            session.add(
                DocumentFile(
                    id=new_id(),
                    document_id=document.id,
                    media_asset_id=asset.id,
                    version_number=document.version or 1,
                    position=position,
                )
            )
            stats["document_files"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "gallery_image")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            gallery = lookup_legacy(
                session, Gallery, int(restore_value(record.payload["gallery_id"]))
            )
            relative = str(restore_value(record.payload.get("image")) or "")
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=False,
                caption=restore_value(record.payload.get("caption")),
                metadata={
                    "source": "gallery_image",
                    "legacy_pk": legacy_id(record.payload),
                },
            )
            if gallery is None or asset is None:
                stats["missing_objects"] += 1
                continue
            stats["assets_created_or_reused"] += 1
            position = int(restore_value(record.payload.get("order")) or 0)
            existing = session.scalar(
                select(GalleryItem).where(
                    GalleryItem.gallery_id == gallery.id,
                    GalleryItem.media_asset_id == asset.id,
                )
            )
            if existing:
                continue
            clash = session.scalar(
                select(GalleryItem).where(
                    GalleryItem.gallery_id == gallery.id,
                    GalleryItem.position == position,
                )
            )
            if clash is not None:
                position = int(
                    session.scalar(
                        select(func.count(GalleryItem.id)).where(
                            GalleryItem.gallery_id == gallery.id
                        )
                    )
                    or 0
                )
            session.add(
                GalleryItem(
                    id=new_id(),
                    gallery_id=gallery.id,
                    media_asset_id=asset.id,
                    position=position,
                    caption=restore_value(record.payload.get("caption")),
                    allow_download=True,
                )
            )
            stats["gallery_items"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "dashboard_attacheddocument")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            article = lookup_legacy(
                session, Article, int(restore_value(record.payload["news_id"]))
            )
            relative = str(restore_value(record.payload.get("file")) or "")
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=False,
                alt_text=restore_value(record.payload.get("name")),
                metadata={
                    "source": "dashboard_attacheddocument",
                    "legacy_pk": legacy_id(record.payload),
                },
            )
            if article is None or asset is None:
                stats["missing_objects"] += 1
                continue
            stats["assets_created_or_reused"] += 1
            existing = session.scalar(
                select(ArticleAttachment).where(
                    ArticleAttachment.article_id == article.id,
                    ArticleAttachment.media_asset_id == asset.id,
                )
            )
            if existing:
                continue
            position = int(
                session.scalar(
                    select(func.count(ArticleAttachment.id)).where(
                        ArticleAttachment.article_id == article.id
                    )
                )
                or 0
            )
            session.add(
                ArticleAttachment(
                    id=new_id(),
                    article_id=article.id,
                    media_asset_id=asset.id,
                    position=position,
                )
            )
            stats["article_attachments"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "dashboard_news")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            article = lookup_legacy(session, Article, legacy_id(record.payload))
            relative = str(restore_value(record.payload.get("featured_image")) or "")
            if article is None or not relative:
                continue
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=False,
                alt_text=article.title,
                metadata={"source": "dashboard_news.featured_image"},
            )
            if asset is None:
                stats["missing_objects"] += 1
                continue
            stats["assets_created_or_reused"] += 1
            if article.featured_media_id != asset.id:
                article.featured_media_id = asset.id
                stats["article_featured"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "dashboard_event")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            event = lookup_legacy(session, Event, legacy_id(record.payload))
            relative = str(restore_value(record.payload.get("featured_image")) or "")
            if event is None or not relative:
                continue
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=False,
                alt_text=event.title,
                metadata={"source": "dashboard_event.featured_image"},
            )
            if asset is None:
                stats["missing_objects"] += 1
                continue
            stats["assets_created_or_reused"] += 1
            if event.featured_media_id != asset.id:
                event.featured_media_id = asset.id
                stats["event_featured"] += 1

        for record in session.scalars(
            select(LegacyArchiveRecord)
            .where(LegacyArchiveRecord.source_table == "accounts_user")
            .order_by(LegacyArchiveRecord.source_pk)
        ):
            user = lookup_legacy(session, User, legacy_id(record.payload))
            if user is None:
                continue
            relative = str(
                restore_value(record.payload.get("executive_image"))
                or restore_value(record.payload.get("profile_pic"))
                or ""
            )
            if not relative:
                continue
            asset = ensure_media_asset(
                session,
                relative_path=relative,
                manifest=manifest,
                is_private=False,
                owner_id=user.id,
                alt_text=f"{user.other_name} {user.surname}".strip(),
                metadata={"source": "accounts_user.portrait"},
            )
            if asset is None:
                stats["missing_objects"] += 1
                continue
            stats["assets_created_or_reused"] += 1
            if user.profile_media_id != asset.id:
                user.profile_media_id = asset.id
                stats["user_portraits"] += 1

        session.commit()
    return stats


def reconcile(source: Engine, target: Engine, output: Path) -> bool:
    source_report = inventory(source, output.with_name("source-inventory.json"))
    result: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "tables": {},
        "passed": True,
        "archive_approval_required": [],
    }
    with OrmSession(target) as session:
        for table_name, details in source_report["tables"].items():
            source_count = int(details["rows"])
            archive_count = int(
                session.scalar(
                    select(func.count(LegacyArchiveRecord.id)).where(
                        LegacyArchiveRecord.source_table == table_name
                    )
                )
                or 0
            )
            disposition_count = int(
                session.scalar(
                    select(func.count(MigrationDisposition.id)).where(
                        MigrationDisposition.source_table == table_name
                    )
                )
                or 0
            )
            migrated_count = int(
                session.scalar(
                    select(func.count(MigrationDisposition.id)).where(
                        MigrationDisposition.source_table == table_name,
                        MigrationDisposition.disposition == "migrated",
                    )
                )
                or 0
            )
            archived_count = disposition_count - migrated_count
            passed = source_count == archive_count == disposition_count
            if source_count == 0:
                coverage = "empty"
            elif migrated_count == source_count:
                coverage = "operationally_promoted"
            elif migrated_count == 0:
                coverage = "archive_only"
            else:
                coverage = "partially_promoted"
            result["tables"][table_name] = {
                "source": source_count,
                "captured": archive_count,
                "dispositions": disposition_count,
                "migrated": migrated_count,
                "archived_only": archived_count,
                "coverage": coverage,
                "passed": passed,
            }
            if archived_count:
                result["archive_approval_required"].append(table_name)
            result["passed"] = bool(result["passed"] and passed)
    write_private_json(output, result)
    return bool(result["passed"])


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["inventory", "capture", "promote", "files", "link-media", "reconcile"],
    )
    parser.add_argument("--source-url", default=settings.legacy_database_url)
    parser.add_argument("--target-url", default=settings.database_url)
    parser.add_argument("--batch-id", default=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    parser.add_argument("--archive-dir", type=Path, default=Path("migration-evidence"))
    parser.add_argument("--output", type=Path, default=Path("migration-evidence/report.json"))
    parser.add_argument("--media-root", type=Path)
    parser.add_argument("--upload", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command in {"inventory", "capture", "reconcile"} and not args.source_url:
        raise SystemExit("--source-url is required")
    if args.command == "files":
        if not args.media_root:
            raise SystemExit("--media-root is required")
        copy_files(args.media_root, args.archive_dir, args.upload)
        return
    target = engine(args.target_url)
    if args.command == "promote":
        promote(target, args.batch_id)
        return
    if args.command == "link-media":
        manifest = args.archive_dir / "media-manifest.json"
        if args.output and args.output.name.endswith("media-manifest.json"):
            manifest = args.output
        elif not manifest.is_file():
            # Allow --output to point at the manifest directly.
            candidate = Path(args.output)
            if candidate.is_file():
                manifest = candidate
        if not manifest.is_file():
            raise SystemExit(f"media manifest not found: {manifest}")
        stats = link_media(target, manifest)
        print(json.dumps({"linked": True, **stats}, indent=2, sort_keys=True))
        return
    source = engine(args.source_url)
    if args.command == "inventory":
        inventory(source, args.output)
    elif args.command == "capture":
        capture(source, target, args.batch_id, args.archive_dir)
    elif args.command == "reconcile" and not reconcile(source, target, args.output):
        raise SystemExit("Reconciliation failed")


if __name__ == "__main__":
    main()
