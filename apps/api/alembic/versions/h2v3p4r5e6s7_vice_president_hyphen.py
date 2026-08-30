"""Normalize Vice President position spelling to Vice-President.

Revision ID: h2v3p4r5e6s7
Revises: g1d2r3i4v5e6
Create Date: 2026-08-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "h2v3p4r5e6s7"
down_revision: str | Sequence[str] | None = "g1d2r3i4v5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE executive_appointments
        SET position = 'Vice-President'
        WHERE position = 'Vice President'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE executive_appointments
        SET position = 'Vice President'
        WHERE position = 'Vice-President'
        """
    )
