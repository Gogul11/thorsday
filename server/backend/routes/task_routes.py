"""
Task routes — REST and WebSocket endpoints.

POST /task
    Submit a new task or follow-up.

POST /delete-confirmation
    Confirm or cancel a pending destructive filesystem operation.

WS /ws/{req_id}
    Stream kernel events for that request.

GET /tasks
    List task history.

GET /tasks/{task_id}
    Get full task details.
"""

from fastapi import (
    APIRouter,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from controller.task_controller import (
    confirm_delete_handler,
    create_task_handler,
)

from schemas.task import (
    DeleteConfirmationRequest,
    DeleteConfirmationResponse,
    TaskRequest,
    TaskResponse,
)

from services.task_query_service import (
    get_all_tasks,
    get_task_by_id,
)

from services.ws_service import (
    ws_connect,
    ws_disconnect,
)


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
async def create_task(
    request: TaskRequest,
) -> TaskResponse:
    """
    Accept a prompt and submit it to the kernel.
    """

    return await create_task_handler(request)


# ---------------------------------------------------------------------------
# Delete confirmation
# ---------------------------------------------------------------------------


@router.post(
    "/delete-confirmation",
    response_model=DeleteConfirmationResponse,
    summary="Confirm or cancel a pending delete operation",
)
async def confirm_delete(
    request: DeleteConfirmationRequest,
) -> DeleteConfirmationResponse:
    """
    Process the user's Delete/Cancel decision.

    The frontend sends:
        req_id
        task_id
        confirmation_id
        confirmed

    The frontend does NOT send the filesystem path.

    The backend retrieves the pending confirmation and performs
    the appropriate action through confirm_delete_handler().
    """

    return await confirm_delete_handler(request)


# ---------------------------------------------------------------------------
# WebSocket live stream
# ---------------------------------------------------------------------------


@router.websocket("/ws/{req_id}")
async def task_websocket(
    websocket: WebSocket,
    req_id: str,
) -> None:
    """
    Stream kernel events for req_id.
    """

    await ws_connect(
        req_id,
        websocket,
    )

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass

    finally:
        ws_disconnect(
            req_id,
            websocket,
        )


# ---------------------------------------------------------------------------
# Task history
# ---------------------------------------------------------------------------


@router.get(
    "/tasks",
    summary="List all tasks",
    description=(
        "Returns all tasks newest-first with summary fields "
        "for the sidebar."
    ),
)
async def list_tasks() -> list[dict]:
    return await get_all_tasks()


@router.get(
    "/tasks/{task_id}",
    summary="Get a single task with full message history",
)
async def get_task(
    task_id: str,
) -> dict:
    task = await get_task_by_id(task_id)

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task