"""Member polls with a frozen electorate and durable ballots."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from utag_api.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Poll(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "polls"
    __table_args__ = (Index("ix_polls_publication_window", "published_at", "closes_at"),)

    title: Mapped[str] = mapped_column(String(250))
    question: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    kind: Mapped[str] = mapped_column(String(20), default="single")
    privacy: Mapped[str] = mapped_column(String(20), default="confidential")
    results_visibility: Mapped[str] = mapped_column(String(20), default="after_close")
    allow_vote_changes: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_choices: Mapped[int] = mapped_column(Integer, default=1)
    audiences: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PollOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "poll_options"
    __table_args__ = (
        UniqueConstraint("id", "poll_id", name="poll_option_identity"),
        UniqueConstraint("poll_id", "position", name="poll_option_position"),
    )

    poll_id: Mapped[UUID] = mapped_column(ForeignKey("polls.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer)


class PollElectorate(Base):
    __tablename__ = "poll_electorate"

    poll_id: Mapped[UUID] = mapped_column(
        ForeignKey("polls.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True, index=True
    )


class PollVote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "poll_votes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["poll_id", "user_id"],
            ["poll_electorate.poll_id", "poll_electorate.user_id"],
            ondelete="RESTRICT",
            name="fk_poll_votes_electorate",
        ),
        UniqueConstraint("poll_id", "user_id", name="poll_member_vote"),
        UniqueConstraint("id", "poll_id", name="poll_vote_identity"),
        Index("ix_poll_votes_poll_created", "poll_id", "created_at"),
    )

    poll_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)


class PollSelection(Base):
    __tablename__ = "poll_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["vote_id", "poll_id"],
            ["poll_votes.id", "poll_votes.poll_id"],
            ondelete="CASCADE",
            name="fk_poll_selections_vote",
        ),
        ForeignKeyConstraint(
            ["option_id", "poll_id"],
            ["poll_options.id", "poll_options.poll_id"],
            ondelete="RESTRICT",
            name="fk_poll_selections_option",
        ),
        Index("ix_poll_selections_poll_option", "poll_id", "option_id"),
    )

    vote_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    option_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    poll_id: Mapped[UUID] = mapped_column(Uuid)


class PollDelivery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "poll_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["poll_id", "user_id"],
            ["poll_electorate.poll_id", "poll_electorate.user_id"],
            ondelete="CASCADE",
            name="fk_poll_deliveries_electorate",
        ),
        UniqueConstraint("poll_id", "user_id", "campaign", name="poll_delivery_campaign"),
    )

    poll_id: Mapped[UUID] = mapped_column(Uuid)
    user_id: Mapped[UUID] = mapped_column(Uuid)
    campaign: Mapped[str] = mapped_column(String(180))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
