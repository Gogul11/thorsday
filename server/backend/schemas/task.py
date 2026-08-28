"""Request/response schemas for the task API."""

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """Body for POST /task."""
    prompt: str = Field(..., min_length=1, description="The user's task prompt")


class TaskResponse(BaseModel):
    """Immediate response from POST /task."""
    req_id: str = Field(..., description="Unique request ID — use this to open the WebSocket")
    status: str = Field(default="queued", description="Always 'queued' on creation")


class KernelEvent(BaseModel):
    """Shape of messages pushed over the WebSocket.

    Mirrors what the kernel publishes to 'kernel_events'. Extra fields
    (plan, agent_id, result, response, error, etc.) are passed through as-is.
    """
    event: str
    req_id: str
    task_id: str
