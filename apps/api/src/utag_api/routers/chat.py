import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased
from starlette.concurrency import run_in_threadpool

from utag_api.config import get_settings
from utag_api.database import new_id
from utag_api.dependencies import (
    DbSession,
    Principal,
    event_context,
    require_mutation_permissions,
    require_permissions,
)
from utag_api.errors import ApiError
from utag_api.models import (
    Conversation,
    ConversationInvite,
    ConversationMember,
    MediaAsset,
    Message,
    MessageAttachment,
    MessageReceipt,
    User,
)
from utag_api.schemas.common import MessageResponse, Page
from utag_api.schemas.domain import (
    ConversationCreate,
    ConversationInviteCreate,
    ConversationInviteView,
    ConversationMemberRoleUpdate,
    ConversationMembersUpdate,
    ConversationOwnershipTransfer,
    ConversationPreferenceUpdate,
    ConversationUpdate,
    ConversationView,
    MediaView,
    MessageAttachmentView,
    MessageCreateRequest,
    MessageReplyView,
    MessageUpdateRequest,
    MessageView,
)
from utag_api.services.chat import (
    decrypt_message,
    direct_conversation_key,
    encrypt_message,
    new_conversation_key,
)
from utag_api.services.events import enqueue_task, record_change
from utag_api.services.storage import (
    quarantine_key,
    s3_client,
    s3_encryption_args,
    safe_filename,
    validate_upload,
)
from utag_api.services.system_chat_groups import is_system_chat

router = APIRouter(prefix="/chat", tags=["chat"])


def attachment_view(attachment: MessageAttachment) -> MessageAttachmentView:
    content_url = f"/api/v1/chat/attachments/{attachment.id}/content"
    return MessageAttachmentView(
        id=attachment.id,
        filename=attachment.filename,
        content_type=attachment.content_type,
        byte_size=attachment.byte_size,
        content_url=content_url,
        thumbnail_url=(
            content_url if (attachment.content_type or "").startswith("image/") else None
        ),
    )


async def message_attachment_map(
    db: DbSession, message_ids: list[UUID]
) -> dict[UUID, list[MessageAttachmentView]]:
    if not message_ids:
        return {}
    rows = (
        await db.scalars(
            select(MessageAttachment)
            .where(MessageAttachment.message_id.in_(message_ids))
            .order_by(MessageAttachment.created_at, MessageAttachment.id)
        )
    ).all()
    result: dict[UUID, list[MessageAttachmentView]] = {}
    for attachment in rows:
        result.setdefault(attachment.message_id, []).append(attachment_view(attachment))
    return result


def invite_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invite_expired(invite: ConversationInvite) -> bool:
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


