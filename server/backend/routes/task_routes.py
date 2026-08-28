"""Task routes — REST and WebSocket endpoints.

POST /task        — submit a new task, get back req_id
WS   /ws/{req_id} — stream kernel events for that task in real time
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from controller.task_controller import create_task_handler
from schemas.task import TaskRequest, TaskResponse
from services.ws_service import ws_connect, ws_disconnect

router = APIRouter()


@router.post(
    "/task",
    response_model=TaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a task",
    description=(
        "Accepts a prompt, generates a unique req_id, publishes the task to the "
        "kernel via Redis, and returns the req_id immediately. "
        "Open WS /ws/{req_id} to receive live progress events."
    ),
)
async def create_task(request: TaskRequest) -> TaskResponse:
    return await create_task_handler(request)


@router.websocket("/ws/{req_id}")
async def task_websocket(websocket: WebSocket, req_id: str) -> None:
    """Stream kernel events for *req_id* to the connected client.

    The server pushes one JSON message per kernel event. The client does
    not need to send anything; just keep the connection open.

    Disconnect (close the tab / call ws.close()) to stop receiving events.
    """
    await ws_connect(req_id, websocket)
    try:
        while True:
            # Keep the connection alive; raises WebSocketDisconnect on close.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_disconnect(req_id, websocket)
