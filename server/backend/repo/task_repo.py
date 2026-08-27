"""In-memory task repository — function-based interface.

Module-level store is a plain dict. Replace with a database-backed
implementation when persistence across restarts is needed.
"""

from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Module-level store
# ---------------------------------------------------------------------------
_tasks: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_task(task_id: str) -> None:
    """Initialise a new task record with status 'queued'."""
    _tasks[task_id] = {
        "status": "queued",
        "response": None,
        "error": None,
        "events": [],
    }
    add_task_event(
        task_id,
        stage="task",
        status="queued",
        message="Task accepted and waiting to start.",
    )


def get_task(task_id: str) -> dict[str, Any] | None:
    """Return the task record or *None* if it does not exist."""
    return _tasks.get(task_id)


def update_task(task_id: str, **values: Any) -> None:
    """Merge *values* into the task record.

    Raises KeyError if the task does not exist.
    """
    task = _tasks.get(task_id)
    if task is None:
        raise KeyError(f"Task not found: {task_id}")
    task.update(values)


def add_task_event(
    task_id: str,
    stage: str,
    status: str,
    message: str,
    agent_id: str | None = None,
) -> None:
    """Append a timeline event to the task's event list.

    Raises KeyError if the task does not exist.
    """
    task = _tasks.get(task_id)
    if task is None:
        raise KeyError(f"Task not found: {task_id}")

    task["events"].append(
        {
            "stage": stage,
            "status": status,
            "message": message,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
        }
    )