async def require_membership(
    db: DbSession, conversation_id: UUID, user_id: UUID
) -> tuple[Conversation, ConversationMember]:
    row = (
        await db.execute(
            select(Conversation, ConversationMember)
            .join(
                ConversationMember,
                ConversationMember.conversation_id == Conversation.id,
            )
            .where(
                Conversation.id == conversation_id,
                ConversationMember.user_id == user_id,
                ConversationMember.left_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "conversation_not_found", "Conversation not found")
    return row[0], row[1]


async def require_group_admin(
    db: DbSession, conversation_id: UUID, user_id: UUID
) -> tuple[Conversation, ConversationMember]:
    conversation, membership = await require_membership(db, conversation_id, user_id)
    if conversation.kind != "group" or membership.role not in {"owner", "admin"}:
        raise ApiError(403, "group_admin_required", "Group administrator access is required")
    return conversation, membership


async def conversation_views(
    db: DbSession,
    user_id: UUID,
    conversation_ids: set[UUID] | None = None,
) -> list[ConversationView]:
    """Build member-specific conversation summaries without per-row queries."""
    if conversation_ids == set():
        return []

    current_member = aliased(ConversationMember)
    active_member = aliased(ConversationMember)
    member_count = (
        select(func.count(active_member.id))
        .where(
            active_member.conversation_id == Conversation.id,
            active_member.left_at.is_(None),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    unread_count = (
        select(func.count(Message.id))
        .outerjoin(
            MessageReceipt,
            and_(
                MessageReceipt.message_id == Message.id,
                MessageReceipt.user_id == user_id,
            ),
        )
        .where(
            Message.conversation_id == Conversation.id,
            Message.sender_id != user_id,
            Message.deleted_at.is_(None),
            MessageReceipt.read_at.is_(None),
        )
        .correlate(Conversation)
        .scalar_subquery()
    )
    latest_message_id = (
        select(Message.id)
        .where(
            Message.conversation_id == Conversation.id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
        .correlate(Conversation)
        .scalar_subquery()
    )
    statement = (
        select(
            Conversation,
            current_member,
            member_count.label("member_count"),
            unread_count.label("unread_count"),
            latest_message_id.label("latest_message_id"),
        )
        .join(
            current_member,
            and_(
                current_member.conversation_id == Conversation.id,
                current_member.user_id == user_id,
                current_member.left_at.is_(None),
            ),
        )
        .order_by(
            Conversation.last_message_at.desc().nullslast(),
            Conversation.created_at.desc(),
        )
    )
    if conversation_ids is not None:
        statement = statement.where(Conversation.id.in_(conversation_ids))
    rows = (await db.execute(statement)).all()
    if not rows:
        return []

    direct_ids = {conversation.id for conversation, *_rest in rows if conversation.kind == "direct"}
    direct_members: dict[UUID, User] = {}
    if direct_ids:
        direct_members = {
            conversation_id: member
            for conversation_id, member in (
                await db.execute(
                    select(ConversationMember.conversation_id, User)
                    .join(User, User.id == ConversationMember.user_id)
                    .where(
                        ConversationMember.conversation_id.in_(direct_ids),
                        ConversationMember.user_id != user_id,
                        ConversationMember.left_at.is_(None),
                    )
                )
            ).all()
        }

    latest_ids = {latest_id for *_row, latest_id in rows if latest_id is not None}
    latest_messages: dict[UUID, tuple[Message, User]] = {}
    attachment_counts: dict[UUID, int] = {}
    if latest_ids:
        latest_messages = {
            message.id: (message, sender)
            for message, sender in (
                await db.execute(
                    select(Message, User)
                    .join(User, User.id == Message.sender_id)
                    .where(Message.id.in_(latest_ids))
                )
            ).all()
        }
        attachment_counts = {
            message_id: int(count)
            for message_id, count in (
                await db.execute(
                    select(MessageAttachment.message_id, func.count(MessageAttachment.id))
                    .where(MessageAttachment.message_id.in_(latest_ids))
                    .group_by(MessageAttachment.message_id)
                )
            ).all()
        }

    result: list[ConversationView] = []
    for conversation, membership, count, unread, latest_id in rows:
        direct_member = direct_members.get(conversation.id)
        display_title = (
            direct_member.full_name
            if direct_member is not None
            else conversation.title
            or ("Member group" if conversation.kind == "group" else "Direct conversation")
        )
        preview: str | None = None
        preview_sender: str | None = None
        latest = latest_messages.get(latest_id) if latest_id is not None else None
        if latest is not None:
            message, sender = latest
            if conversation.encryption_key_ciphertext:
                try:
                    preview = " ".join(
                        decrypt_message(
                            conversation.encryption_key_ciphertext,
                            message.ciphertext,
                        ).split()
                    )
                except Exception:
                    preview = "Encrypted message"
            attachment_count = attachment_counts.get(message.id, 0)
            if not preview and attachment_count:
                preview = (
                    "Attachment" if attachment_count == 1 else f"{attachment_count} attachments"
                )
            if preview and len(preview) > 120:
                preview = f"{preview[:117].rstrip()}…"
            preview_sender = "You" if sender.id == user_id else sender.full_name
        result.append(
            ConversationView(
                id=conversation.id,
                kind=conversation.kind,
                title=conversation.title,
                created_by_id=conversation.created_by_id,
                last_message_at=conversation.last_message_at,
                member_count=int(count),
                unread_count=int(unread),
                display_title=display_title,
                direct_member_id=direct_member.id if direct_member is not None else None,
                current_user_role=membership.role,
                is_muted=membership.is_muted,
                last_message_preview=preview,
                last_message_sender=preview_sender,
                created_at=conversation.created_at,
            )
        )
    return result


async def message_reply_map(
    db: DbSession,
    conversation: Conversation,
    reply_ids: set[UUID],
) -> dict[UUID, MessageReplyView]:
    if not reply_ids or not conversation.encryption_key_ciphertext:
        return {}
    rows = (
        await db.execute(
            select(Message, User)
            .join(User, User.id == Message.sender_id)
            .where(
                Message.id.in_(reply_ids),
                Message.conversation_id == conversation.id,
                Message.deleted_at.is_(None),
            )
        )
    ).all()
    return {
        message.id: MessageReplyView(
            id=message.id,
            sender_id=message.sender_id,
            sender_name=sender.full_name,
            text=decrypt_message(conversation.encryption_key_ciphertext, message.ciphertext),
        )
        for message, sender in rows
    }


@router.post("/attachments", response_model=MediaView, status_code=201)
async def upload_chat_attachment(
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
    file: Annotated[UploadFile, File()],
) -> MediaView:
    digest = hashlib.sha256()
    byte_size = 0
    while chunk := await file.read(1024 * 1024):
        byte_size += len(chunk)
        digest.update(chunk)
        if byte_size > get_settings().upload_max_bytes:
            raise ApiError(413, "file_too_large", "The selected file is too large")
    await file.seek(0)
    content_type = file.content_type or "application/octet-stream"
    validate_upload(content_type, byte_size)
    asset_id = new_id()
    storage_key = quarantine_key(asset_id, file.filename or "attachment")
    asset = MediaAsset(
        id=asset_id,
        owner_id=principal.user.id,
        storage_key=storage_key,
        original_filename=file.filename or "attachment",
        content_type=content_type,
        byte_size=byte_size,
        sha256=digest.hexdigest(),
        status="quarantined",
        is_private=True,
    )
    db.add(asset)
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.attachment.upload.created",
        resource_type="media_asset",
        resource_id=asset.id,
        topic=f"user:{principal.user.id}",
        payload={"asset_id": str(asset.id), "status": asset.status},
    )
    await db.commit()
    try:
        await run_in_threadpool(
            lambda: s3_client().upload_fileobj(
                file.file,
                get_settings().media_bucket,
                storage_key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {
                        "byte-size": str(byte_size),
                        "sha256": asset.sha256,
                    },
                    **s3_encryption_args(),
                },
            )
        )
    except Exception as exc:
        asset.status = "rejected"
        asset.metadata_json = {"upload_error": "object_storage_unavailable"}
        await db.commit()
        raise ApiError(503, "upload_failed", "The file could not be stored") from exc
    asset.status = "scanning"
    enqueue_task(
        db,
        task_name="utag.media.process",
        aggregate_type="media_asset",
        aggregate_id=asset.id,
        args=[str(asset.id)],
        queue="media",
    )
    await db.commit()
    return MediaView.model_validate(asset)


@router.get("/attachments/uploads/{asset_id}", response_model=MediaView)
async def chat_attachment_status(
    asset_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
) -> MediaView:
    asset = await db.get(MediaAsset, asset_id)
    if asset is None or asset.owner_id != principal.user.id or not asset.is_private:
        raise ApiError(404, "attachment_not_found", "Attachment not found")
    return MediaView.model_validate(asset)


@router.get("/attachments/{attachment_id}/content")
async def stream_chat_attachment(
    attachment_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
) -> StreamingResponse:
    row = (
        await db.execute(
            select(MessageAttachment, Message)
            .join(Message, Message.id == MessageAttachment.message_id)
            .join(
                ConversationMember,
                and_(
                    ConversationMember.conversation_id == Message.conversation_id,
                    ConversationMember.user_id == principal.user.id,
                    ConversationMember.left_at.is_(None),
                ),
            )
            .where(
                MessageAttachment.id == attachment_id,
                MessageAttachment.status == "ready",
                Message.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "attachment_not_found", "Attachment not found")
    attachment = row[0]
    try:
        stored = await run_in_threadpool(
            lambda: s3_client().get_object(
                Bucket=get_settings().media_bucket,
                Key=attachment.storage_key,
            )
        )
    except Exception as exc:
        raise ApiError(404, "attachment_not_found", "Attachment not found") from exc
    return StreamingResponse(
        stored["Body"].iter_chunks(chunk_size=1024 * 1024),
        media_type=attachment.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": (f'inline; filename="{safe_filename(attachment.filename)}"'),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/directory")
async def chat_directory(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
    q: str | None = None,
) -> list[dict[str, object]]:
    statement = select(User).where(User.status == "active", User.id != principal.user.id)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                User.email.ilike(pattern),
                User.other_name.ilike(pattern),
                User.surname.ilike(pattern),
            )
        )
    users = (await db.scalars(statement.order_by(User.surname, User.other_name).limit(100))).all()
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "academic_rank": user.academic_rank,
        }
        for user in users
    ]


@router.get("/conversations", response_model=list[ConversationView])
async def list_conversations(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
) -> list[ConversationView]:
    return await conversation_views(db, principal.user.id)


@router.post("/conversations", response_model=ConversationView, status_code=201)
async def create_conversation(
    payload: ConversationCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> ConversationView:
    member_ids = set(payload.member_ids) | {principal.user.id}
    if payload.kind == "direct" and len(member_ids) != 2:
        raise ApiError(422, "direct_member_count", "Direct chats must have two members")
    title = payload.title.strip() if payload.title else None
    if payload.kind == "group" and (title is None or len(title) < 2):
        raise ApiError(422, "group_title_required", "Give the group a name")
    valid_users = set(
        (
            await db.scalars(
                select(User.id).where(User.id.in_(member_ids), User.status == "active")
            )
        ).all()
    )
    if valid_users != member_ids:
        raise ApiError(422, "invalid_members", "One or more chat members are invalid")
    direct_key = direct_conversation_key(list(member_ids)) if payload.kind == "direct" else None
    if direct_key:
        existing = await db.scalar(
            select(Conversation).where(Conversation.direct_key == direct_key)
        )
        if existing:
            summaries = await conversation_views(db, principal.user.id, {existing.id})
            if not summaries:
                raise ApiError(409, "conversation_unavailable", "Conversation is unavailable")
            return summaries[0]
    encrypted_key, key_version = new_conversation_key()
    conversation = Conversation(
        id=new_id(),
        kind=payload.kind,
        direct_key=direct_key,
        title=title,
        created_by_id=principal.user.id,
        encryption_key_ciphertext=encrypted_key,
        encryption_key_version=key_version,
    )
    db.add(conversation)
    await db.flush()
    for user_id in member_ids:
        db.add(
            ConversationMember(
                id=new_id(),
                conversation_id=conversation.id,
                user_id=user_id,
                role="owner" if user_id == principal.user.id else "member",
            )
        )
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.conversation.created",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"conversation_id": str(conversation.id), "kind": conversation.kind},
    )
    for user_id in member_ids:
        record_change(
            db,
            context=event_context(request, principal),
            action="chat.conversation.available",
            resource_type="conversation",
            resource_id=conversation.id,
            topic=f"user:{user_id}",
            payload={"conversation_id": str(conversation.id)},
        )
    await db.commit()
    summaries = await conversation_views(db, principal.user.id, {conversation.id})
    return summaries[0]


@router.get("/conversations/{conversation_id}/members")
async def conversation_members(
    conversation_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
) -> list[dict[str, object]]:
    await require_membership(db, conversation_id, principal.user.id)
    rows = (
        await db.execute(
            select(ConversationMember, User)
            .join(User, User.id == ConversationMember.user_id)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.left_at.is_(None),
            )
            .order_by(User.surname, User.other_name)
        )
    ).all()
    return [
        {
            "user_id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": membership.role,
        }
        for membership, user in rows
    ]


