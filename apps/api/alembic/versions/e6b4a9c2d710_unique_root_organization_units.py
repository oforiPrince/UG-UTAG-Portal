"""unique root organization units

Revision ID: e6b4a9c2d710
Revises: b4e8c1d7a902
Create Date: 2026-07-27 23:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e6b4a9c2d710"
down_revision: str | Sequence[str] | None = "b4e8c1d7a902"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_organization_root_identity",
        "organization_units",
        ["unit_type", "name"],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL"),
        sqlite_where=sa.text("parent_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_organization_root_identity",
        table_name="organization_units",
    )
