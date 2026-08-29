"""Redis pub/sub — clean async interface.

Single shared client, created lazily on first use.
Call redis_close() in the app shutdown hook.
"""

import json
from typing import Awaitable, Callable

import redis.asyncio as redis

# ---------------------------------------------------------------------------
# Shared client (lazy singleton)
# ---------------------------------------------------------------------------

_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True,
        )
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def redis_publish(channel: str, data: dict) -> None:
    """Publish *data* as JSON to *channel*."""
    await _get_client().publish(channel, json.dumps(data))


async def redis_subscribe(
    channel: str,
    handler: Callable[[dict], Awaitable[None]],
) -> None:
    """Subscribe to *channel* and call *handler* for every message.

    Runs indefinitely — cancel the wrapping asyncio.Task to stop it.
    """
    pubsub = _get_client().pubsub()
    await pubsub.subscribe(channel)

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            data = json.loads(message["data"])
            await handler(data)
        except Exception as exc:
            # Log and continue — never crash the listener loop
            print(f"[kernel_listener] error handling message: {exc}")


async def redis_close() -> None:
    """Close and discard the shared Redis client."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