@router.patch("/conversations/{conversation_id}", response_model=ConversationView)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> ConversationView:
    conversation, _ = await require_group_admin(db, conversation_id, principal.user.id)
    conversation.title = payload.title.strip()
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.conversation.updated",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"conversation_id": str(conversation.id), "title": conversation.title},
    )
    await db.commit()
    summaries = await conversation_views(db, principal.user.id, {conversation.id})
    return summaries[0]


@router.patch(
    "/conversations/{conversation_id}/preferences",
    response_model=ConversationView,
)
async def update_conversation_preferences(
    conversation_id: UUID,
    payload: ConversationPreferenceUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> ConversationView:
    conversation, membership = await require_membership(db, conversation_id, principal.user.id)
    membership.is_muted = payload.is_muted
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.preferences.updated",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"user:{principal.user.id}",
        payload={
            "conversation_id": str(conversation.id),
            "is_muted": membership.is_muted,
        },
    )
    await db.commit()
    summaries = await conversation_views(db, principal.user.id, {conversation.id})
    return summaries[0]


@router.post(
    "/conversations/{conversation_id}/invites",
    response_model=ConversationInviteView,
    status_code=201,
)
async def create_conversation_invite(
    conversation_id: UUID,
    payload: ConversationInviteCreate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> ConversationInviteView:
    conversation, _ = await require_group_admin(db, conversation_id, principal.user.id)
    token = secrets.token_urlsafe(32)
    invite = ConversationInvite(
        id=new_id(),
        conversation_id=conversation.id,
        token_hash=invite_token_hash(token),
        created_by_id=principal.user.id,
        expires_at=datetime.now(UTC) + timedelta(hours=payload.expires_in_hours),
        max_uses=payload.max_uses,
    )
    db.add(invite)
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.invite.created",
        resource_type="conversation_invite",
        resource_id=invite.id,
        topic=f"conversation:{conversation.id}",
        payload={
            "conversation_id": str(conversation.id),
            "expires_at": invite.expires_at.isoformat(),
            "max_uses": invite.max_uses,
        },
    )
    await db.commit()
    return ConversationInviteView(
        id=invite.id,
        conversation_id=conversation.id,
        conversation_title=conversation.title or "Member group",
        join_url=f"/dashboard/chat?invite={token}",
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
    )


