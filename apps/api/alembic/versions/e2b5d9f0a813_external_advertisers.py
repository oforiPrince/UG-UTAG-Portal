"""External advertisers as commercial ad clients.

Revision ID: e2b5d9f0a813
Revises: d1a4c8e9f702
Create Date: 2026-08-02
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "e2b5d9f0a813"
down_revision: str | Sequence[str] | None = "d1a4c8e9f702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ad_advertisers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_name", sa.String(length=200), nullable=False),
        sa.Column("contact_name", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("website", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("member_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["member_user_id"],
            ["users.id"],
            name="fk_ad_advertisers_member_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ad_advertisers"),
    )
    op.create_index("ix_ad_advertisers_email", "ad_advertisers", ["email"])
    op.create_index("ix_ad_advertisers_member_user_id", "ad_advertisers", ["member_user_id"])

    op.add_column("ad_orders", sa.Column("advertiser_id", sa.Uuid(), nullable=True))

    conn = op.get_bind()
    now = datetime.now(UTC)
    orders = conn.execute(
        sa.text("SELECT id, user_id FROM ad_orders WHERE advertiser_id IS NULL")
    ).mappings()
    advertiser_by_user: dict[str, str] = {}
    for row in orders:
        user_id = str(row["user_id"])
        if user_id not in advertiser_by_user:
            user = conn.execute(
                sa.text(
                    """
                    SELECT email, other_name, surname, title
                    FROM users WHERE id = :user_id
                    """
                ),
                {"user_id": row["user_id"]},
            ).mappings().first()
            email = (user["email"] if user else None) or f"legacy-{user_id[:8]}@advertiser.local"
            parts = []
            if user:
                if user.get("title"):
                    parts.append(str(user["title"]))
                if user.get("other_name"):
                    parts.append(str(user["other_name"]))
                if user.get("surname"):
                    parts.append(str(user["surname"]))
            contact = " ".join(parts).strip() or email
            advertiser_id = str(uuid4())
            conn.execute(
                sa.text(
                    """
                    INSERT INTO ad_advertisers (
                        id, organization_name, contact_name, email, phone, website, notes,
                        is_active, member_user_id, created_at, updated_at
                    ) VALUES (
                        :id, :organization_name, :contact_name, :email, '', NULL, '',
                        true, :member_user_id, :now, :now
                    )
                    """
                ),
                {
                    "id": advertiser_id,
                    "organization_name": contact,
                    "contact_name": contact,
                    "email": email,
                    "member_user_id": row["user_id"],
                    "now": now,
                },
            )
            advertiser_by_user[user_id] = advertiser_id
        conn.execute(
            sa.text("UPDATE ad_orders SET advertiser_id = :advertiser_id WHERE id = :id"),
            {"advertiser_id": advertiser_by_user[user_id], "id": row["id"]},
        )

    # Any remaining rows without a user mapping get a placeholder client.
    orphan = conn.execute(
        sa.text("SELECT id FROM ad_orders WHERE advertiser_id IS NULL")
    ).scalars().all()
    if orphan:
        placeholder_id = str(uuid4())
        conn.execute(
            sa.text(
                """
                INSERT INTO ad_advertisers (
                    id, organization_name, contact_name, email, phone, website, notes,
                    is_active, member_user_id, created_at, updated_at
                ) VALUES (
                    :id, 'Migrated advertiser', 'Migrated advertiser',
                    'migrated@advertiser.local', '', NULL, '', true, NULL, :now, :now
                )
                """
            ),
            {"id": placeholder_id, "now": now},
        )
        conn.execute(
            sa.text(
                "UPDATE ad_orders SET advertiser_id = :advertiser_id WHERE advertiser_id IS NULL"
            ),
            {"advertiser_id": placeholder_id},
        )

    op.alter_column("ad_orders", "advertiser_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index("ix_ad_orders_advertiser_id", "ad_orders", ["advertiser_id"])
    op.create_foreign_key(
        "fk_ad_orders_advertiser_id_ad_advertisers",
        "ad_orders",
        "ad_advertisers",
        ["advertiser_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(op.f("fk_ad_orders_user_id_users"), "ad_orders", type_="foreignkey")
    op.drop_index(op.f("ix_ad_orders_user_id"), table_name="ad_orders")
    op.drop_column("ad_orders", "user_id")
    op.alter_column("ad_advertisers", "contact_name", server_default=None)
    op.alter_column("ad_advertisers", "phone", server_default=None)
    op.alter_column("ad_advertisers", "notes", server_default=None)
    op.alter_column("ad_advertisers", "is_active", server_default=None)


def downgrade() -> None:
    op.add_column("ad_orders", sa.Column("user_id", sa.Uuid(), nullable=True))
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE ad_orders AS orders
            SET user_id = advertisers.member_user_id
            FROM ad_advertisers AS advertisers
            WHERE advertisers.id = orders.advertiser_id
            """
        )
    )
    # Fallback for advertisers without a linked member.
    admin = conn.execute(sa.text("SELECT id FROM users ORDER BY created_at LIMIT 1")).scalar()
    if admin is not None:
        conn.execute(
            sa.text("UPDATE ad_orders SET user_id = :user_id WHERE user_id IS NULL"),
            {"user_id": admin},
        )
    op.alter_column("ad_orders", "user_id", existing_type=sa.Uuid(), nullable=False)
    op.create_index(op.f("ix_ad_orders_user_id"), "ad_orders", ["user_id"])
    op.create_foreign_key(
        op.f("fk_ad_orders_user_id_users"),
        "ad_orders",
        "users",
        ["user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        "fk_ad_orders_advertiser_id_ad_advertisers", "ad_orders", type_="foreignkey"
    )
    op.drop_index("ix_ad_orders_advertiser_id", table_name="ad_orders")
    op.drop_column("ad_orders", "advertiser_id")
    op.drop_index("ix_ad_advertisers_member_user_id", table_name="ad_advertisers")
    op.drop_index("ix_ad_advertisers_email", table_name="ad_advertisers")
    op.drop_table("ad_advertisers")
