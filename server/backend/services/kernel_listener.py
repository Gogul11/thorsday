"""Kernel event listener.

Subscribes to the 'kernel_events' Redis channel and forwards every
event to any WebSocket connections watching that req_id.

The kernel publishes events shaped like:

    {
        "event":    "task.CREATED" | "task.PLANNING" | "task.PLANNED" |
                    "task.COMPLETED" | "agent.STARTED" | "agent.COMPLETED" |
                    "agent.FAILED" | "agent.DESTROYED" |
                    "tool.STARTED" | "tool.COMPLETED" | "tool.FAILED",
        "req_id":   "<uuid>",
        "task_id":  "<uuid>",
        # optional extra fields per event:
        "plan":       [...],       # task.PLANNED
        "agent_id":   "...",       # agent.* / tool.*
        "agent_name": "...",       # agent.* / tool.*
        "tool_name":  "...",       # tool.*
        "tool_input": "...",       # tool.STARTED
        "result":     "...",       # agent.COMPLETED
        "response":   "...",       # task.COMPLETED
        "error":      "...",       # *.FAILED
    }

The backend passes these payloads straight through to the browser —
no translation, no in-memory state.
"""

import asyncio

from Redis.redis_connection import redis_subscribe
from services.ws_service import ws_broadcast

KERNEL_CHANNEL = "kernel_events"


async def handle_kernel_event(data: dict) -> None:
    """Receive one kernel event and push it to the right WS subscribers."""
    req_id = data.get("req_id", "")
    if req_id:
        await ws_broadcast(req_id, data)


async def start_kernel_listener() -> asyncio.Task:
    """Spawn the Redis subscriber as a background task and return it."""
    task = asyncio.create_task(
        redis_subscribe(KERNEL_CHANNEL, handle_kernel_event),
        name="kernel_listener",
    )
    return task