@router.get("/invites/{token}")
async def conversation_invite_details(
    token: str,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
) -> dict[str, object]:
    del principal
    row = (
        await db.execute(
            select(ConversationInvite, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationInvite.conversation_id,
            )
            .where(ConversationInvite.token_hash == invite_token_hash(token))
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "invite_not_found", "Invitation link not found")
    invite, conversation = row
    unavailable = (
        invite.revoked_at is not None
        or invite_expired(invite)
        or (invite.max_uses is not None and invite.use_count >= invite.max_uses)
    )
    if unavailable:
        raise ApiError(
            410,
            "invite_unavailable",
            "This invitation link has expired or is no longer available",
        )
    return {
        "conversation_id": conversation.id,
        "conversation_title": conversation.title or "Member group",
        "expires_at": invite.expires_at,
    }


@router.post("/invites/{token}/accept", response_model=ConversationView)
async def accept_conversation_invite(
    token: str,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> ConversationView:
    row = (
        await db.execute(
            select(ConversationInvite, Conversation)
            .join(
                Conversation,
                Conversation.id == ConversationInvite.conversation_id,
            )
            .where(ConversationInvite.token_hash == invite_token_hash(token))
            .with_for_update()
        )
    ).one_or_none()
    if row is None:
        raise ApiError(404, "invite_not_found", "Invitation link not found")
    invite, conversation = row
    if (
        invite.revoked_at is not None
        or invite_expired(invite)
        or (invite.max_uses is not None and invite.use_count >= invite.max_uses)
    ):
        raise ApiError(
            410,
            "invite_unavailable",
            "This invitation link has expired or is no longer available",
        )
    membership = await db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id == principal.user.id,
        )
    )
    joined = membership is None or membership.left_at is not None
    if membership is None:
        db.add(
            ConversationMember(
                id=new_id(),
                conversation_id=conversation.id,
                user_id=principal.user.id,
                role="member",
            )
        )
    elif membership.left_at is not None:
        membership.left_at = None
        membership.role = "member"
    if joined:
        invite.use_count += 1
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.invite.accepted",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={
            "conversation_id": str(conversation.id),
            "user_id": str(principal.user.id),
        },
    )
    await db.commit()
    summaries = await conversation_views(db, principal.user.id, {conversation.id})
    return summaries[0]


