"""Dispatcher — Redis message handler for the 'backend_tasks' channel.

Receives raw messages from the backend and routes them to the appropriate
handler. Currently handles only task.REQUESTED; new event types can be
added here as the system grows without touching main.py.

The dispatcher is the only module that knows about:
  - which Redis events exist
  - how to extract fields from those events
  - how to call run_task and what to publish on failure
"""

from logger import logger
from Redis.redis_connection import publish
from services.task_runner import run_task


async def handle_backend_task(data: dict) -> None:
    """Process one message received from the 'backend_tasks' Redis channel.

    Expected message shape
    ----------------------
    {
        "event":   "task.REQUESTED",
        "req_id":  "<uuid>",          # transient WS key
        "prompt":  "<user text>",
        "task_id": "<uuid> or empty",  # empty = new task, non-empty = follow-up
    }

    On success the graph publishes kernel_events directly (task.CREATED,
    task.PLANNED, task.COMPLETED, …). On failure an agent.FAILED event is
    published here so the frontend always receives a terminal event.
    """
    event = data.get("event")
    req_id = data.get("req_id", "")

    logger.info("Dispatcher received | event=%s req_id=%s", event, req_id)

    if event != "task.REQUESTED":
        logger.debug("Dispatcher: ignoring unknown event '%s'", event)
        return

    prompt = data.get("prompt", "")
    task_id = data.get("task_id", "")  # "" for new tasks, set for follow-ups

    try:
        await run_task(prompt=prompt, req_id=req_id, task_id=task_id)
    except Exception as exc:
        logger.exception("Dispatcher: task %s failed — %s", req_id, exc)
        await publish(
            "kernel_events",
            {
                "event": "agent.FAILED",
                "req_id": req_id,
                "task_id": task_id,
                "error": str(exc),
            },
        )
