from uuid import UUID

from fastapi import APIRouter, status

from backend.controller.task_controller import TaskController
from backend.schemas.task import (
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
)


def create_task_router(controller: TaskController) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/task",
        response_model=TaskResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_task(request: TaskRequest) -> TaskResponse:
        return await controller.create_task(request)

    @router.get(
        "/status/{task_id}",
        response_model=TaskStatusResponse,
    )
    async def get_task_status(task_id: UUID) -> TaskStatusResponse:
        return await controller.get_status(task_id)

    return router
