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

    async def follow_up(self, task_id: UUID, request: TaskRequest) -> TaskResponse:
        try:
            self.service.follow_up(str(task_id), request.prompt)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found",
            ) from None
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task is still running",
            ) from None

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
            events=task["events"],
            messages=task["messages"],
        )
