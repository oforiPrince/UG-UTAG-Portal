from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, LargeBinary, MetaData, Numeric, Table, create_engine, insert
from sqlalchemy.orm import Session

from scripts.legacy_migration import (
    MigrationDriftError,
    capture,
    checksum,
    copy_files,
    legacy_group_role_key,
    reconcile,
    restore_value,
    source_tables,
)
from utag_api.database import Base
from utag_api.models import LegacyArchiveRecord, MigrationDisposition
from utag_api.permissions import ROLE_GRANTS


def test_capture_reconcile_and_drift_detection(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = create_engine(f"sqlite:///{tmp_path / 'source.sqlite'}")
    target = create_engine(f"sqlite:///{tmp_path / 'target.sqlite'}")
    metadata = MetaData()
    sample = Table(
        "legacy_sample",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("amount", Numeric(10, 2), nullable=False),
        Column("payload", LargeBinary, nullable=False),
    )
    metadata.create_all(source)
    Base.metadata.create_all(target)
    with source.begin() as connection:
        connection.execute(
            insert(sample).values(id=7, amount=Decimal("42.75"), payload=b"\x00\xff")
        )

    archive_directory = tmp_path / "evidence"
    capture(source, target, "test-batch", archive_directory)
    assert reconcile(source, target, tmp_path / "reconciliation.json") is True

    with Session(target) as session:
        archived = session.query(LegacyArchiveRecord).one()
        disposition = session.query(MigrationDisposition).one()
        assert archived.source_pk == "[7]"
        assert restore_value(archived.payload["amount"]) == Decimal("42.75")
        assert restore_value(archived.payload["payload"]) == b"\x00\xff"
        assert disposition.disposition == "archived"

        session.delete(disposition)
        session.commit()

    capture(source, target, "test-batch", archive_directory)
    with Session(target) as session:
        assert session.query(MigrationDisposition).count() == 1

    with source.begin() as connection:
        connection.execute(sample.update().where(sample.c.id == 7).values(amount=Decimal("43")))
    with pytest.raises(MigrationDriftError):
        capture(source, target, "test-batch", archive_directory)


def test_checksum_is_canonical() -> None:
    timestamp = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    left = {"amount": {"$decimal": "1.00"}, "when": {"$temporal": timestamp.isoformat()}}
    right = {"when": {"$temporal": timestamp.isoformat()}, "amount": {"$decimal": "1.00"}}

    assert checksum(left) == checksum(right)


def test_source_tables_include_django_security_and_schema_rows(tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = create_engine(f"sqlite:///{tmp_path / 'django.sqlite'}")
    metadata = MetaData()
    Table("django_session", metadata, Column("id", Integer, primary_key=True))
    Table("django_migrations", metadata, Column("id", Integer, primary_key=True))
    metadata.create_all(source)

    assert source_tables(source) == ["django_migrations", "django_session"]


def test_symlinked_media_is_rejected(tmp_path) -> None:  # type: ignore[no-untyped-def]
    media_root = tmp_path / "media"
    media_root.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("not safe to follow", encoding="utf-8")
    (media_root / "linked.txt").symlink_to(target)

    with pytest.raises(RuntimeError, match="Symlink requires an explicit migration decision"):
        copy_files(media_root, tmp_path / "evidence", upload=False)


def test_legacy_roles_map_without_privilege_escalation() -> None:
    assert legacy_group_role_key({"id": 1, "name": "Secretary"}) == "secretary"
    assert legacy_group_role_key({"id": 2, "name": "Admin"}) == "administrator"
    assert legacy_group_role_key({"id": 7, "name": "Special Committee"}) == (
        "legacy-7-special-committee"
    )
    assert "settings.manage" not in ROLE_GRANTS["secretary"]
