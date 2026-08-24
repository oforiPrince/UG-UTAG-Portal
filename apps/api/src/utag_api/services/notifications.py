from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import Announcement, BackgroundJob, Notification, Role, User, UserRole
from utag_api.services.delivery import email_delivery_enabled
from utag_api.services.events import EventContext, enqueue_task, record_change

MAX_NOTIFICATION_EMAIL_JOB_RECIPIENTS = 5_000


def enqueue_notification_email_jobs(
    db: AsyncSession,
    notification_ids: list[UUID],
    *,
    owner_id: UUID | None,
    kind: str,
) -> list[UUID]:
    if not notification_ids or not email_delivery_enabled():
        return []
    if kind not in {"email.announcement", "email.notification"}:
        raise ValueError("Unsupported notification email job kind")
    job_ids: list[UUID] = []
    for offset in range(0, len(notification_ids), MAX_NOTIFICATION_EMAIL_JOB_RECIPIENTS):
        chunk = notification_ids[offset : offset + MAX_NOTIFICATION_EMAIL_JOB_RECIPIENTS]
        job = BackgroundJob(
            id=new_id(),
            owner_id=owner_id,
            kind=kind,
            status="queued",
            input_json={"notification_ids": [str(item) for item in chunk]},
        )
        db.add(job)
        job_ids.append(job.id)
        enqueue_task(
            db,
            task_name="utag.email.notification_batch",
            aggregate_type="background_job",
            aggregate_id=job.id,
            args=[str(job.id)],
            queue="communications",
        )
    return job_ids


def _announcement_role_audiences(announcement: Announcement) -> set[str] | None:
    """Return targeted role keys, or None when every active user is targeted."""
    if not announcement.audiences:
        return None

    roles: set[str] = set()
    for audience in announcement.audiences:
        audience_type = audience.get("type")
        if audience_type in {"everyone", "all_members"}:
            return None
        if audience_type == "role" and audience.get("value"):
            roles.add(audience["value"])
    return roles


async def deliver_announcement_notifications(
    db: AsyncSession,
    announcement: Announcement,
    *,
    context: EventContext,
) -> int:
    """Create one durable inbox delivery per eligible user, without duplicates."""
    role_keys = _announcement_role_audiences(announcement)
    recipients = select(User.id).where(User.status == "active")
    if role_keys is not None:
        if not role_keys:
            return 0
        recipients = (
            recipients.join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.key.in_(role_keys))
            .distinct()
        )

    recipient_ids = set((await db.scalars(recipients)).all())
    if not recipient_ids:
        return 0

    delivered_ids = set(
        (
            await db.scalars(
                select(Notification.user_id).where(
                    Notification.user_id.in_(recipient_ids),
                    Notification.resource_type == "announcement",
                    Notification.resource_id == announcement.id,
                )
            )
        ).all()
    )

    notification_ids: list[UUID] = []
    for user_id in recipient_ids - delivered_ids:
        notification = Notification(
            id=new_id(),
            user_id=user_id,
            category="announcement",
            priority=announcement.priority,
            title=announcement.title,
            body=announcement.content_html,
            resource_type="announcement",
            resource_id=announcement.id,
            deep_link="/dashboard/announcements",
        )
        db.add(notification)
        notification_ids.append(notification.id)
        record_change(
            db,
            context=context,
            action="notification.created",
            resource_type="notification",
            resource_id=notification.id,
            topic=f"user:{user_id}",
            payload={
                "notification_id": str(notification.id),
                "category": "announcement",
                "priority": notification.priority,
                "announcement_id": str(announcement.id),
            },
        )
    enqueue_notification_email_jobs(
        db,
        notification_ids,
        owner_id=context.actor_id,
        kind="email.announcement",
    )
    return len(notification_ids)
