import asyncio
from uuid import uuid4

from Agents.main_agent import Main_Agent
from logger import logger

from backend.repo.task_repo import TaskRepository


class TaskService:
    def __init__(self, agent: Main_Agent, repository: TaskRepository):
        self.agent = agent
        self.repository = repository

    def submit(self, prompt: str) -> str:
        task_id = str(uuid4())
        self.repository.create(task_id)
        asyncio.create_task(self._run(task_id, prompt))
        return task_id

    async def _run(self, task_id: str, prompt: str) -> None:
        self.repository.update(task_id, status="running")

        try:
            response = await self.agent.chat(prompt)
            self.repository.update(
                task_id,
                status="completed",
                response=response,
            )
            logger.info("Task completed: %s", task_id)
        except Exception as exc:
            self.repository.update(
                task_id,
                status="failed",
                error=str(exc),
            )
            logger.exception("Task failed: %s", task_id)

    def get(self, task_id: str) -> dict | None:
        return self.repository.get(task_id)
