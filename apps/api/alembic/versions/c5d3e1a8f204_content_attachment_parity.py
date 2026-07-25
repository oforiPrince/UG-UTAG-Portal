"""Add news, event and multi-file document attachments.

Revision ID: c5d3e1a8f204
Revises: 9a7f2c4d1e6b
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5d3e1a8f204"
down_revision: str | Sequence[str] | None = "9a7f2c4d1e6b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("photos_url", sa.String(length=1000), nullable=True))
    op.create_table(
        "article_attachments",
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            name=op.f("fk_article_attachments_article_id_articles"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_article_attachments_media_asset_id_media_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_attachments")),
        sa.UniqueConstraint("article_id", "media_asset_id", name="article_attachment_asset"),
        sa.UniqueConstraint("article_id", "position", name="article_attachment_position"),
    )
    op.create_index(
        op.f("ix_article_attachments_article_id"),
        "article_attachments",
        ["article_id"],
    )
    op.create_index(
        op.f("ix_article_attachments_media_asset_id"),
        "article_attachments",
        ["media_asset_id"],
    )
    op.create_table(
        "event_attachments",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("media_asset_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["events.id"],
            name=op.f("fk_event_attachments_event_id_events"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_event_attachments_media_asset_id_media_assets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_attachments")),
        sa.UniqueConstraint("event_id", "media_asset_id", name="event_attachment_asset"),
        sa.UniqueConstraint("event_id", "position", name="event_attachment_position"),
    )
    op.create_index(
        op.f("ix_event_attachments_event_id"),
        "event_attachments",
        ["event_id"],
    )
    op.create_index(
        op.f("ix_event_attachments_media_asset_id"),
        "event_attachments",
        ["media_asset_id"],
    )
    op.add_column(
        "document_files",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.drop_constraint("document_version", "document_files", type_="unique")
    op.create_unique_constraint(
        "document_version_position",
        "document_files",
        ["document_id", "version_number", "position"],
    )
    op.create_unique_constraint(
        "document_version_asset",
        "document_files",
        ["document_id", "version_number", "media_asset_id"],
    )
    op.alter_column("document_files", "position", server_default=None)


def downgrade() -> None:
    op.drop_constraint("document_version_asset", "document_files", type_="unique")
    op.drop_constraint("document_version_position", "document_files", type_="unique")
    op.create_unique_constraint(
        "document_version", "document_files", ["document_id", "version_number"]
    )
    op.drop_column("document_files", "position")
    op.drop_index(op.f("ix_event_attachments_media_asset_id"), table_name="event_attachments")
    op.drop_index(op.f("ix_event_attachments_event_id"), table_name="event_attachments")
    op.drop_table("event_attachments")
    op.drop_index(
        op.f("ix_article_attachments_media_asset_id"),
        table_name="article_attachments",
    )
    op.drop_index(op.f("ix_article_attachments_article_id"), table_name="article_attachments")
    op.drop_table("article_attachments")
    op.drop_column("events", "photos_url")
