from uuid import UUID

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    task_id: UUID
    status: str


class TaskStatusResponse(BaseModel):
    task_id: UUID
    status: str
    response: str | None = None
    error: str | None = None
