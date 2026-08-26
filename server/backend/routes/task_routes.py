from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from controller.task_controller import TaskController
from schemas.task import (
    TaskRequest,
    TaskResponse,
    TaskStatusResponse,
)
from svc.redis_service import WebSocketManager


def create_task_router(controller: TaskController, ws_manager: WebSocketManager) -> APIRouter:
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

    @router.websocket("/ws/{req_id}")
    async def task_websocket(websocket: WebSocket, req_id: str) -> None:
        """
        WebSocket endpoint.  Connect with:
            ws://host/ws/<req_id>

        The server pushes a message every time a kernel event arrives for
        that req_id.  The client does not need to send anything.
        """
        await ws_manager.connect(req_id, websocket)
        try:
            # Keep the connection alive until the client disconnects.
            while True:
                # We only push, but we must await something so the loop
                # doesn't spin.  receive_text() will raise WebSocketDisconnect
                # when the browser closes the tab / navigates away.
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            ws_manager.disconnect(req_id, websocket)

    return router
