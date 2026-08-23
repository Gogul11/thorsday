from uuid import UUID

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    prompt: str = Field(..., min_length=1)


class TaskResponse(BaseModel):
    task_id: UUID
    status: str


class TaskEventResponse(BaseModel):
    stage: str
    status: str
    message: str
    occurred_at: str
    agent_id: str | None = None


class TaskMessageResponse(BaseModel):
    role: str
    content: str
    occurred_at: str


class TaskStatusResponse(BaseModel):
    task_id: UUID
    status: str
    response: str | None = None
    error: str | None = None
    events: list[TaskEventResponse] = Field(default_factory=list)
    messages: list[TaskMessageResponse] = Field(default_factory=list)
