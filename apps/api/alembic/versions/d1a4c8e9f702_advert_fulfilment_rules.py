"""Page-aware advert fulfilment rules: house ads vs paid order linkage.

Revision ID: d1a4c8e9f702
Revises: c9e2b7a4d601
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d1a4c8e9f702"
down_revision: str | Sequence[str] | None = "c9e2b7a4d601"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ad_campaigns",
        sa.Column("is_house_ad", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    # Deduplicate campaign links before unique index: keep newest order per campaign.
    op.execute(
        sa.text(
            """
            UPDATE ad_orders AS older
            SET campaign_id = NULL
            WHERE older.campaign_id IS NOT NULL
              AND EXISTS (
                SELECT 1
                FROM ad_orders AS newer
                WHERE newer.campaign_id = older.campaign_id
                  AND newer.created_at > older.created_at
              )
            """
        )
    )
    op.create_index(
        "uq_ad_orders_campaign_id",
        "ad_orders",
        ["campaign_id"],
        unique=True,
        postgresql_where=sa.text("campaign_id IS NOT NULL"),
        sqlite_where=sa.text("campaign_id IS NOT NULL"),
    )
    op.alter_column("ad_campaigns", "is_house_ad", server_default=None)


def downgrade() -> None:
    op.drop_index("uq_ad_orders_campaign_id", table_name="ad_orders")
    op.drop_column("ad_campaigns", "is_house_ad")
