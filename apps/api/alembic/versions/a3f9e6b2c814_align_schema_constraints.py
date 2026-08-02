"""align schema constraints

Revision ID: a3f9e6b2c814
Revises: f8c1d7a3e920
Create Date: 2026-07-27 23:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3f9e6b2c814"
down_revision: str | Sequence[str] | None = "f8c1d7a3e920"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_conversation_invites_token_hash"),
        "conversation_invites",
        type_="unique",
    )
    op.drop_index(
        op.f("ix_conversation_invites_token_hash"),
        table_name="conversation_invites",
    )
    op.create_index(
        op.f("ix_conversation_invites_token_hash"),
        "conversation_invites",
        ["token_hash"],
        unique=True,
    )
    op.alter_column("gallery_items", "allow_download", server_default=None)
    op.alter_column("executive_appointments", "show_email", server_default=None)
    op.alter_column("executive_appointments", "show_phone", server_default=None)


def downgrade() -> None:
    op.alter_column(
        "executive_appointments",
        "show_phone",
        server_default=sa.text("false"),
    )
    op.alter_column(
        "executive_appointments",
        "show_email",
        server_default=sa.text("false"),
    )
    op.alter_column(
        "gallery_items",
        "allow_download",
        server_default=sa.text("true"),
    )
    op.drop_index(
        op.f("ix_conversation_invites_token_hash"),
        table_name="conversation_invites",
    )
    op.create_unique_constraint(
        op.f("uq_conversation_invites_token_hash"),
        "conversation_invites",
        ["token_hash"],
    )
    op.create_index(
        op.f("ix_conversation_invites_token_hash"),
        "conversation_invites",
        ["token_hash"],
    )