@router.post("/conversations/{conversation_id}/members", response_model=MessageResponse)
async def add_conversation_members(
    conversation_id: UUID,
    payload: ConversationMembersUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    conversation, _ = await require_group_admin(db, conversation_id, principal.user.id)
    requested = set(payload.member_ids)
    valid = set(
        (
            await db.scalars(select(User.id).where(User.id.in_(requested), User.status == "active"))
        ).all()
    )
    if valid != requested:
        raise ApiError(422, "invalid_members", "One or more chat members are invalid")
    existing = {
        membership.user_id: membership
        for membership in (
            await db.scalars(
                select(ConversationMember).where(
                    ConversationMember.conversation_id == conversation.id,
                    ConversationMember.user_id.in_(requested),
                )
            )
        ).all()
    }
    added = 0
    for user_id in requested:
        membership = existing.get(user_id)
        if membership is None:
            db.add(
                ConversationMember(
                    id=new_id(),
                    conversation_id=conversation.id,
                    user_id=user_id,
                    role="member",
                )
            )
            added += 1
        elif membership.left_at is not None:
            membership.left_at = None
            membership.role = "member"
            added += 1
        record_change(
            db,
            context=event_context(request, principal),
            action="chat.conversation.available",
            resource_type="conversation",
            resource_id=conversation.id,
            topic=f"user:{user_id}",
            payload={"conversation_id": str(conversation.id)},
        )
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.members.added",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"conversation_id": str(conversation.id), "count": added},
    )
    await db.commit()
    return MessageResponse(message=f"{added} member(s) added")


@router.patch(
    "/conversations/{conversation_id}/members/{user_id}/role",
    response_model=MessageResponse,
)
async def update_conversation_member_role(
    conversation_id: UUID,
    user_id: UUID,
    payload: ConversationMemberRoleUpdate,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    conversation, membership = await require_group_admin(db, conversation_id, principal.user.id)
    if membership.role != "owner":
        raise ApiError(403, "group_owner_required", "Only the group owner can change roles")
    target = await db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if target is None:
        raise ApiError(404, "conversation_member_not_found", "Group member not found")
    if target.role == "owner":
        raise ApiError(409, "owner_role_locked", "The group owner role cannot be changed")
    target.role = payload.role
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.member.role.updated",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"user_id": str(user_id), "role": target.role},
    )
    await db.commit()
    return MessageResponse(message="Member role updated")


