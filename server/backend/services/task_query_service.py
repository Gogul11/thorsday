"""Task query service — read-only MongoDB helpers for the backend.

The kernel owns all writes. The backend only reads here.
"""

from DB.mongodb import tasks_collection


async def get_all_tasks() -> list[dict]:
    """Return all tasks newest-first with summary fields."""
    cursor = tasks_collection.find(
        {},
        {
            "_id": 0,
            "task_id": 1,
            "title": 1,
            "status": 1,
            "plan": 1,
            "response": 1,
            "created_at": 1,
        },
    ).sort("created_at", -1)

    tasks = await cursor.to_list(length=200)

    # Serialize datetime objects to ISO strings for JSON
    for task in tasks:
        if "created_at" in task and hasattr(task["created_at"], "isoformat"):
            task["created_at"] = task["created_at"].isoformat()

    return tasks


async def get_task_by_id(task_id: str) -> dict | None:
    """Return a full task document including messages[], or None if not found."""
    task = await tasks_collection.find_one(
        {"task_id": task_id},
        {"_id": 0},
    )

    if task is None:
        return None

    # Serialize datetime objects
    for key in ("created_at", "updated_at", "completed_at"):
        if key in task and task[key] is not None and hasattr(task[key], "isoformat"):
            task[key] = task[key].isoformat()

    # Serialize timestamps inside messages[]
    for msg in task.get("messages", []):
        if "timestamp" in msg and hasattr(msg["timestamp"], "isoformat"):
            msg["timestamp"] = msg["timestamp"].isoformat()

    # Serialize timestamps inside events[]
    for ev in task.get("events", []):
        if "timestamp" in ev and hasattr(ev["timestamp"], "isoformat"):
            ev["timestamp"] = ev["timestamp"].isoformat()

    return task
