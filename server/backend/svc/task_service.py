import uuid

from Redis.redis_connection import RedisPubSub
from repo.task_repo import TaskRepository


class TaskService:
    def __init__(
        self,
        pubsub: RedisPubSub,
        repository: TaskRepository,
    ):
        self.pubsub = pubsub
        self.repository = repository

    async def submit(self, prompt: str, req_id: str) -> str:

        await self.pubsub.publish(
            "backend_tasks",
            {
                "event": "task.REQUESTED",
                "req_id": req_id,
                "prompt": prompt,
            }
        )

        return req_id

    def get(self, task_id: str):
        return self.repository.get(task_id)