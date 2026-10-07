"""Add targeted member polls and frozen electorate ballots.

Revision ID: k4p5o6l7l8s9
Revises: j3c4h5a6t7e8
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "k4p5o6l7l8s9"
down_revision: str | Sequence[str] | None = "j3c4h5a6t7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POLL_PERMISSIONS = {
    "polls.manage": "Create and manage targeted member polls",
    "polls.results": "View live poll results and authorized named ballots",
    "polls.export": "Export authorized poll results",
}


def upgrade() -> None:
    op.create_table(
        "polls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("privacy", sa.String(20), nullable=False),
        sa.Column("results_visibility", sa.String(20), nullable=False),
        sa.Column("allow_vote_changes", sa.Boolean(), nullable=False),
        sa.Column("max_choices", sa.Integer(), nullable=False),
        sa.Column("audiences", sa.JSON(), nullable=False),
        sa.Column("opens_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_polls_publication_window", "polls", ["published_at", "closes_at"])
    op.create_table(
        "poll_options",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "poll_id", name="poll_option_identity"),
        sa.UniqueConstraint("poll_id", "position", name="poll_option_position"),
    )
    op.create_index("ix_poll_options_poll_id", "poll_options", ["poll_id"])
    op.create_table(
        "poll_electorate",
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["poll_id"], ["polls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("poll_id", "user_id"),
    )
    op.create_index("ix_poll_electorate_user_id", "poll_electorate", ["user_id"])
    op.create_table(
        "poll_votes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["poll_id", "user_id"],
            ["poll_electorate.poll_id", "poll_electorate.user_id"],
            name="fk_poll_votes_electorate",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "user_id", name="poll_member_vote"),
        sa.UniqueConstraint("id", "poll_id", name="poll_vote_identity"),
    )
    op.create_index("ix_poll_votes_poll_created", "poll_votes", ["poll_id", "created_at"])
    op.create_table(
        "poll_selections",
        sa.Column("vote_id", sa.Uuid(), nullable=False),
        sa.Column("option_id", sa.Uuid(), nullable=False),
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["vote_id", "poll_id"],
            ["poll_votes.id", "poll_votes.poll_id"],
            name="fk_poll_selections_vote",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["option_id", "poll_id"],
            ["poll_options.id", "poll_options.poll_id"],
            name="fk_poll_selections_option",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("vote_id", "option_id"),
    )
    op.create_index("ix_poll_selections_poll_option", "poll_selections", ["poll_id", "option_id"])
    op.create_table(
        "poll_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("poll_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("campaign", sa.String(180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["poll_id", "user_id"],
            ["poll_electorate.poll_id", "poll_electorate.user_id"],
            name="fk_poll_deliveries_electorate",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "user_id", "campaign", name="poll_delivery_campaign"),
    )
    # Grant new capability immediately on deployed databases; the normal seed
    # remains the source of truth for fresh installs and subsequent runs.
    connection = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
    )
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("key", sa.String()))
    grants = sa.table(
        "role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
    )
    for key, description in POLL_PERMISSIONS.items():
        permission_id = connection.scalar(
            sa.select(permissions.c.id).where(permissions.c.key == key)
        )
        if permission_id is None:
            permission_id = uuid5(NAMESPACE_URL, f"utag-ug:permission:{key}")
            connection.execute(
                permissions.insert().values(id=permission_id, key=key, description=description)
            )
        for role_id in connection.scalars(
            sa.select(roles.c.id).where(roles.c.key.in_(["executive", "administrator"]))
        ):
            exists = connection.scalar(
                sa.select(grants.c.role_id).where(
                    grants.c.role_id == role_id, grants.c.permission_id == permission_id
                )
            )
            if exists is None:
                connection.execute(
                    grants.insert().values(role_id=role_id, permission_id=permission_id)
                )


def downgrade() -> None:
    connection = op.get_bind()
    permissions = sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("key", sa.String()))
    permission_ids = sa.select(permissions.c.id).where(permissions.c.key.in_(POLL_PERMISSIONS))
    for name in ("role_permissions", "user_permission_grants"):
        table = sa.table(name, sa.column("permission_id", sa.Uuid()))
        connection.execute(table.delete().where(table.c.permission_id.in_(permission_ids)))
    connection.execute(permissions.delete().where(permissions.c.key.in_(POLL_PERMISSIONS)))
    for name in (
        "poll_deliveries",
        "poll_selections",
        "poll_votes",
        "poll_electorate",
        "poll_options",
        "polls",
    ):
        op.drop_table(name)
