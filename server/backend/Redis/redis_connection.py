"""Redis pub/sub connection — function-based interface.

Module-level client is created lazily on first use.
Call redis_close() during app shutdown.
"""

import json
from typing import Awaitable, Callable

import redis.asyncio as redis

# ---------------------------------------------------------------------------
# Module-level client (created once, reused everywhere)
# ---------------------------------------------------------------------------
_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    """Return the shared Redis client, creating it on first call."""
    global _client
    if _client is None:
        _client = redis.Redis(
            host="localhost",
            port=6379,
            decode_responses=True,
        )
        print("Redis connection established.")
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def redis_publish(channel: str, data: dict) -> None:
    """Publish a JSON-serialised *data* dict to *channel*."""
    await _get_client().publish(channel, json.dumps(data))


async def redis_subscribe(
    channel: str,
    handler: Callable[[dict], Awaitable[None]],
) -> None:
    """Subscribe to *channel* and call *handler* for every message.

    This coroutine runs indefinitely; cancel the task to stop it.
    """
    client = _get_client()
    pubsub = client.pubsub()
    await pubsub.subscribe(channel)

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        data = json.loads(message["data"])
        await handler(data)


async def redis_close() -> None:
    """Close the shared Redis connection."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
