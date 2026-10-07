"""Poll authorization, electorate resolution, ballots, and lifecycle delivery.

Ballot choices stay in ballot tables. Audit and outbox records carry only poll
invalidation metadata, including for confidential polls.
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime
from html import escape
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.dependencies import Principal
from utag_api.errors import ApiError
from utag_api.models import (
    Conversation,
    ConversationMember,
    Notification,
    OrganizationUnit,
    OutboxEvent,
    Role,
    User,
    UserRole,
)
from utag_api.models.polls import (
    Poll,
    PollDelivery,
    PollElectorate,
    PollOption,
    PollSelection,
    PollVote,
)
from utag_api.schemas.polls import (
    NamedPollVoter,
    PollAudience,
    PollOptionView,
    PollResultOption,
    PollResults,
    PollState,
    PollTimelinePoint,
    PollView,
)
from utag_api.services.events import EventContext, record_change


def utc(value: datetime) -> datetime:
    """SQLite loses timezone information; persisted times always represent UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def poll_state(poll: Poll, now: datetime | None = None) -> PollState:
    now = now or datetime.now(UTC)
    if poll.published_at is None:
        return "draft"
    if poll.closed_at is not None or (poll.closes_at and utc(poll.closes_at) <= now):
        return "closed"
    if poll.opens_at and utc(poll.opens_at) > now:
        return "scheduled"
    return "open"


def can_view_results(
    poll: Poll,
    principal: Principal,
    *,
    eligible: bool = False,
    has_voted: bool = False,
    now: datetime | None = None,
) -> bool:
    state = poll_state(poll, now)
    if state == "draft":
        return False
    if "polls.results" in principal.permissions:
        return True
    if not eligible or state == "scheduled":
        return False
    return (
        poll.results_visibility == "live"
        or (poll.results_visibility == "after_vote" and has_voted)
        or (poll.results_visibility == "after_close" and state == "closed")
    )


async def resolve_audience_ids(db: AsyncSession, audiences: list[PollAudience]) -> list[UUID]:
    """Validate selectors and resolve their union to distinct active accounts."""
    conditions = []
    for audience in audiences:
        value = audience.value or ""
        if audience.type == "all_members":
            conditions.append(User.status == "active")
        elif audience.type in {"college", "school", "department"}:
            unit_id = UUID(value)
            valid = await db.scalar(
                select(OrganizationUnit.id).where(
                    OrganizationUnit.id == unit_id,
                    OrganizationUnit.unit_type == audience.type,
                    OrganizationUnit.is_active.is_(True),
                )
            )
            if valid is None:
                raise ApiError(422, "invalid_poll_audience", "Choose an active organization unit")
            conditions.append(getattr(User, f"{audience.type}_id") == unit_id)
        elif audience.type == "role":
            role_id = await db.scalar(select(Role.id).where(Role.key == value))
            if role_id is None:
                raise ApiError(422, "invalid_poll_audience", "Choose a valid member role")
            conditions.append(
                User.id.in_(select(UserRole.user_id).where(UserRole.role_id == role_id))
            )
        elif audience.type == "chat_group":
            group_id = UUID(value)
            valid = await db.scalar(
                select(Conversation.id).where(
                    Conversation.id == group_id,
                    Conversation.kind == "group",
                    Conversation.is_archived.is_(False),
                )
            )
            if valid is None:
                raise ApiError(422, "invalid_poll_audience", "Choose an active chat group")
            conditions.append(
                User.id.in_(
                    select(ConversationMember.user_id).where(
                        ConversationMember.conversation_id == group_id,
                        ConversationMember.left_at.is_(None),
                    )
                )
            )
        else:
            user_id = UUID(value)
            valid = await db.scalar(
                select(User.id).where(User.id == user_id, User.status == "active")
            )
            if valid is None:
                raise ApiError(422, "invalid_poll_audience", "Choose an active member")
            conditions.append(User.id == user_id)
    if not conditions:
        raise ApiError(422, "invalid_poll_audience", "Choose at least one target audience")
    return list(
        (
            await db.scalars(
                select(User.id).where(User.status == "active", or_(*conditions)).order_by(User.id)
            )
        ).all()
    )


