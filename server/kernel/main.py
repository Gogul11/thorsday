import asyncio

from Redis.redis_connection import RedisPubSub
from models.model import Models
from Agents.main_agent import Main_Agent


redis_client = RedisPubSub()

models = Models()

main_agent = Main_Agent(
    models,
    redis_client
)


async def handle_backend_task(data: dict):
    print("\n========== BACKEND TASK ==========")

    print(f"Event : {data['event']}")
    print(f"Req ID: {data['req_id']}")
    print(f"Prompt: {data['prompt']}")

    if data["event"] == "task.REQUESTED":
        await main_agent.chat(
            data["prompt"],
            data["req_id"]
        )


async def main():
    await redis_client.subscribe(
        "backend_tasks",
        handle_backend_task
    )


if __name__ == "__main__":
    asyncio.run(main())