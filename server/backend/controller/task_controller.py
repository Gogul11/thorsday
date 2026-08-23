from uuid import UUID

from fastapi import HTTPException, status

from backend.schemas.task import (
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
)
from backend.svc.task_service import TaskService


class TaskController:
    def __init__(self, service: TaskService):
        self.service = service

    async def create_task(self, request: TaskRequest) -> TaskResponse:
        task_id = self.service.submit(request.prompt)
        return TaskResponse(task_id=task_id, status="queued")

    async def get_status(self, task_id: UUID) -> TaskStatusResponse:
        task = self.service.get(str(task_id))

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            )

        return TaskStatusResponse(
            task_id=task_id,
            status=task["status"],
            response=task["response"],
            error=task["error"],
        )