async def active_recipient_ids(db: AsyncSession, poll_id: UUID) -> list[UUID]:
    """Frozen electorate members whose accounts still permit participation."""
    return list(
        (
            await db.scalars(
                select(PollElectorate.user_id)
                .join(User, User.id == PollElectorate.user_id)
                .where(PollElectorate.poll_id == poll_id, User.status == "active")
                .order_by(PollElectorate.user_id)
            )
        ).all()
    )


async def eligible_member(db: AsyncSession, poll_id: UUID, user_id: UUID) -> bool:
    return await db.get(PollElectorate, (poll_id, user_id)) is not None


async def get_vote(db: AsyncSession, poll_id: UUID, user_id: UUID) -> PollVote | None:
    vote: PollVote | None = await db.scalar(
        select(PollVote).where(PollVote.poll_id == poll_id, PollVote.user_id == user_id)
    )
    return vote


async def poll_options(db: AsyncSession, poll_id: UUID) -> list[PollOption]:
    return list(
        (
            await db.scalars(
                select(PollOption)
                .where(PollOption.poll_id == poll_id)
                .order_by(PollOption.position)
            )
        ).all()
    )


async def poll_view(db: AsyncSession, poll: Poll, principal: Principal) -> PollView:
    return (await poll_views(db, [poll], principal))[0]


async def poll_views(db: AsyncSession, items: list[Poll], principal: Principal) -> list[PollView]:
    """Batch participant state for a page without querying once per published poll."""
    if not items:
        return []
    now = datetime.now(UTC)
    poll_ids = [poll.id for poll in items]
    eligible_ids = set(
        (
            await db.scalars(
                select(PollElectorate.poll_id).where(
                    PollElectorate.poll_id.in_(poll_ids),
                    PollElectorate.user_id == principal.user.id,
                )
            )
        ).all()
    )
    vote_rows = (
        await db.scalars(
            select(PollVote).where(
                PollVote.poll_id.in_(poll_ids), PollVote.user_id == principal.user.id
            )
        )
    ).all()
    votes = {vote.poll_id: vote for vote in vote_rows}
    selections: dict[UUID, list[UUID]] = defaultdict(list)
    if vote_rows:
        for vote_id, option_id in (
            await db.execute(
                select(PollSelection.vote_id, PollSelection.option_id)
                .join(PollOption, PollOption.id == PollSelection.option_id)
                .where(PollSelection.vote_id.in_([vote.id for vote in vote_rows]))
                .order_by(PollOption.position)
            )
        ).all():
            selections[vote_id].append(option_id)
    options: dict[UUID, list[PollOption]] = defaultdict(list)
    for option in (
        await db.scalars(
            select(PollOption).where(PollOption.poll_id.in_(poll_ids)).order_by(PollOption.position)
        )
    ).all():
        options[option.poll_id].append(option)
    counts = {
        poll_id: count
        for poll_id, count in (
            await db.execute(
                select(PollElectorate.poll_id, func.count())
                .where(PollElectorate.poll_id.in_(poll_ids))
                .group_by(PollElectorate.poll_id)
            )
        ).all()
    }
    active = await db.scalar(select(User.status).where(User.id == principal.user.id)) == "active"
    views = []
    for poll in items:
        eligible = poll.id in eligible_ids
        vote = votes.get(poll.id)
        eligible_count = counts.get(poll.id, 0)
        audiences = [PollAudience.model_validate(item) for item in poll.audiences]
        if poll.published_at is None:
            # Draft preview reflects the current roster; publication freezes it.
            try:
                eligible_count = len(await resolve_audience_ids(db, audiences))
            except ApiError:
                eligible_count = 0
        results_allowed = can_view_results(
            poll, principal, eligible=eligible, has_voted=vote is not None, now=now
        )
        views.append(
            PollView(
                id=poll.id,
                title=poll.title,
                question=poll.question,
                description=poll.description,
                kind=poll.kind,
                privacy=poll.privacy,
                results_visibility=poll.results_visibility,
                allow_vote_changes=poll.allow_vote_changes,
                max_choices=poll.max_choices,
                opens_at=utc(poll.opens_at) if poll.opens_at else None,
                closes_at=utc(poll.closes_at) if poll.closes_at else None,
                closed_at=utc(poll.closed_at) if poll.closed_at else None,
                audiences=audiences,
                options=[PollOptionView.model_validate(option) for option in options[poll.id]],
                status=poll_state(poll, now),
                published_at=utc(poll.published_at) if poll.published_at else None,
                eligible_count=eligible_count,
                has_voted=vote is not None,
                my_vote=selections[vote.id] if vote else None,
                can_vote=(
                    active
                    and eligible
                    and poll_state(poll, now) == "open"
                    and (vote is None or poll.allow_vote_changes)
                ),
                can_manage="polls.manage" in principal.permissions,
                can_view_results=results_allowed,
                can_export="polls.export" in principal.permissions and results_allowed,
                created_at=utc(poll.created_at),
                version=poll.version,
                server_now=now,
            )
        )
    return views


