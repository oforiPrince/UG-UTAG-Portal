"""Remove retired inactive advertising placements.

Revision ID: f3a7c1e8b924
Revises: e2b5d9f0a813
Create Date: 2026-08-02
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f3a7c1e8b924"
down_revision: str | Sequence[str] | None = "e2b5d9f0a813"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    slot_ids = [
        row[0]
        for row in conn.execute(
            sa.text(
                """
                SELECT id
                FROM ad_slots
                WHERE is_active = false
                   OR key IN (
                       'top', 'hero', 'sidebar', 'bottom', 'home-hero', 'dashboard-partner'
                   )
                """
            )
        ).all()
    ]
    if not slot_ids:
        return

    for slot_id in slot_ids:
        campaign_ids = [
            row[0]
            for row in conn.execute(
                sa.text("SELECT id FROM ad_campaigns WHERE slot_id = :slot_id"),
                {"slot_id": slot_id},
            ).all()
        ]
        for campaign_id in campaign_ids:
            conn.execute(
                sa.text("DELETE FROM ad_orders WHERE campaign_id = :campaign_id"),
                {"campaign_id": campaign_id},
            )
            conn.execute(
                sa.text("DELETE FROM ad_campaigns WHERE id = :campaign_id"),
                {"campaign_id": campaign_id},
            )

        plan_ids = [
            row[0]
            for row in conn.execute(
                sa.text("SELECT id FROM ad_plans WHERE slot_id = :slot_id"),
                {"slot_id": slot_id},
            ).all()
        ]
        for plan_id in plan_ids:
            conn.execute(
                sa.text("DELETE FROM ad_orders WHERE plan_id = :plan_id"),
                {"plan_id": plan_id},
            )
            conn.execute(
                sa.text("DELETE FROM ad_plans WHERE id = :plan_id"),
                {"plan_id": plan_id},
            )

        conn.execute(
            sa.text("DELETE FROM ad_slots WHERE id = :slot_id"),
            {"slot_id": slot_id},
        )


def downgrade() -> None:
    # Retired placements are intentionally not restored.
    pass
