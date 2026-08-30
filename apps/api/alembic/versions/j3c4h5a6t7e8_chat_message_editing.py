"""Add chat message editing timestamp.

Revision ID: j3c4h5a6t7e8
Revises: h2v3p4r5e6s7
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "j3c4h5a6t7e8"
down_revision: str | Sequence[str] | None = "h2v3p4r5e6s7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "edited_at")