def emit_poll_change(
    db: AsyncSession,
    poll: Poll,
    context: EventContext,
    action: str,
    *,
    reason: str | None = None,
    changes: dict[str, object] | None = None,
) -> None:
    record_change(
        db,
        context=context,
        action=action,
        resource_type="poll",
        resource_id=poll.id,
        topic="polls:management",
        payload={"poll_id": str(poll.id), "version": poll.version, "status": poll_state(poll)},
        reason=reason,
        changes=changes,
    )


def _invalidate_results(db: AsyncSession, poll: Poll) -> None:
    db.add(
        OutboxEvent(
            id=new_id(),
            event_type="poll.results.changed",
            topic=f"poll:{poll.id}:results",
            aggregate_type="poll",
            aggregate_id=poll.id,
            payload={"poll_id": str(poll.id)},
            created_at=datetime.now(UTC),
        )
    )


async def emit_electorate_change(db: AsyncSession, poll: Poll, action: str) -> None:
    for user_id in await active_recipient_ids(db, poll.id):
        db.add(
            OutboxEvent(
                id=new_id(),
                event_type=action,
                topic=f"user:{user_id}",
                aggregate_type="poll",
                aggregate_id=poll.id,
                payload={
                    "poll_id": str(poll.id),
                    "version": poll.version,
                    "status": poll_state(poll),
                },
                created_at=datetime.now(UTC),
            )
        )


async def cast_vote(
    db: AsyncSession,
    poll: Poll,
    principal: Principal,
    option_ids: list[UUID],
    context: EventContext,
) -> None:
    """Caller holds the poll lock through commit, including close/extend races."""
    now = datetime.now(UTC)
    # Refresh from the database after acquiring the poll lock, not from the session identity.
    active = await db.scalar(select(User.status).where(User.id == principal.user.id)) == "active"
    if not active or not await eligible_member(db, poll.id, principal.user.id):
        raise ApiError(403, "poll_not_eligible", "You are not eligible to vote in this poll")
    valid_ids = {option.id for option in await poll_options(db, poll.id)}
    if (
        not option_ids
        or len(set(option_ids)) != len(option_ids)
        or not set(option_ids) <= valid_ids
    ):
        raise ApiError(422, "invalid_poll_options", "Choose valid options from this poll")
    if len(option_ids) > poll.max_choices:
        raise ApiError(422, "too_many_poll_choices", f"Choose at most {poll.max_choices} option(s)")
    vote = await get_vote(db, poll.id, principal.user.id)
    if vote:
        previous = set(
            (
                await db.scalars(
                    select(PollSelection.option_id).where(PollSelection.vote_id == vote.id)
                )
            ).all()
        )
        if previous == set(option_ids):
            # A lost successful response remains safely retryable after closure.
            return
        if poll_state(poll, now) != "open":
            raise ApiError(409, "poll_not_open", "This poll is not accepting votes")
        if not poll.allow_vote_changes:
            raise ApiError(
                409, "poll_vote_final", "Your vote has already been recorded and is final"
            )
        await db.execute(delete(PollSelection).where(PollSelection.vote_id == vote.id))
        vote.updated_at = now
    else:
        if poll_state(poll, now) != "open":
            raise ApiError(409, "poll_not_open", "This poll is not accepting votes")
        vote = PollVote(id=new_id(), poll_id=poll.id, user_id=principal.user.id, created_at=now)
        db.add(vote)
        await db.flush()
    for option_id in option_ids:
        db.add(PollSelection(vote_id=vote.id, poll_id=poll.id, option_id=option_id))
    emit_poll_change(db, poll, context, "poll.vote.recorded")
    _invalidate_results(db, poll)


