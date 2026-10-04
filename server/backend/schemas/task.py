"""
Request/response schemas for the task API.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Body for POST /task."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="The user's task prompt",
    )

    task_id: Optional[str] = Field(
        default="",
        description=(
            "Existing task_id for follow-up messages. "
            "Empty for new tasks."
        ),
    )


class TaskResponse(BaseModel):
    """Immediate response from POST /task."""

    req_id: str = Field(
        ...,
        description="Unique request ID — use it to open the WebSocket",
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

    plan: Optional[list[str]] = None

    agent_id: Optional[str] = None
    agent_name: Optional[str] = None

    tool_name: Optional[str] = None
    tool_input: Optional[str] = None

    result: Optional[str] = None
    response: Optional[str] = None
    error: Optional[str] = None

    # Global scheduler metadata
    step_id: Optional[str] = None
    execution_id: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[float] = None
    effective_priority: Optional[float] = None
    queue_wait_ms: Optional[int] = None
    queue_position: Optional[int] = None
    attempt: Optional[int] = None
    reason: Optional[str] = None
    scheduler_metrics: Optional[dict] = None
    token_usage: Optional[dict] = None

    # Delete confirmation fields
    confirmation_id: Optional[str] = None
    path: Optional[str] = None
    recursive: Optional[bool] = None


class DeleteConfirmationRequest(BaseModel):
    """User's response to a pending delete confirmation."""

    req_id: str
    task_id: str
    confirmation_id: str
    confirmed: bool

class DeleteConfirmationResponse(BaseModel):
    success: bool
    status: str
    message: str
    path: Optional[str] = None
