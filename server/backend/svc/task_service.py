import asyncio
from collections.abc import Callable
from uuid import uuid4

from Agents.main_agent import Main_Agent
from logger import logger

from backend.repo.task_repo import TaskRepository


class TaskService:
    def __init__(
        self,
        agent_factory: Callable[[], Main_Agent],
        repository: TaskRepository,
    ):
        self.agent_factory = agent_factory
        self.repository = repository

    def submit(self, prompt: str) -> str:
        task_id = str(uuid4())
        self.repository.create(task_id)
        asyncio.create_task(self._run(task_id, prompt))
        return task_id

    async def _run(self, task_id: str, prompt: str) -> None:
        self.repository.update(task_id, status="running")
        self.repository.add_event(
            task_id,
            stage="task",
            status="running",
            message="Task execution started.",
        )

        try:
            agent = self.agent_factory()
            response = await agent.chat(
                prompt,
                task_id=task_id,
                event_callback=lambda stage, event_status, message, agent_id=None:
                    self.repository.add_event(
                        task_id,
                        stage=stage,
                        status=event_status,
                        message=message,
                        agent_id=agent_id,
                    ),
            )
            self.repository.update(
                task_id,
                status="completed",
                response=response,
            )
            self.repository.add_event(
                task_id,
                stage="task",
                status="completed",
                message="Task completed successfully.",
            )
            logger.info("Task completed: %s", task_id)
        except Exception as exc:
            self.repository.update(
                task_id,
                status="failed",
                error=str(exc),
            )
            self.repository.add_event(
                task_id,
                stage="task",
                status="failed",
                message="Task execution failed.",
            )
            logger.exception("Task failed: %s", task_id)

    def get(self, task_id: str) -> dict | None:
        return self.repository.get(task_id)
