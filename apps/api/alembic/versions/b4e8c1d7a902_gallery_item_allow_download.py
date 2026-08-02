"""gallery item allow download

Revision ID: b4e8c1d7a902
Revises: a8c4e2f9b105
Create Date: 2026-07-25 11:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4e8c1d7a902"
down_revision: str | Sequence[str] | None = "a8c4e2f9b105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gallery_items",
        sa.Column(
            "allow_download",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("gallery_items", "allow_download")
