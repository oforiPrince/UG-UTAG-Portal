"""Add secure chat invitation links.

Revision ID: d7f41b9c6a20
Revises: c5d3e1a8f204
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7f41b9c6a20"
down_revision: str | Sequence[str] | None = "c5d3e1a8f204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("uq_message_attachments_storage_key"),
        "message_attachments",
        type_="unique",
    )
    op.create_table(
        "conversation_invites",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_conversation_invites_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_conversation_invites_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_conversation_invites_token_hash")),
    )
    op.create_index(
        op.f("ix_conversation_invites_conversation_id"),
        "conversation_invites",
        ["conversation_id"],
    )
    op.create_index(
        op.f("ix_conversation_invites_expires_at"),
        "conversation_invites",
        ["expires_at"],
    )
    op.create_index(
        op.f("ix_conversation_invites_token_hash"),
        "conversation_invites",
        ["token_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_conversation_invites_token_hash"),
        table_name="conversation_invites",
    )
    op.drop_index(
        op.f("ix_conversation_invites_expires_at"),
        table_name="conversation_invites",
    )
    op.drop_index(
        op.f("ix_conversation_invites_conversation_id"),
        table_name="conversation_invites",
    )
    op.drop_table("conversation_invites")
    op.create_unique_constraint(
        op.f("uq_message_attachments_storage_key"),
        "message_attachments",
        ["storage_key"],
    )