@router.patch(
    "/conversations/{conversation_id}/owner",
    response_model=MessageResponse,
)
async def transfer_conversation_ownership(
    conversation_id: UUID,
    payload: ConversationOwnershipTransfer,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    conversation, membership = await require_group_admin(db, conversation_id, principal.user.id)
    if membership.role != "owner":
        raise ApiError(403, "group_owner_required", "Only the group owner can transfer ownership")
    if payload.user_id == principal.user.id:
        raise ApiError(409, "owner_unchanged", "You already own this group")
    memberships = (
        await db.scalars(
            select(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation.id,
                ConversationMember.user_id.in_([principal.user.id, payload.user_id]),
                ConversationMember.left_at.is_(None),
            )
            .with_for_update()
        )
    ).all()
    member_by_user = {item.user_id: item for item in memberships}
    current_owner = member_by_user.get(principal.user.id)
    next_owner = member_by_user.get(payload.user_id)
    if current_owner is None or current_owner.role != "owner":
        raise ApiError(409, "owner_changed", "Group ownership changed; refresh and try again")
    if next_owner is None:
        raise ApiError(404, "conversation_member_not_found", "Group member not found")
    current_owner.role = "admin"
    next_owner.role = "owner"
    conversation.created_by_id = next_owner.user_id
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.owner.transferred",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={
            "previous_owner_id": str(principal.user.id),
            "owner_id": str(next_owner.user_id),
        },
    )
    await db.commit()
    return MessageResponse(message="Group ownership transferred")


@router.delete("/conversations/{conversation_id}/members/{user_id}", response_model=MessageResponse)
async def remove_conversation_member(
    conversation_id: UUID,
    user_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    conversation, membership = await require_membership(db, conversation_id, principal.user.id)
    if conversation.kind != "group":
        raise ApiError(409, "group_required", "Direct chat membership cannot be changed")
    if is_system_chat(conversation):
        raise ApiError(
            409,
            "system_chat_membership_managed",
            "Membership in this group is managed from the member's organization",
        )
    if user_id != principal.user.id and membership.role not in {"owner", "admin"}:
        raise ApiError(403, "group_admin_required", "Group administrator access is required")
    target = await db.scalar(
        select(ConversationMember).where(
            ConversationMember.conversation_id == conversation.id,
            ConversationMember.user_id == user_id,
            ConversationMember.left_at.is_(None),
        )
    )
    if target is None:
        raise ApiError(404, "conversation_member_not_found", "Group member not found")
    if target.role == "owner":
        raise ApiError(409, "owner_cannot_leave", "Transfer ownership before the owner leaves")
    target.left_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.member.removed",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"user_id": str(user_id)},
    )
    await db.commit()
    return MessageResponse(message="Member removed from the group")


