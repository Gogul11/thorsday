"""Request/response schemas for the task API."""

from typing import Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Body for POST /task.

    For new tasks, omit task_id (or pass "").
    For follow-ups on an existing task, pass the task_id returned by the
    kernel's task.CREATED event — the kernel will continue the same conversation.
    """

    prompt: str = Field(..., min_length=1, description="The user's task prompt")
    task_id: Optional[str] = Field(
        default="",
        description="Existing task_id for follow-up messages. Empty for new tasks.",
    )


class TaskResponse(BaseModel):
    """Immediate response from POST /task."""

    req_id: str = Field(
        ..., description="Unique request ID — use this to open the WebSocket"
    )
    status: str = Field(default="queued")


class TaskSummary(BaseModel):
    """One row in the GET /tasks list."""

    task_id: str
    title: str
    status: str
    plan: list[str] = []
    response: Optional[str] = None
    created_at: str


class KernelEvent(BaseModel):
    """Shape of messages pushed over the WebSocket."""

    event: str
    req_id: str
    task_id: str
