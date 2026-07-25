"""Add optimistic versioning to galleries.

Revision ID: 6e2aa871a4d0
Revises: 58a30c54b2e1
Create Date: 2026-07-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6e2aa871a4d0"
down_revision: str | Sequence[str] | None = "58a30c54b2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "galleries",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("galleries", "version", server_default=None)


def downgrade() -> None:
    op.drop_column("galleries", "version")
