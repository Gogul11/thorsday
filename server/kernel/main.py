import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from Redis.redis_connection import redis_client, subscribe, publish
from models.model import Models
from Agents.main_agent import Main_Agent
from DB.mongodb import mongo_client


async def main():

    try:
        await mongo_client.admin.command("ping")
        print("MongoDB Connection is established")
    except Exception as exc:
            print(f"MongoDB Connection failed: {exc}")
            raise
    try:
        await redis_client.ping()
        print("Redis Connection is established")
    except Exception as exc:
        print(f"Redis Connection failed: {exc}")
        raise
    
    models = Models()
    main_agent = Main_Agent(models)
    
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
                await publish(
                    "kernel_events",
                    {
                        "event": "agent.FAILED",
                        "req_id": data.get("req_id", ""),
                        "task_id": data.get("req_id", ""),
                        "error": str(exc),
                    },
                )

    await subscribe(
        "backend_tasks",
        handle_backend_task,
    )



if __name__ == "__main__":
    asyncio.run(main())