@router.get("/conversations/{conversation_id}/messages", response_model=Page[MessageView])
async def list_messages(
    conversation_id: UUID,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_permissions("chat.use"))],
    before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[MessageView]:
    conversation, _ = await require_membership(db, conversation_id, principal.user.id)
    if not conversation.encryption_key_ciphertext:
        raise ApiError(500, "conversation_key_missing", "Conversation encryption is unavailable")
    statement = (
        select(Message, User)
        .join(User, User.id == Message.sender_id)
        .where(Message.conversation_id == conversation.id, Message.deleted_at.is_(None))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    if before:
        statement = statement.where(Message.created_at < before)
    rows = list(reversed((await db.execute(statement)).all()))
    attachments = await message_attachment_map(db, [message.id for message, _user in rows])
    message_ids = [message.id for message, _user in rows]
    replies = await message_reply_map(
        db,
        conversation,
        {message.reply_to_id for message, _user in rows if message.reply_to_id is not None},
    )
    read_counts = {
        message_id: int(read_count)
        for message_id, read_count in (
            await db.execute(
                select(MessageReceipt.message_id, func.count(MessageReceipt.user_id))
                .where(
                    MessageReceipt.message_id.in_(message_ids),
                    MessageReceipt.read_at.is_not(None),
                )
                .group_by(MessageReceipt.message_id)
            )
        ).all()
    }
    total = int(
        (
            await db.scalar(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conversation.id,
                    Message.deleted_at.is_(None),
                )
            )
        )
        or 0
    )
    items = [
        MessageView(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            sender_name=user.full_name,
            client_message_id=message.client_message_id,
            text=decrypt_message(conversation.encryption_key_ciphertext, message.ciphertext),
            reply_to_id=message.reply_to_id,
            reply_to=replies.get(message.reply_to_id) if message.reply_to_id else None,
            created_at=message.created_at,
            edited_at=message.edited_at,
            read_by=read_counts.get(message.id, 0),
            attachments=attachments.get(message.id, []),
        )
        for message, user in rows
    ]
    return Page[MessageView](
        items=items,
        page=1,
        page_size=limit,
        total=total,
        pages=max(1, (total + limit - 1) // limit),
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageView,
    status_code=201,
)
async def create_message(
    conversation_id: UUID,
    payload: MessageCreateRequest,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageView:
    conversation, _ = await require_membership(db, conversation_id, principal.user.id)
    if not conversation.encryption_key_ciphertext:
        raise ApiError(500, "conversation_key_missing", "Conversation encryption is unavailable")
    existing = await db.scalar(
        select(Message).where(
            Message.sender_id == principal.user.id,
            Message.client_message_id == payload.client_message_id,
        )
    )
    if existing:
        if existing.conversation_id != conversation.id:
            raise ApiError(
                409,
                "client_message_id_conflict",
                "This message identifier was already used in another conversation",
            )
        existing_attachments = await message_attachment_map(db, [existing.id])
        existing_reply = await message_reply_map(
            db,
            conversation,
            {existing.reply_to_id} if existing.reply_to_id else set(),
        )
        return MessageView(
            id=existing.id,
            conversation_id=existing.conversation_id,
            sender_id=existing.sender_id,
            sender_name=principal.user.full_name,
            client_message_id=existing.client_message_id,
            text=decrypt_message(conversation.encryption_key_ciphertext, existing.ciphertext),
            reply_to_id=existing.reply_to_id,
            reply_to=(existing_reply.get(existing.reply_to_id) if existing.reply_to_id else None),
            created_at=existing.created_at,
            edited_at=existing.edited_at,
            attachments=existing_attachments.get(existing.id, []),
        )
    if payload.reply_to_id:
        reply_exists = await db.scalar(
            select(Message.id).where(
                Message.id == payload.reply_to_id,
                Message.conversation_id == conversation.id,
                Message.deleted_at.is_(None),
            )
        )
        if not reply_exists:
            raise ApiError(422, "reply_not_found", "The replied message does not exist")
    attachment_assets: list[MediaAsset] = []
    if payload.attachment_media_ids:
        attachment_assets = list(
            (
                await db.scalars(
                    select(MediaAsset).where(
                        MediaAsset.id.in_(payload.attachment_media_ids),
                        MediaAsset.owner_id == principal.user.id,
                        MediaAsset.status == "ready",
                        MediaAsset.is_private.is_(True),
                    )
                )
            ).all()
        )
        if len(attachment_assets) != len(payload.attachment_media_ids):
            raise ApiError(
                409,
                "attachment_not_ready",
                "Wait for every attachment to complete security scanning",
            )
        asset_by_id = {asset.id: asset for asset in attachment_assets}
        attachment_assets = [asset_by_id[asset_id] for asset_id in payload.attachment_media_ids]
    message = Message(
        id=new_id(),
        conversation_id=conversation.id,
        sender_id=principal.user.id,
        client_message_id=payload.client_message_id,
        reply_to_id=payload.reply_to_id,
        ciphertext=encrypt_message(conversation.encryption_key_ciphertext, payload.text),
        key_version=conversation.encryption_key_version or "v1",
    )
    db.add(message)
    await db.flush()
    message_attachments = [
        MessageAttachment(
            id=new_id(),
            message_id=message.id,
            filename=asset.original_filename,
            content_type=asset.content_type,
            byte_size=asset.byte_size,
            storage_key=asset.storage_key,
            sha256=asset.sha256,
            encryption_key_version=(
                get_settings().s3_server_side_encryption or "development-unencrypted"
            ),
            status="ready",
        )
        for asset in attachment_assets
    ]
    db.add_all(message_attachments)
    conversation.last_message_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.message.created",
        resource_type="message",
        resource_id=message.id,
        topic=f"conversation:{conversation.id}",
        payload={
            "message_id": str(message.id),
            "conversation_id": str(conversation.id),
            "sender_id": str(principal.user.id),
            "attachment_count": len(message_attachments),
        },
    )
    await db.commit()
    reply = await message_reply_map(
        db,
        conversation,
        {message.reply_to_id} if message.reply_to_id else set(),
    )
    return MessageView(
        id=message.id,
        conversation_id=conversation.id,
        sender_id=principal.user.id,
        sender_name=principal.user.full_name,
        client_message_id=message.client_message_id,
        text=payload.text,
        reply_to_id=message.reply_to_id,
        reply_to=reply.get(message.reply_to_id) if message.reply_to_id else None,
        created_at=message.created_at,
        edited_at=message.edited_at,
        attachments=[attachment_view(attachment) for attachment in message_attachments],
    )


@router.patch("/messages/{message_id}", response_model=MessageView)
async def update_message(
    message_id: UUID,
    payload: MessageUpdateRequest,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageView:
    message = await db.get(Message, message_id)
    if message is None or message.deleted_at is not None:
        raise ApiError(404, "message_not_found", "Message not found")
    conversation, _ = await require_membership(db, message.conversation_id, principal.user.id)
    if message.sender_id != principal.user.id:
        raise ApiError(403, "message_edit_denied", "You can only edit your own messages")
    if not conversation.encryption_key_ciphertext:
        raise ApiError(500, "conversation_key_missing", "Conversation encryption is unavailable")
    text = payload.text.strip()
    if not text:
        has_attachment = await db.scalar(
            select(MessageAttachment.id).where(MessageAttachment.message_id == message.id).limit(1)
        )
        if has_attachment is None:
            raise ApiError(422, "message_content_required", "A message cannot be empty")
    message.ciphertext = encrypt_message(conversation.encryption_key_ciphertext, text)
    message.edited_at = datetime.now(UTC)
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.message.updated",
        resource_type="message",
        resource_id=message.id,
        topic=f"conversation:{conversation.id}",
        payload={
            "message_id": str(message.id),
            "conversation_id": str(conversation.id),
        },
    )
    await db.commit()
    attachments = await message_attachment_map(db, [message.id])
    replies = await message_reply_map(
        db,
        conversation,
        {message.reply_to_id} if message.reply_to_id else set(),
    )
    read_by = int(
        (
            await db.scalar(
                select(func.count(MessageReceipt.user_id)).where(
                    MessageReceipt.message_id == message.id,
                    MessageReceipt.read_at.is_not(None),
                )
            )
        )
        or 0
    )
    return MessageView(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name=principal.user.full_name,
        client_message_id=message.client_message_id,
        text=text,
        reply_to_id=message.reply_to_id,
        reply_to=replies.get(message.reply_to_id) if message.reply_to_id else None,
        created_at=message.created_at,
        edited_at=message.edited_at,
        read_by=read_by,
        attachments=attachments.get(message.id, []),
    )


@router.delete("/messages/{message_id}", response_model=MessageResponse)
async def delete_message(
    message_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    message = await db.get(Message, message_id)
    if message is None:
        raise ApiError(404, "message_not_found", "Message not found")
    conversation, membership = await require_membership(
        db, message.conversation_id, principal.user.id
    )
    can_moderate = conversation.kind == "group" and membership.role in {"owner", "admin"}
    if message.sender_id != principal.user.id and not can_moderate:
        raise ApiError(403, "message_delete_denied", "You cannot delete this message")
    if message.deleted_at is None:
        message.deleted_at = datetime.now(UTC)
        message.deleted_by_id = principal.user.id
        conversation.last_message_at = await db.scalar(
            select(func.max(Message.created_at)).where(
                Message.conversation_id == conversation.id,
                Message.id != message.id,
                Message.deleted_at.is_(None),
            )
        )
        record_change(
            db,
            context=event_context(request, principal),
            action="chat.message.deleted",
            resource_type="message",
            resource_id=message.id,
            topic=f"conversation:{conversation.id}",
            payload={"message_id": str(message.id)},
        )
        await db.commit()
    return MessageResponse(message="Message deleted")


@router.post("/conversations/{conversation_id}/read", response_model=MessageResponse)
async def mark_conversation_read(
    conversation_id: UUID,
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_mutation_permissions("chat.use"))],
) -> MessageResponse:
    conversation, _ = await require_membership(db, conversation_id, principal.user.id)
    unread = (
        await db.scalars(
            select(Message.id)
            .outerjoin(
                MessageReceipt,
                and_(
                    MessageReceipt.message_id == Message.id,
                    MessageReceipt.user_id == principal.user.id,
                ),
            )
            .where(
                Message.conversation_id == conversation.id,
                Message.sender_id != principal.user.id,
                Message.deleted_at.is_(None),
                MessageReceipt.read_at.is_(None),
            )
        )
    ).all()
    now = datetime.now(UTC)
    for message_id in unread:
        receipt = await db.get(MessageReceipt, (message_id, principal.user.id))
        if receipt:
            receipt.read_at = now
            receipt.delivered_at = receipt.delivered_at or now
        else:
            db.add(
                MessageReceipt(
                    message_id=message_id,
                    user_id=principal.user.id,
                    delivered_at=now,
                    read_at=now,
                )
            )
    record_change(
        db,
        context=event_context(request, principal),
        action="chat.conversation.read",
        resource_type="conversation",
        resource_id=conversation.id,
        topic=f"conversation:{conversation.id}",
        payload={"user_id": str(principal.user.id), "read_count": len(unread)},
    )
    await db.commit()
    return MessageResponse(message="Conversation marked as read")
