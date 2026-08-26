import json
import redis.asyncio as redis
from typing import Any, Callable, Awaitable

redis_client = redis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
)


async def publish(
    channel: str,
    data: dict[str, Any],
):
    await redis_client.publish(
        channel,
        json.dumps(data),
    )


async def subscribe(
    channel: str,
    handler: Callable[[dict[str, Any]], Awaitable[None]],
):
    pubsub = redis_client.pubsub()

    await pubsub.subscribe(channel)

    async for message in pubsub.listen():

        if message["type"] != "message":
            continue

        data = json.loads(message["data"])

        await handler(data)


async def close():
    await redis_client.aclose()