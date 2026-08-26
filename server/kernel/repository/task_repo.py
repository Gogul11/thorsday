from datetime import datetime, timezone
from typing import Any

from DB.mongodb import tasks_collection


class TaskRepository:

    async def create(
        self,
        req_id: str,
        task_id: str,
        prompt: str,
    ):
        now = datetime.now(timezone.utc)

        await tasks_collection.insert_one({
            "req_id": req_id,
            "task_id": task_id,

            # "task": prompt,
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


    async def add_message(
        self,
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