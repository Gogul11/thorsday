"""Task routes — REST + WebSocket endpoints.

Routes delegate directly to controller functions and the ws module-level
helpers; no class instances are passed around.
"""

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from controller.task_controller import create_task_handler, get_status_handler
from schemas.task import TaskRequest, TaskResponse, TaskStatusResponse
from svc.redis_service import ws_connect, ws_disconnect

router = APIRouter()


@router.post(
    "/task",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_task(request: TaskRequest) -> TaskResponse:
    """Accept a new task and dispatch it to the kernel."""
    return await create_task_handler(request)


@router.get(
    "/status/{task_id}",
    response_model=TaskStatusResponse,
)
async def get_task_status(task_id: UUID) -> TaskStatusResponse:
    """Return current state and event timeline for a task."""
    return await get_status_handler(task_id)


@router.websocket("/ws/{req_id}")
async def task_websocket(websocket: WebSocket, req_id: str) -> None:
    """Stream kernel events for *req_id* to the connected browser.

    Connect with:  ws://host/ws/<req_id>

    The server pushes a message for every kernel event. The client does
    not need to send anything; the connection stays open until the client
    disconnects.
    """
    await ws_connect(req_id, websocket)
    try:
        while True:
            # recv keeps the connection alive; raises WebSocketDisconnect on close
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_disconnect(req_id, websocket)
