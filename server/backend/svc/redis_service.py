from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from Redis.redis_connection import RedisPubSub


async def handle_kernel_event(data: dict):
    print("\n========== KERNEL EVENT ==========")

    event = data["event"]
    req_id = data["req_id"]
    task_id = data["task_id"]

    print(f"Event     : {event}")
    print(f"Request ID: {req_id}")
    print(f"Task ID   : {task_id}")

    if event == "task.CREATED":
        print(f"Task Created: {task_id}")

    elif event == "task.PLANNING":
        print("Task Status: Planning")

    elif event == "task.PLANNED":
        print(f"Execution Plan: {data.get('plan')}")

    elif event == "agent.STARTED":
        print(f"Agent Started: {data.get('agent_name')}")
        print(f"Agent ID     : {data.get('agent_id')}")

    elif event == "agent.COMPLETED":
        print(f"Agent Completed: {data.get('agent_name')}")
        print(f"Agent ID      : {data.get('agent_id')}")
        print(f"Result        : {data.get('result')}")

    elif event == "agent.FAILED":
        print(f"Agent Failed: {data.get('agent_name')}")
        print(f"Agent ID    : {data.get('agent_id')}")
        print(f"Error       : {data.get('error')}")

    elif event == "agent.DESTROYED":
        print(f"Agent Destroyed: {data.get('agent_name')}")

    elif event == "task.COMPLETED":
        print("Task Completed")
        print(f"Final Response: {data.get('response')}")

    print("==================================\n")


def create_lifespan(redis_client: RedisPubSub):

    @asynccontextmanager
    async def lifespan(app: FastAPI):

        subscriber_task = asyncio.create_task(
            redis_client.subscribe(
                "kernel_events",
                handle_kernel_event
            )
        )

        yield

        subscriber_task.cancel()
        await redis_client.close()

    return lifespan