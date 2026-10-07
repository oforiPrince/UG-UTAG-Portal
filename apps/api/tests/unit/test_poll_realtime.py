"""Exercise the WebSocket authorization protocol without a Redis service."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import WebSocket, WebSocketDisconnect

from utag_api.database import new_id
from utag_api.dependencies import Principal
from utag_api.models import Session, User
from utag_api.realtime import router as realtime


class FakePubsub:
    def __init__(self) -> None:
        self.subscriptions: set[str] = set()
        self.added: list[set[str]] = []
        self.removed: list[set[str]] = []
        self.incoming: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.closed = False
        self.listener_cancelled = False
        self.listener_started = asyncio.Event()

    async def subscribe(self, *topics: str) -> None:
        self.subscriptions.update(topics)
        self.added.append(set(topics))

    async def unsubscribe(self, *topics: str) -> None:
        removed = set(topics) if topics else self.subscriptions.copy()
        self.subscriptions.difference_update(removed)
        self.removed.append(removed)

    async def listen(self) -> AsyncIterator[dict[str, Any]]:
        self.listener_started.set()
        try:
            while True:
                yield await self.incoming.get()
        except asyncio.CancelledError:
            self.listener_cancelled = True
            raise

    async def aclose(self) -> None:
        self.closed = True


class FakeRedis:
    def __init__(self, pubsub: FakePubsub) -> None:
        self.subscription = pubsub
        self.closed = False

    def pubsub(self) -> FakePubsub:
        return self.subscription

    async def aclose(self) -> None:
        self.closed = True


class FakeWebsocket:
    def __init__(self) -> None:
        self.cookies = {"session": "trusted-session-cookie"}
        self.incoming: asyncio.Queue[dict[str, Any] | WebSocketDisconnect] = asyncio.Queue()
        self.outgoing: asyncio.Queue[dict[str, Any] | str] = asyncio.Queue()
        self.accepted: str | None = None
        self.closes: list[tuple[int, str | None]] = []

    async def accept(self, *, subprotocol: str) -> None:
        self.accepted = subprotocol

    async def receive_json(self) -> dict[str, Any]:
        message = await self.incoming.get()
        if isinstance(message, WebSocketDisconnect):
            raise message
        return message

    async def send_json(self, message: dict[str, Any]) -> None:
        await self.outgoing.put(message)

    async def send_text(self, message: str) -> None:
        await self.outgoing.put(message)

    async def close(self, *, code: int = 1000, reason: str | None = None) -> None:
        self.closes.append((code, reason))


def principal(permissions: set[str]) -> Principal:
    return Principal(
        user=User(id=new_id(), must_change_password=False),
        session=Session(id=new_id()),
        roles={"member"},
        permissions=permissions,
    )


def transport(
    monkeypatch: pytest.MonkeyPatch, initial: Principal
) -> tuple[FakeWebsocket, FakePubsub, FakeRedis, dict[str, Principal | None], list[str | None]]:
    websocket = FakeWebsocket()
    pubsub = FakePubsub()
    redis = FakeRedis(pubsub)
    current: dict[str, Principal | None] = {"principal": initial}
    resolved_tokens: list[str | None] = []

    @asynccontextmanager
    async def session_factory() -> AsyncIterator[object]:
        yield object()

    async def resolve(db: object, token: str | None, *, touch: bool) -> Principal | None:
        assert touch is False
        resolved_tokens.append(token)
        return current["principal"]

    async def topics(user: Principal) -> list[str]:
        return sorted({"utag:user:member", *(f"utag:{key}" for key in user.permissions)})

    monkeypatch.setattr(realtime, "SessionFactory", session_factory)
    monkeypatch.setattr(realtime, "resolve_principal", resolve)
    monkeypatch.setattr(realtime, "authorized_topics", topics)
    monkeypatch.setattr(
        realtime,
        "get_settings",
        lambda: SimpleNamespace(
            session_cookie_name="session",
            redis_url="redis://unused.test",
            realtime_heartbeat_seconds=3600,
        ),
    )
    monkeypatch.setattr(realtime, "Redis", SimpleNamespace(from_url=lambda *args, **kwargs: redis))
    return websocket, pubsub, redis, current, resolved_tokens


async def next_message(websocket: FakeWebsocket) -> dict[str, Any]:
    message = await asyncio.wait_for(websocket.outgoing.get(), timeout=2)
    assert isinstance(message, dict)
    return message


async def test_subscription_refresh_uses_server_grants_and_replaces_revoked_topics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_topic = "poll:previous:results"
    new_topic = "poll:newly-voted:results"
    websocket, pubsub, redis, current, tokens = transport(monkeypatch, principal({old_topic}))
    baseline = asyncio.all_tasks()
    handler = asyncio.create_task(realtime.realtime(cast(WebSocket, websocket)))
    try:
        ready = await next_message(websocket)
        assert ready["type"] == "connection.ready"
        assert pubsub.subscriptions == {"utag:user:member", f"utag:{old_topic}"}
        await asyncio.wait_for(pubsub.listener_started.wait(), timeout=2)
        current["principal"] = principal({new_topic})
        await websocket.incoming.put(
            {
                "type": "subscriptions.refresh",
                "topics": ["polls:management", "poll:another-member:results"],
                "token": "client-supplied-fake-token",
            }
        )
        refreshed = await next_message(websocket)
        assert refreshed == {
            "type": "subscriptions.changed",
            "topics": sorted(["user:member", new_topic]),
            "resync_required": True,
        }
        assert pubsub.subscriptions == {"utag:user:member", f"utag:{new_topic}"}
        assert {f"utag:{new_topic}"} in pubsub.added
        assert {f"utag:{old_topic}"} in pubsub.removed
        assert tokens == ["trusted-session-cookie", "trusted-session-cookie"]
        # Refresh is also a resync handshake when grants have not changed.
        await websocket.incoming.put({"type": "subscriptions.refresh"})
        unchanged = await next_message(websocket)
        assert unchanged == refreshed
        await websocket.incoming.put(WebSocketDisconnect())
        await asyncio.wait_for(handler, timeout=2)
    finally:
        if not handler.done():
            handler.cancel()
            await asyncio.gather(handler, return_exceptions=True)
    assert websocket.accepted == "utag.v1"
    assert pubsub.listener_cancelled
    assert pubsub.closed and redis.closed and not pubsub.subscriptions
    assert not (asyncio.all_tasks() - baseline)


async def test_revoked_session_refresh_closes_and_cleans_up_running_tasks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    websocket, pubsub, redis, current, tokens = transport(
        monkeypatch, principal({"poll:active:results"})
    )
    baseline = asyncio.all_tasks()
    handler = asyncio.create_task(realtime.realtime(cast(WebSocket, websocket)))
    try:
        assert (await next_message(websocket))["type"] == "connection.ready"
        await asyncio.wait_for(pubsub.listener_started.wait(), timeout=2)
        current["principal"] = None
        await websocket.incoming.put({"type": "subscriptions.refresh"})
        await asyncio.wait_for(handler, timeout=2)
    finally:
        if not handler.done():
            handler.cancel()
            await asyncio.gather(handler, return_exceptions=True)
    assert any(code == 1008 for code, _ in websocket.closes)
    assert tokens == ["trusted-session-cookie", "trusted-session-cookie"]
    assert websocket.outgoing.empty()
    assert pubsub.listener_cancelled
    assert pubsub.closed and redis.closed and not pubsub.subscriptions
    assert not (asyncio.all_tasks() - baseline)
