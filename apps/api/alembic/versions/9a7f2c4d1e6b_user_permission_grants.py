"""Add auditable per-user permission grants.

Revision ID: 9a7f2c4d1e6b
Revises: 6e2aa871a4d0
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9a7f2c4d1e6b"
down_revision: str | Sequence[str] | None = "6e2aa871a4d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_permission_grants",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by_id", sa.Uuid(), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["granted_by_id"],
            ["users.id"],
            name=op.f("fk_user_permission_grants_granted_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_user_permission_grants_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_permission_grants_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_permission_grants")),
        sa.UniqueConstraint(
            "user_id",
            "permission_id",
            name="user_permission_grant",
        ),
    )
    op.create_index(
        op.f("ix_user_permission_grants_permission_id"),
        "user_permission_grants",
        ["permission_id"],
    )
    op.create_index(
        op.f("ix_user_permission_grants_user_id"),
        "user_permission_grants",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_permission_grants_user_id"),
        table_name="user_permission_grants",
    )
    op.drop_index(
        op.f("ix_user_permission_grants_permission_id"),
        table_name="user_permission_grants",
    )
    op.drop_table("user_permission_grants")
