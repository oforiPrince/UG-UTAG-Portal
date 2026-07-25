from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from utag_api.dependencies import DbSession, Principal, require_permissions
from utag_api.models import (
    Article,
    AuditEvent,
    Document,
    Event,
    EventRegistration,
    Notification,
    User,
)
from utag_api.routers.auth import current_executive_appointment, summarize_executive_profile
from utag_api.routers.documents import audiences_allow
from utag_api.schemas.domain import (
    DashboardMetric,
    DashboardOverview,
    EventView,
    NotificationView,
    PulsePoint,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def event_view(item: Event, registrations: int = 0, registered: bool = False) -> EventView:
    return EventView(
        **{key: value for key, value in item.__dict__.items() if not key.startswith("_")},
        registrations=registrations,
        registered=registered,
    )


@router.get("/overview", response_model=DashboardOverview)
async def overview(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("dashboard.view"))],
) -> DashboardOverview:
    now = datetime.now(UTC)
    permissions = principal.permissions
    can_manage_events = "events.manage" in permissions
    can_view_activity = "audit.view" in permissions
    can_view_pulse = can_view_activity or "analytics.view" in permissions
    sections = ["events", "notifications"]
    metrics: list[DashboardMetric] = []

    if "members.view" in permissions:
        member_count = int(
            (await db.scalar(select(func.count(User.id)).where(User.status == "active"))) or 0
        )
        metrics.append(DashboardMetric(key="members", label="Active members", value=member_count))
        sections.append("members")

    if "documents.view" in permissions:
        if "documents.manage" in permissions:
            document_count = int(
                (
                    await db.scalar(
                        select(func.count(Document.id)).where(Document.status != "archived")
                    )
                )
                or 0
            )
            document_label = "Knowledge records"
        else:
            # Audience rules live in JSON, so authorization is applied per record.
            audience_rows = (
                await db.scalars(select(Document.audiences).where(Document.status != "archived"))
            ).all()
            document_count = sum(
                1 for audiences in audience_rows if audiences_allow(audiences, principal)
            )
            document_label = "Available documents"
        metrics.append(
            DashboardMetric(key="documents", label=document_label, value=document_count)
        )
        sections.append("documents")

    event_filters = (
        Event.start_date >= now.date(),
        Event.status.in_(["upcoming", "ongoing"]),
    )
    event_count_statement = select(func.count(Event.id)).where(*event_filters)
    event_statement = select(Event).where(*event_filters)
    if not can_manage_events:
        event_count_statement = event_count_statement.where(
            Event.publication_status == "published"
        )
        event_statement = event_statement.where(Event.publication_status == "published")
    upcoming_count = int((await db.scalar(event_count_statement)) or 0)
    metrics.append(DashboardMetric(key="events", label="Upcoming events", value=upcoming_count))

    unread_count = int(
        (
            await db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.user_id == principal.user.id,
                    Notification.read_at.is_(None),
                    Notification.archived_at.is_(None),
                )
            )
        )
        or 0
    )
    metrics.append(DashboardMetric(key="unread", label="Unread updates", value=unread_count))

    upcoming = (
        await db.scalars(event_statement.order_by(Event.start_date, Event.start_time).limit(4))
    ).all()
    event_ids = [item.id for item in upcoming]
    count_rows = (
        (
            await db.execute(
                select(EventRegistration.event_id, func.count(EventRegistration.id))
                .where(
                    EventRegistration.event_id.in_(event_ids),
                    EventRegistration.status != "cancelled",
                )
                .group_by(EventRegistration.event_id)
            )
        ).all()
        if event_ids
        else []
    )
    counts: dict[UUID, int] = {event_id: count for event_id, count in count_rows}
    registered_ids = (
        set(
            (
                await db.scalars(
                    select(EventRegistration.event_id).where(
                        EventRegistration.event_id.in_(event_ids),
                        EventRegistration.user_id == principal.user.id,
                        EventRegistration.status != "cancelled",
                    )
                )
            ).all()
        )
        if event_ids
        else set()
    )
    notifications = (
        await db.scalars(
            select(Notification)
            .where(Notification.user_id == principal.user.id)
            .order_by(Notification.created_at.desc())
            .limit(6)
        )
    ).all()

    recent_activity: list[dict[str, Any]] = []
    if can_view_activity:
        activity_rows = (
            await db.execute(
                select(AuditEvent, User)
                .outerjoin(User, User.id == AuditEvent.actor_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(10)
            )
        ).all()
        recent_activity = [
            {
                "id": audit.id,
                "action": audit.action,
                "resource_type": audit.resource_type,
                "resource_id": audit.resource_id,
                "created_at": audit.created_at,
                "actor_name": user.full_name if user else "System",
            }
            for audit, user in activity_rows
        ]
        sections.append("activity")

    pulse_points: list[PulsePoint] = []
    if can_view_pulse:
        since = now - timedelta(days=13)
        pulse_rows = (
            await db.scalars(
                select(AuditEvent)
                .where(AuditEvent.created_at >= since)
                .order_by(AuditEvent.created_at)
            )
        ).all()
        pulse: dict[date, dict[str, int]] = defaultdict(
            lambda: {"engagement": 0, "events": 0, "publications": 0}
        )
        for offset in range(14):
            pulse[(since + timedelta(days=offset)).date()]
        for event in pulse_rows:
            bucket = pulse[event.created_at.date()]
            bucket["engagement"] += 1
            if event.resource_type in {"event", "event_registration"}:
                bucket["events"] += 1
            if event.resource_type in {"article", "announcement", "document"}:
                bucket["publications"] += 1
        pulse_points = [PulsePoint(at=day, **values) for day, values in sorted(pulse.items())]
        sections.append("pulse")

    appointment = await current_executive_appointment(db, principal.user.id)

    return DashboardOverview(
        generated_at=now,
        metrics=metrics,
        pulse=pulse_points,
        upcoming_events=[
            event_view(item, counts.get(item.id, 0), item.id in registered_ids)
            for item in upcoming
        ],
        recent_notifications=[NotificationView.model_validate(item) for item in notifications],
        recent_activity=recent_activity,
        sections=sections,
        executive_appointment=(
            summarize_executive_profile(appointment) if appointment is not None else None
        ),
    )


@router.get("/analytics")
async def analytics(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("analytics.view"))],
) -> dict[str, Any]:
    now = datetime.now(UTC)
    thirty_days_ago = now - timedelta(days=30)
    return {
        "generated_at": now,
        "members": {
            "total": int((await db.scalar(select(func.count(User.id)))) or 0),
            "active": int(
                (await db.scalar(select(func.count(User.id)).where(User.status == "active"))) or 0
            ),
            "new_30_days": int(
                (
                    await db.scalar(
                        select(func.count(User.id)).where(User.created_at >= thirty_days_ago)
                    )
                )
                or 0
            ),
        },
        "content": {
            "published_articles": int(
                (
                    await db.scalar(
                        select(func.count(Article.id)).where(Article.status == "published")
                    )
                )
                or 0
            ),
            "documents": int((await db.scalar(select(func.count(Document.id)))) or 0),
        },
        "events": {
            "total": int((await db.scalar(select(func.count(Event.id)))) or 0),
            "registrations": int((await db.scalar(select(func.count(EventRegistration.id)))) or 0),
        },
    }
