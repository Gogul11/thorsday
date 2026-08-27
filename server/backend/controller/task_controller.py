"""Task controller — function-based request handlers.

Each function maps directly to one HTTP route. It validates input,
calls the service layer, and returns the appropriate Pydantic response model.
"""

from uuid import UUID, uuid4

from fastapi import HTTPException, status

from schemas.task import TaskRequest, TaskResponse, TaskStatusResponse
from svc.task_service import get_task_status, submit_task


async def create_task_handler(request: TaskRequest) -> TaskResponse:
    """Handle POST /task — publish a new task to the kernel."""
    req_id = str(uuid4())
    await submit_task(request.prompt, req_id)
    return TaskResponse(task_id=req_id, status="queued")


async def get_status_handler(task_id: UUID) -> TaskStatusResponse:
    """Handle GET /status/{task_id} — return current task state."""
    task = get_task_status(str(task_id))

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
