import json
import redis.asyncio as redis
from typing import Callable, Awaitable

class RedisPubSub:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
    ):
        self.redis = redis.Redis(
            host=host,
            port=port,
            decode_responses=True,
        )
        print("Redis Connection is established")

    async def publish(self, channel: str, data: dict[any, any]):
        await self.redis.publish(
            channel,
            json.dumps(data),
        )

    async def subscribe(
        self,
        channel: str,
        handler: Callable[[dict], Awaitable[None]],
    ):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            data = json.loads(message["data"])
            await handler(data)

    async def close(self):
        await self.redis.aclose()