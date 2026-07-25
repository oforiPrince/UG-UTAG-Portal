from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import AuditEvent, OutboxEvent


@dataclass(slots=True)
class EventContext:
    actor_id: UUID | None
    request_id: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


def record_change(
    db: AsyncSession,
    *,
    context: EventContext,
    action: str,
    resource_type: str,
    resource_id: UUID,
    topic: str,
    payload: dict[str, object],
    changes: dict[str, object] | None = None,
    reason: str | None = None,
) -> None:
    now = datetime.now(UTC)
    db.add(
        AuditEvent(
            actor_id=context.actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=context.request_id,
            changes=changes or {},
            metadata_json=context.metadata,
            reason=reason,
            created_at=now,
        )
    )
    db.add(
        OutboxEvent(
            id=new_id(),
            event_type=action,
            topic=topic,
            aggregate_type=resource_type,
            aggregate_id=resource_id,
            payload=payload,
            created_at=now,
        )
    )
