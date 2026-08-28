"""Task repository — all MongoDB read/write operations for tasks."""

from datetime import datetime, timezone
from typing import Any

from DB.mongodb import tasks_collection


async def DB_create_task(task_id: str, prompt: str) -> None:
    """Insert a new task document keyed only by task_id."""
    now = datetime.now(timezone.utc)
    await tasks_collection.insert_one(
        {
            "task_id": task_id,
            "title": prompt[:80],  # first 80 chars as display title
            "status": "running",
            "messages": [],
            "plan": [],
            "current_agent": 0,
            "agents": {},
            "results": {},
            "response": None,
            "events": [],
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
    )


async def DB_add_task_message(task_id: str, role: str, content: str) -> None:
    """Append one message to the task's messages array."""
    await tasks_collection.update_one(
        {"task_id": task_id},
        {
            "$push": {
                "messages": {
                    "role": role,
                    "content": content,
                    "timestamp": datetime.now(timezone.utc),
                }
            }
        },
    )


async def DB_update_task(task_id: str, **values: Any) -> None:
    """Set arbitrary fields on a task document."""
    values["updated_at"] = datetime.now(timezone.utc)
    await tasks_collection.update_one(
        {"task_id": task_id},
        {"$set": values},
    )


async def DB_add_task_event(task_id: str, event: dict) -> None:
    """Append one event to the task's events array."""
    event["timestamp"] = datetime.now(timezone.utc)
    await tasks_collection.update_one(
        {"task_id": task_id},
        {"$push": {"events": event}},
    )


async def DB_get_task_messages(task_id: str) -> list[dict] | None:
    """Return the messages array for a task, or None if not found."""
    doc = await tasks_collection.find_one(
        {"task_id": task_id},
        {"messages": 1, "_id": 0},
    )
    if doc is None:
        return None
    return doc.get("messages", [])


async def DB_get_all_tasks() -> list[dict]:
    """Return all tasks ordered newest-first, with only summary fields."""
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
    return await cursor.to_list(length=200)


async def DB_get_task(task_id: str) -> dict | None:
    """Return a full task document by task_id."""
    return await tasks_collection.find_one(
        {"task_id": task_id},
        {"_id": 0},
    )
