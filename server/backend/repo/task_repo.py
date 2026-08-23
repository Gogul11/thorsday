from typing import Any


class TaskRepository:
    """In-memory task-state repository.

    Replace this class with a database-backed implementation when persistence
    across process restarts is required.
    """

    def __init__(self):
        self._tasks: dict[str, dict[str, Any]] = {}

    def create(self, task_id: str) -> None:
        self._tasks[task_id] = {
            "status": "queued",
            "response": None,
            "error": None,
        }

    def get(self, task_id: str) -> dict[str, Any] | None:
        return self._tasks.get(task_id)

    def update(self, task_id: str, **values: Any) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        task.update(values)
