from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from utag_api.database import new_id
from utag_api.models import (
    Conversation,
    ConversationMember,
    OrganizationUnit,
    Role,
    User,
)
from utag_api.services.chat import new_conversation_key

SYSTEM_CHAT_PREFIX = "system:"
ASSOCIATION_CHAT_KEY = f"{SYSTEM_CHAT_PREFIX}association:utag-ug"


@dataclass(frozen=True, slots=True)
class SystemChatSyncResult:
    groups_created: int = 0
    memberships_added: int = 0
    memberships_reactivated: int = 0
    memberships_removed: int = 0


def system_chat_specs(
    user: User,
    units: dict[UUID, OrganizationUnit],
) -> dict[str, str]:
    specs = {ASSOCIATION_CHAT_KEY: "UTAG UG"}
    school = units.get(user.school_id) if user.school_id else None
    if school is not None and school.unit_type == "school" and school.is_active:
        specs[f"{SYSTEM_CHAT_PREFIX}school:{school.id}"] = f"School: {school.name}"
    department = units.get(user.department_id) if user.department_id else None
    if department is not None and department.unit_type == "department" and department.is_active:
        specs[f"{SYSTEM_CHAT_PREFIX}department:{department.id}"] = f"Department: {department.name}"
    return specs


def is_system_chat(conversation: Conversation) -> bool:
    return bool(conversation.direct_key and conversation.direct_key.startswith(SYSTEM_CHAT_PREFIX))


async def sync_system_chat_groups(
    db: AsyncSession,
    users: Sequence[User],
    *,
    created_by_id: UUID | None,
) -> SystemChatSyncResult:
    unique_users = {user.id: user for user in users}
    if not unique_users:
        return SystemChatSyncResult()

    # Every synchronization takes the same row lock in PostgreSQL. This keeps
    # concurrent imports from racing to create the same managed conversation.
    await db.scalar(select(Role.id).where(Role.key == "member").with_for_update())
    await db.flush()

    eligible_users = {
        user_id: user
        for user_id, user in unique_users.items()
        if user.status in {"active", "invited"}
    }
    unit_ids = {
        unit_id
        for user in eligible_users.values()
        for unit_id in (user.school_id, user.department_id)
        if unit_id is not None
    }
    units = {
        unit.id: unit
        for unit in (
            await db.scalars(select(OrganizationUnit).where(OrganizationUnit.id.in_(unit_ids)))
        ).all()
    }
    desired_by_user = {
        user_id: system_chat_specs(user, units) if user_id in eligible_users else {}
        for user_id, user in unique_users.items()
    }
    desired_specs = {
        key: title for specs in desired_by_user.values() for key, title in specs.items()
    }

    conversations: dict[str, Conversation] = {}
    if desired_specs:
        conversations = {
            conversation.direct_key: conversation
            for conversation in (
                await db.scalars(
                    select(Conversation).where(
                        Conversation.kind == "group",
                        Conversation.direct_key.in_(desired_specs),
                    )
                )
            ).all()
            if conversation.direct_key is not None
        }
    groups_created = 0
    for key, title in desired_specs.items():
        conversation = conversations.get(key)
        if conversation is None:
            encrypted_key, key_version = new_conversation_key()
            conversation = Conversation(
                id=new_id(),
                kind="group",
                direct_key=key,
                title=title,
                created_by_id=created_by_id,
                encryption_key_ciphertext=encrypted_key,
                encryption_key_version=key_version,
            )
            db.add(conversation)
            conversations[key] = conversation
            groups_created += 1
        else:
            conversation.title = title
            conversation.is_archived = False
    await db.flush()

    existing_by_user: dict[UUID, dict[str, ConversationMember]] = {
        user_id: {} for user_id in unique_users
    }
    existing_rows = (
        await db.execute(
            select(ConversationMember, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationMember.conversation_id,
            )
            .where(
                ConversationMember.user_id.in_(unique_users),
                Conversation.kind == "group",
                Conversation.direct_key.like(f"{SYSTEM_CHAT_PREFIX}%"),
            )
        )
    ).all()
    for membership, conversation in existing_rows:
        if conversation.direct_key is not None:
            existing_by_user[membership.user_id][conversation.direct_key] = membership

    memberships_added = 0
    memberships_reactivated = 0
    memberships_removed = 0
    now = datetime.now(UTC)
    for user_id, desired in desired_by_user.items():
        existing = existing_by_user[user_id]
        for key in desired:
            membership = existing.get(key)
            if membership is None:
                db.add(
                    ConversationMember(
                        id=new_id(),
                        conversation_id=conversations[key].id,
                        user_id=user_id,
                        role="member",
                    )
                )
                memberships_added += 1
            else:
                membership.role = "member"
                if membership.left_at is not None:
                    membership.left_at = None
                    memberships_reactivated += 1

        for key, membership in existing.items():
            if key not in desired and membership.left_at is None:
                membership.left_at = now
                memberships_removed += 1

    return SystemChatSyncResult(
        groups_created=groups_created,
        memberships_added=memberships_added,
        memberships_reactivated=memberships_reactivated,
        memberships_removed=memberships_removed,
    )
