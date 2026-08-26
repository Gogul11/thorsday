import asyncio
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from Redis.redis_connection import RedisPubSub
from models.model import Models
from Agents.main_agent import Main_Agent


async def main():
    redis_client = RedisPubSub()
    models = Models()
    main_agent = Main_Agent(
        models,
        redis_client,
    )

    async def handle_backend_task(data: dict):
        print("\n========== BACKEND TASK ==========")
        print(f"Event : {data.get('event')}")
        print(f"Req ID: {data.get('req_id')}")
        print(f"Prompt: {data.get('prompt')}")

        if data.get("event") == "task.REQUESTED":
            try:
                await main_agent.chat(
                    data["prompt"],
                    data["req_id"],
                )
            except Exception as exc:
                print(f"Error executing task {data.get('req_id')}: {exc}")
                await redis_client.publish(
                    "kernel_events",
                    {
                        "event": "agent.FAILED",
                        "req_id": data.get("req_id", ""),
                        "task_id": data.get("req_id", ""),
                        "error": str(exc),
                    },
                )

    await redis_client.subscribe(
        "backend_tasks",
        handle_backend_task,
    )


if __name__ == "__main__":
    asyncio.run(main())
