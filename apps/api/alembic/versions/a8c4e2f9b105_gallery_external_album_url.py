"""Add optional external album links to galleries.

Revision ID: a8c4e2f9b105
Revises: f2a9d5c3b817
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8c4e2f9b105"
down_revision: str | Sequence[str] | None = "f2a9d5c3b817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "galleries",
        sa.Column("external_album_url", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("galleries", "external_album_url")
