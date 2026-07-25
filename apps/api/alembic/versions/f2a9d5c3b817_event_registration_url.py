"""Restore the external event registration link from the legacy dashboard.

Revision ID: f2a9d5c3b817
Revises: d7f41b9c6a20
Create Date: 2026-07-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f2a9d5c3b817"
down_revision: str | Sequence[str] | None = "d7f41b9c6a20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "events",
        sa.Column("registration_url", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("events", "registration_url")
