"""Task controller — HTTP request handlers."""

from uuid import uuid4

from schemas.task import TaskRequest, TaskResponse
from Redis.redis_connection import redis_publish


async def create_task_handler(request: TaskRequest) -> TaskResponse:
    """Handle POST /task.

    1. Generate a unique req_id (transient WebSocket key).
    2. Publish task.REQUESTED to the kernel via Redis, including the
       optional task_id (empty string = new task, non-empty = follow-up).
    3. Return the req_id immediately — the client opens WS /ws/{req_id}.
    """
    req_id = str(uuid4())

    await redis_publish(
        "backend_tasks",
        {
            "event": "task.REQUESTED",
            "req_id": req_id,
            "prompt": request.prompt,
            "task_id": request.task_id or "",
        },
    )

    return TaskResponse(req_id=req_id, status="queued")
