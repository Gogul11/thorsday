"""Task routes — REST and WebSocket endpoints.

POST /task              — submit a new task or follow-up, get back req_id
WS   /ws/{req_id}       — stream kernel events for that request in real time
GET  /tasks             — list all tasks (summary) for sidebar history
GET  /tasks/{task_id}   — full task detail including messages[]
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from controller.task_controller import create_task_handler
from schemas.task import TaskRequest, TaskResponse
from services.ws_service import ws_connect, ws_disconnect
from services.task_query_service import get_all_tasks, get_task_by_id

router = APIRouter()


# ---------------------------------------------------------------------------
# Task submission
# ---------------------------------------------------------------------------

@router.post(
    "/task",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a task or follow-up",
)
async def create_task(request: TaskRequest) -> TaskResponse:
    """
    Accepts a prompt (and optional task_id for follow-ups).
    Generates a unique req_id, publishes to the kernel via Redis,
    and returns the req_id immediately.
    Open WS /ws/{req_id} to receive live progress events.
    """
    return await create_task_handler(request)


# ---------------------------------------------------------------------------
# WebSocket live stream
# ---------------------------------------------------------------------------

@router.websocket("/ws/{req_id}")
async def task_websocket(websocket: WebSocket, req_id: str) -> None:
    """Stream kernel events for *req_id* to the connected client."""
    await ws_connect(req_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_disconnect(req_id, websocket)


# ---------------------------------------------------------------------------
# Task history (GPT-style sidebar)
# ---------------------------------------------------------------------------

@router.get(
    "/tasks",
    summary="List all tasks",
    description="Returns all tasks newest-first with summary fields for the sidebar.",
)
async def list_tasks() -> list[dict]:
    return await get_all_tasks()


@router.get(
    "/tasks/{task_id}",
    summary="Get a single task with full message history",
)
async def get_task(task_id: str) -> dict:
    task = await get_task_by_id(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
