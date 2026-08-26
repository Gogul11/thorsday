from datetime import datetime, timezone
from typing import Any

from DB.mongodb import tasks_collection


async def DB_create_task(
    req_id: str,
    task_id: str,
):
    now = datetime.now(timezone.utc)

    await tasks_collection.insert_one({
        "req_id": req_id,
        "task_id": task_id,

        "status": "created",

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
    })


async def DB_add_task_message(
    task_id: str,
    role: str,
    content: str,
):
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
        }
    )

async def DB_update_task(
    task_id: str,
    **values: Any
):
    values["updated_at"] = datetime.now(timezone.utc)

    await tasks_collection.update_one(
        {"task_id": task_id},
        {"$set": values}
    )

async def DB_add_task_event(
    task_id: str,
    event: dict,
):
    event["timestamp"] = datetime.now(timezone.utc)

    await tasks_collection.update_one(
        {"task_id": task_id},
        {
            "$push": {
                "events": event
            }
        }
    )

async def DB_get_task_messages(
    req_id : str
) -> list[dict[str,str]] | None:
    await tasks_collection.find_one(
        {"req_id" : req_id},
        {"messages" : 1}
    )
