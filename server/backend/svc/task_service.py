"""Task service — function-based interface.

Orchestrates publishing a task to the kernel via Redis and reading task
state from the in-memory repository.
"""

from Redis.redis_connection import redis_publish
from repo.task_repo import get_task


async def submit_task(prompt: str, req_id: str) -> str:
    """Publish a task.REQUESTED event to the kernel and return *req_id*.

    The kernel picks up the event from the 'backend_tasks' channel and
    starts processing. It will publish progress events back on
    'kernel_events', which the redis_service subscriber handles.
    """
    await redis_publish(
        "backend_tasks",
        {
            "event": "task.REQUESTED",
            "req_id": req_id,
            "prompt": prompt,
        },
    )
    return req_id


def get_task_status(task_id: str):
    """Return the current task record, or *None* if not found."""
    return get_task(task_id)
