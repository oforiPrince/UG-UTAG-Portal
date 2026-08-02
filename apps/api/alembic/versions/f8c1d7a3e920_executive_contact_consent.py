"""executive contact consent

Revision ID: f8c1d7a3e920
Revises: e6b4a9c2d710
Create Date: 2026-07-27 23:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8c1d7a3e920"
down_revision: str | Sequence[str] | None = "e6b4a9c2d710"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "executive_appointments",
        sa.Column(
            "show_email",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "executive_appointments",
        sa.Column(
            "show_phone",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("executive_appointments", "show_phone")
    op.drop_column("executive_appointments", "show_email")
