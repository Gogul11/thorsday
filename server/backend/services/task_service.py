"""Task service — Redis pub/sub, WebSocket manager, and app lifespan.

Single source of truth for all real-time communication:
- Redis client (publish to kernel, subscribe from kernel)
- WebSocket registry (connect/disconnect/broadcast per req_id)
- App lifespan (starts the kernel-event subscriber on startup)
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket

# ---------------------------------------------------------------------------
# Redis client (lazy-initialised singleton)
# ---------------------------------------------------------------------------

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    return _client


async def redis_publish(channel: str, data: dict) -> None:
    """Publish a JSON payload to a Redis channel."""
    await _get_client().publish(channel, json.dumps(data))


async def redis_subscribe(
    channel: str,
    handler: Callable[[dict], Awaitable[None]],
) -> None:
    """Subscribe to *channel* and forward every message to *handler*.

    Runs indefinitely — cancel the task to stop it.
    """
    pubsub = _get_client().pubsub()
    await pubsub.subscribe(channel)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        await handler(json.loads(message["data"]))


async def redis_close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# WebSocket registry (req_id → list of active sockets)
# ---------------------------------------------------------------------------

_connections: dict[str, list[WebSocket]] = {}


async def ws_connect(req_id: str, websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.setdefault(req_id, []).append(websocket)


def ws_disconnect(req_id: str, websocket: WebSocket) -> None:
    bucket = _connections.get(req_id, [])
    if websocket in bucket:
        bucket.remove(websocket)
    if not bucket:
        _connections.pop(req_id, None)


async def ws_broadcast(req_id: str, data: dict) -> None:
    dead: list[WebSocket] = []
    for ws in list(_connections.get(req_id, [])):
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_disconnect(req_id, ws)


# ---------------------------------------------------------------------------
# Kernel-event handler
# ---------------------------------------------------------------------------

async def handle_kernel_event(data: dict) -> None:
    """Receive a kernel event and push it straight to the subscribed browser."""
    req_id = data.get("req_id", "")
    await ws_broadcast(req_id, data)


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(
        redis_subscribe("kernel_events", handle_kernel_event)
    )
    yield
    task.cancel()
    await redis_close()
