from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import Announcement, Notification, Role, User, UserRole
from utag_api.services.events import EventContext, record_change


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
        )
        db.add(notification)
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
    return len(recipient_ids - delivered_ids)
