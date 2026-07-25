"""Add durable legacy archive and encrypted chat attachments.

Revision ID: 58a30c54b2e1
Revises: 3c1031d8689f
Create Date: 2026-07-22
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "58a30c54b2e1"
down_revision: str | Sequence[str] | None = "3c1031d8689f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "legacy_archive_records",
        sa.Column("batch_id", sa.String(length=100), nullable=False),
        sa.Column("source_table", sa.String(length=180), nullable=False),
        sa.Column("source_pk", sa.String(length=180), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("classification", sa.String(length=30), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_legacy_archive_records")),
        sa.UniqueConstraint("source_table", "source_pk", name="legacy_archive_source_record"),
    )
    op.create_index(
        op.f("ix_legacy_archive_records_batch_id"),
        "legacy_archive_records",
        ["batch_id"],
    )
    op.create_index(
        op.f("ix_legacy_archive_records_classification"),
        "legacy_archive_records",
        ["classification"],
    )
    op.create_index(
        op.f("ix_legacy_archive_records_captured_at"),
        "legacy_archive_records",
        ["captured_at"],
    )
    op.create_index(
        op.f("ix_legacy_archive_records_source_hash"),
        "legacy_archive_records",
        ["source_hash"],
    )
    op.create_index(
        op.f("ix_legacy_archive_records_source_table"),
        "legacy_archive_records",
        ["source_table"],
    )
    op.create_table(
        "message_attachments",
        sa.Column("legacy_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("thumbnail_storage_key", sa.String(length=500), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("encryption_key_version", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_message_attachments_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_attachments")),
        sa.UniqueConstraint("legacy_id", name=op.f("uq_message_attachments_legacy_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_message_attachments_storage_key")),
    )
    op.create_index(
        op.f("ix_message_attachments_message_id"),
        "message_attachments",
        ["message_id"],
    )
    op.create_index(
        op.f("ix_message_attachments_sha256"),
        "message_attachments",
        ["sha256"],
    )
    op.create_index(
        op.f("ix_message_attachments_status"),
        "message_attachments",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_message_attachments_status"), table_name="message_attachments")
    op.drop_index(op.f("ix_message_attachments_sha256"), table_name="message_attachments")
    op.drop_index(op.f("ix_message_attachments_message_id"), table_name="message_attachments")
    op.drop_table("message_attachments")
    op.drop_index(
        op.f("ix_legacy_archive_records_source_table"),
        table_name="legacy_archive_records",
    )
    op.drop_index(
        op.f("ix_legacy_archive_records_source_hash"),
        table_name="legacy_archive_records",
    )
    op.drop_index(
        op.f("ix_legacy_archive_records_captured_at"),
        table_name="legacy_archive_records",
    )
    op.drop_index(
        op.f("ix_legacy_archive_records_classification"),
        table_name="legacy_archive_records",
    )
    op.drop_index(op.f("ix_legacy_archive_records_batch_id"), table_name="legacy_archive_records")
    op.drop_table("legacy_archive_records")
