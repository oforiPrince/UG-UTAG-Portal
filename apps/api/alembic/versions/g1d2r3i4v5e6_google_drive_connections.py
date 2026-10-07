"""Add Google Drive OAuth connections for gallery imports.

Revision ID: g1d2r3i4v5e6
Revises: f3a7c1e8b924
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g1d2r3i4v5e6"
down_revision: str | Sequence[str] | None = "f3a7c1e8b924"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "google_drive_connections",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("google_sub", sa.String(length=128), nullable=False),
        sa.Column("google_email", sa.String(length=255), nullable=False),
        sa.Column("access_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.LargeBinary(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_google_drive_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_drive_connections")),
        sa.UniqueConstraint(
            "user_id", name=op.f("uq_google_drive_connections_user_id")
        ),
    )
    op.create_index(
        op.f("ix_google_drive_connections_google_sub"),
        "google_drive_connections",
        ["google_sub"],
        unique=False,
    )
    op.create_index(
        op.f("ix_google_drive_connections_user_id"),
        "google_drive_connections",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_google_drive_connections_user_id"),
        table_name="google_drive_connections",
    )
    op.drop_index(
        op.f("ix_google_drive_connections_google_sub"),
        table_name="google_drive_connections",
    )
    op.drop_table("google_drive_connections")
