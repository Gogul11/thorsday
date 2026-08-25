from uuid import UUID, uuid4

from fastapi import HTTPException, status

from schemas.task import (
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
)
from svc.task_service import TaskService


class TaskController:
    def __init__(self, service: TaskService):
        self.service = service

    async def create_task(self, request: TaskRequest) -> TaskResponse:
        req_id = str(uuid4())
    
        await self.service.submit(
            request.prompt,
            req_id
        )
    
        return TaskResponse(
            task_id=req_id,
            status="queued"
        )

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
        )
