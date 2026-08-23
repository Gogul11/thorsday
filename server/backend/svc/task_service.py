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
        self._agents: dict[str, Main_Agent] = {}

    def submit(self, prompt: str) -> str:
        task_id = str(uuid4())
        self.repository.create(task_id, prompt)
        asyncio.create_task(self._run(task_id, prompt))
        return task_id

    def follow_up(self, task_id: str, prompt: str) -> None:
        task = self.repository.get(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if task["status"] in {"queued", "running"}:
            raise ValueError("Task is still running")

        self.repository.update(
            task_id,
            status="queued",
            response=None,
            error=None,
        )
        self.repository.add_message(task_id, role="user", content=prompt)
        self.repository.add_event(
            task_id,
            stage="task",
            status="queued",
            message="Follow-up accepted and waiting to start.",
        )
        asyncio.create_task(self._run(task_id, prompt))

    async def _run(self, task_id: str, prompt: str) -> None:
        self.repository.update(task_id, status="running")
        self.repository.add_event(
            task_id,
            stage="task",
            status="running",
            message="Task execution started.",
        )

        try:
            agent = self._agents.get(task_id)
            if agent is None:
                agent = self.agent_factory()
                self._agents[task_id] = agent
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
            self.repository.add_message(task_id, role="assistant", content=response)
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
