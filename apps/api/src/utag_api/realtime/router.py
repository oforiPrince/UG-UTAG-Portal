import asyncio
from contextlib import suppress

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from redis.asyncio import Redis
from sqlalchemy import select

from utag_api.config import get_settings
from utag_api.database import SessionFactory
from utag_api.dependencies import Principal, resolve_principal
from utag_api.models import ConversationMember
from utag_api.observability import get_logger

router = APIRouter(tags=["realtime"])
logger = get_logger()


async def authorized_topics(principal: Principal) -> list[str]:
    topics = {
        f"utag:user:{principal.user.id}",
        "utag:announcements",
        "utag:events",
        "utag:documents",
        "utag:executives",
        "utag:galleries",
        "utag:dashboard",
    }
    if "members.view" in principal.permissions:
        topics.add("utag:members")
        topics.add("utag:organization")
    if "content.view" in principal.permissions:
        topics.add("utag:content")
    if "media.manage" in principal.permissions:
        topics.add("utag:media")
    if "adverts.manage" in principal.permissions:
        topics.add("utag:adverts")
    if "settings.manage" in principal.permissions:
        topics.add("utag:settings")
    async with SessionFactory() as db:
        conversation_ids = (
            await db.scalars(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.user_id == principal.user.id,
                    ConversationMember.left_at.is_(None),
                )
            )
        ).all()
    topics.update(f"utag:conversation:{conversation_id}" for conversation_id in conversation_ids)
    return sorted(topics)


@router.websocket("/realtime")
async def realtime(websocket: WebSocket) -> None:
    settings = get_settings()
    raw_token = websocket.cookies.get(settings.session_cookie_name)
    async with SessionFactory() as db:
        principal = await resolve_principal(db, raw_token, touch=False)
    if principal is None:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication required"
        )
        return
    await websocket.accept(subprotocol="utag.v1")
    topics = await authorized_topics(principal)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(*topics)
    await websocket.send_json(
        {
            "type": "connection.ready",
            "user_id": str(principal.user.id),
            "topics": [topic.removeprefix("utag:") for topic in topics],
            "heartbeat_seconds": settings.realtime_heartbeat_seconds,
            "resync_required": True,
        }
    )

    async def forward_events() -> None:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()
            await websocket.send_text(data)

    async def receive_client() -> None:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif message_type == "resync.complete":
                await websocket.send_json({"type": "resync.acknowledged"})

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(settings.realtime_heartbeat_seconds)
            await websocket.send_json({"type": "heartbeat"})

    tasks = [
        asyncio.create_task(forward_events()),
        asyncio.create_task(receive_client()),
        asyncio.create_task(heartbeat()),
    ]
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("realtime_connection_failed", user_id=str(principal.user.id))
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError, WebSocketDisconnect):
                await task
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await redis.aclose()
        with suppress(RuntimeError):
            await websocket.close()
