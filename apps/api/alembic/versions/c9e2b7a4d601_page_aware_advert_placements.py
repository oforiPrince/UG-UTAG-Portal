"""Page-aware advert placements and plan slot linkage.

Revision ID: c9e2b7a4d601
Revises: a3f9e6b2c814
Create Date: 2026-08-02
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "c9e2b7a4d601"
down_revision: str | Sequence[str] | None = "a3f9e6b2c814"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CANONICAL_SLOTS = (
    ("home-after-hero", "Home after hero", 970, 250, "Home · after hero", True),
    ("news-sidebar", "News listing rail", 300, 250, "News listing · sidebar", True),
    ("events-sidebar", "Events listing rail", 300, 250, "Events listing · sidebar", True),
    (
        "content-inline",
        "Article / detail strip",
        728,
        90,
        "News, events, gallery detail · after hero",
        True,
    ),
    ("footer", "Site footer strip", 970, 90, "All public pages · above footer", True),
)

OBSOLETE_KEYS = (
    "top",
    "hero",
    "sidebar",
    "bottom",
    "home-hero",
    "dashboard-partner",
)


def upgrade() -> None:
    op.add_column(
        "ad_slots",
        sa.Column("location", sa.String(length=200), server_default="", nullable=False),
    )
    op.execute(sa.text("UPDATE ad_slots SET width = 728 WHERE width IS NULL"))
    op.execute(sa.text("UPDATE ad_slots SET height = 90 WHERE height IS NULL"))
    op.alter_column("ad_slots", "width", existing_type=sa.Integer(), nullable=False)
    op.alter_column("ad_slots", "height", existing_type=sa.Integer(), nullable=False)

    conn = op.get_bind()
    now = datetime.now(UTC)
    for key, name, width, height, location, is_active in CANONICAL_SLOTS:
        existing = conn.execute(
            sa.text("SELECT id FROM ad_slots WHERE key = :key"),
            {"key": key},
        ).first()
        if existing is None:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO ad_slots (
                        id, key, name, width, height, location, description, is_active,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :key, :name, :width, :height, :location, '',
                        :is_active, :now, :now
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "key": key,
                    "name": name,
                    "width": width,
                    "height": height,
                    "location": location,
                    "is_active": is_active,
                    "now": now,
                },
            )
        else:
            conn.execute(
                sa.text(
                    """
                    UPDATE ad_slots
                    SET name = :name,
                        width = :width,
                        height = :height,
                        location = :location,
                        is_active = :is_active,
                        updated_at = :now
                    WHERE key = :key
                    """
                ),
                {
                    "key": key,
                    "name": name,
                    "width": width,
                    "height": height,
                    "location": location,
                    "is_active": is_active,
                    "now": now,
                },
            )

    for key in OBSOLETE_KEYS:
        conn.execute(
            sa.text(
                """
                UPDATE ad_slots
                SET is_active = false,
                    location = CASE WHEN location = '' OR location IS NULL
                        THEN 'Retired · not mounted on public site'
                        ELSE location END,
                    updated_at = :now
                WHERE key = :key
                """
            ),
            {"key": key, "now": now},
        )

    op.add_column("ad_plans", sa.Column("slot_id", sa.Uuid(), nullable=True))
    footer_id = conn.execute(
        sa.text("SELECT id FROM ad_slots WHERE key = 'footer' LIMIT 1")
    ).scalar()
    if footer_id is None:
        footer_id = conn.execute(sa.text("SELECT id FROM ad_slots LIMIT 1")).scalar()
    if footer_id is not None:
        conn.execute(
            sa.text("UPDATE ad_plans SET slot_id = :slot_id WHERE slot_id IS NULL"),
            {"slot_id": footer_id},
        )
    op.alter_column("ad_plans", "slot_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_ad_plans_slot_id", "ad_plans", ["slot_id"])
    op.create_foreign_key(
        "fk_ad_plans_slot_id_ad_slots",
        "ad_plans",
        "ad_slots",
        ["slot_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.alter_column("ad_slots", "location", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_ad_plans_slot_id_ad_slots", "ad_plans", type_="foreignkey")
    op.drop_index("ix_ad_plans_slot_id", table_name="ad_plans")
    op.drop_column("ad_plans", "slot_id")
    op.alter_column("ad_slots", "width", existing_type=sa.Integer(), nullable=True)
    op.alter_column("ad_slots", "height", existing_type=sa.Integer(), nullable=True)
    op.drop_column("ad_slots", "location")
