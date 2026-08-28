"""Task controller — HTTP request handlers.

Keeps HTTP concerns (request parsing, response shaping) separated from
the service layer (Redis publish).
"""

from uuid import uuid4

from schemas.task import TaskRequest, TaskResponse
from Redis.redis_connection import redis_publish


async def create_task_handler(request: TaskRequest) -> TaskResponse:
    """Handle POST /task.

    1. Generate a unique req_id.
    2. Publish a task.REQUESTED event to the kernel via Redis.
    3. Return the req_id immediately — the client opens WS /ws/{req_id}
       to receive live progress from the kernel.
    """
    req_id = str(uuid4())

    await redis_publish(
        "backend_tasks",
        {
            "event": "task.REQUESTED",
            "req_id": req_id,
            "prompt": request.prompt,
        },
    )

    return TaskResponse(req_id=req_id, status="queued")