async def results_view(db: AsyncSession, poll: Poll, principal: Principal) -> PollResults:
    # A shared poll lock keeps all aggregate queries on one committed ballot
    # state while concurrent casts, deadline extensions, and closes queue.
    locked = await db.scalar(
        select(Poll)
        .where(Poll.id == poll.id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise ApiError(404, "poll_not_found", "Poll not found")
    poll = locked
    eligible = await eligible_member(db, poll.id, principal.user.id)
    vote = await get_vote(db, poll.id, principal.user.id)
    if not can_view_results(poll, principal, eligible=eligible, has_voted=vote is not None):
        raise ApiError(403, "poll_results_hidden", "Results are not available to you yet")
    options = await poll_options(db, poll.id)
    response_count = int(
        await db.scalar(select(func.count(PollVote.id)).where(PollVote.poll_id == poll.id)) or 0
    )
    eligible_count = int(
        await db.scalar(
            select(func.count())
            .select_from(PollElectorate)
            .where(PollElectorate.poll_id == poll.id)
        )
        or 0
    )
    counts: dict[UUID, int] = {
        option_id: count
        for option_id, count in (
            await db.execute(
                select(PollSelection.option_id, func.count())
                .where(PollSelection.poll_id == poll.id)
                .group_by(PollSelection.option_id)
            )
        ).all()
    }
    times = (await db.scalars(select(PollVote.created_at).where(PollVote.poll_id == poll.id))).all()
    timeline = Counter(utc(at).replace(minute=0, second=0, microsecond=0) for at in times)
    named_voters = None
    if poll.privacy == "named" and "polls.results" in principal.permissions:
        rows = (
            await db.execute(
                select(User, PollOption.label)
                .join(PollVote, PollVote.user_id == User.id)
                .join(PollSelection, PollSelection.vote_id == PollVote.id)
                .join(PollOption, PollOption.id == PollSelection.option_id)
                .where(PollVote.poll_id == poll.id)
                .order_by(User.surname, User.other_name, User.id, PollOption.position)
            )
        ).all()
        members: dict[UUID, NamedPollVoter] = {}
        for member, label in rows:
            members.setdefault(
                member.id, NamedPollVoter(member_name=member.full_name, option_labels=[])
            ).option_labels.append(label)
        named_voters = list(members.values())
    return PollResults(
        response_count=response_count,
        eligible_count=eligible_count,
        turnout_percent=round(response_count * 100 / eligible_count, 2) if eligible_count else 0,
        options=[
            PollResultOption(
                id=option.id,
                label=option.label,
                position=option.position,
                votes=counts.get(option.id, 0),
                percent=round(counts.get(option.id, 0) * 100 / response_count, 2)
                if response_count
                else 0,
            )
            for option in options
        ],
        timeline=[
            PollTimelinePoint(at=at, responses=responses)
            for at, responses in sorted(timeline.items())
        ],
        generated_at=datetime.now(UTC),
        named_voters=named_voters,
    )


async def authorized_poll_topics(db: AsyncSession, principal: Principal) -> list[str]:
    # Managers receive every invalidation on one topic, so subscriptions do
    # not accumulate with historical polls.
    if {"polls.manage", "polls.results"} & principal.permissions:
        return ["polls:management"]
    now = datetime.now(UTC)
    polls = (
        await db.scalars(
            select(Poll)
            .join(PollElectorate, PollElectorate.poll_id == Poll.id)
            .where(
                PollElectorate.user_id == principal.user.id,
                Poll.published_at.is_not(None),
                Poll.closed_at.is_(None),
                Poll.closes_at > now,
                or_(Poll.opens_at.is_(None), Poll.opens_at <= now),
            )
        )
    ).all()
    if not polls:
        return []
    voted_ids = set(
        (
            await db.scalars(
                select(PollVote.poll_id).where(
                    PollVote.user_id == principal.user.id,
                    PollVote.poll_id.in_([poll.id for poll in polls]),
                )
            )
        ).all()
    )
    topics = set()
    for poll in polls:
        if can_view_results(
            poll, principal, eligible=True, has_voted=poll.id in voted_ids, now=now
        ):
            topics.add(f"poll:{poll.id}:results")
    return sorted(topics)


async def nonvoter_ids(db: AsyncSession, poll: Poll) -> list[UUID]:
    if poll_state(poll) != "open":
        raise ApiError(409, "poll_not_open", "Reminders are available only while voting is open")
    voted = set(
        (await db.scalars(select(PollVote.user_id).where(PollVote.poll_id == poll.id))).all()
    )
    return [user_id for user_id in await active_recipient_ids(db, poll.id) if user_id not in voted]


async def deliver_poll_notifications(
    db: AsyncSession,
    poll: Poll,
    recipients: list[UUID],
    campaign: str,
    *,
    title: str,
    context: EventContext,
) -> int:
    delivered = set(
        (
            await db.scalars(
                select(PollDelivery.user_id).where(
                    PollDelivery.poll_id == poll.id, PollDelivery.campaign == campaign
                )
            )
        ).all()
    )
    for user_id in set(recipients) - delivered:
        now = datetime.now(UTC)
        notification = Notification(
            id=new_id(),
            user_id=user_id,
            category="poll",
            priority="high" if campaign.startswith("reminder:") else "normal",
            title=title[:300],
            body=f"<p>{escape(poll.question)}</p>",
            resource_type="poll",
            resource_id=poll.id,
            deep_link=f"/dashboard/polls/{poll.id}",
        )
        db.add(notification)
        db.add(
            PollDelivery(
                id=new_id(), poll_id=poll.id, user_id=user_id, campaign=campaign, created_at=now
            )
        )
        record_change(
            db,
            context=context,
            action="notification.created",
            resource_type="notification",
            resource_id=notification.id,
            topic=f"user:{user_id}",
            payload={
                "notification_id": str(notification.id),
                "category": "poll",
                "poll_id": str(poll.id),
            },
        )
    return len(set(recipients) - delivered)


async def reconcile_one_poll(db: AsyncSession, poll: Poll) -> bool:
    """Called under the poll lock; markers and deliveries commit atomically."""
    state = poll_state(poll)
    context = EventContext(actor_id=None, request_id=None)
    if state == "open" and poll.opened_notified_at is None:
        poll.opened_notified_at = datetime.now(UTC)
        await deliver_poll_notifications(
            db,
            poll,
            await active_recipient_ids(db, poll.id),
            "lifecycle:open",
            title=f"Voting is open: {poll.title}",
            context=context,
        )
        emit_poll_change(db, poll, context, "poll.opened")
        await emit_electorate_change(db, poll, "poll.opened")
        return True
    if state == "closed" and poll.closed_notified_at is None:
        poll.closed_notified_at = datetime.now(UTC)
        await deliver_poll_notifications(
            db,
            poll,
            await active_recipient_ids(db, poll.id),
            "lifecycle:closed",
            title=f"Voting has closed: {poll.title}",
            context=context,
        )
        emit_poll_change(db, poll, context, "poll.closed")
        await emit_electorate_change(db, poll, "poll.closed")
        _invalidate_results(db, poll)
        return True
    return False


async def reconcile_poll_lifecycle(db: AsyncSession) -> int:
    now = datetime.now(UTC)
    polls = (
        await db.scalars(
            select(Poll)
            .where(
                Poll.published_at.is_not(None),
                or_(
                    (Poll.opened_notified_at.is_(None))
                    & (Poll.closed_at.is_(None))
                    & (Poll.closes_at > now)
                    & ((Poll.opens_at.is_(None)) | (Poll.opens_at <= now)),
                    (Poll.closed_notified_at.is_(None))
                    & ((Poll.closed_at.is_not(None)) | (Poll.closes_at <= now)),
                ),
            )
            .with_for_update(skip_locked=True)
        )
    ).all()
    changed = 0
    for poll in polls:
        changed += int(await reconcile_one_poll(db, poll))
    return changed
