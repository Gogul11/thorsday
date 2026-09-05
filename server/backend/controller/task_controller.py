"""
Task controller — HTTP request handlers.
"""

from uuid import uuid4

from schemas.task import (
    DeleteConfirmationRequest,
    DeleteConfirmationResponse,
    TaskRequest,
    TaskResponse,
)

from Redis.redis_connection import redis_publish

from services.delete_confirmation_service import (
    cancel_delete,
    confirm_delete,
)


async def create_task_handler(
    request: TaskRequest,
) -> TaskResponse:
    """
    Handle POST /task.

    1. Generate a unique req_id.
    2. Publish task.REQUESTED to the kernel.
    3. Return req_id immediately.
    """

    req_id = str(uuid4())

    await redis_publish(
        "backend_tasks",
        {
            "event": "task.REQUESTED",
            "req_id": req_id,
            "prompt": request.prompt,
            "task_id": request.task_id or "",
        },
    )

    return TaskResponse(
        req_id=req_id,
        status="queued",
    )


async def confirm_delete_handler(
    request: DeleteConfirmationRequest,
) -> DeleteConfirmationResponse:
    """
    Handle the user's Delete/Cancel decision.

    The browser never supplies the filesystem path.

    If confirmed=True:
        backend validates the pending confirmation and performs deletion.

    If confirmed=False:
        backend cancels the pending operation.
    """

    if request.confirmed:
        result = await confirm_delete(
            confirmation_id=request.confirmation_id,
            req_id=request.req_id,
            task_id=request.task_id,
        )
    else:
        result = await cancel_delete(
            confirmation_id=request.confirmation_id,
            req_id=request.req_id,
            task_id=request.task_id,
        )

    # Tell the kernel/A4 process that the user's decision is available.
    #
    # The A4 process is waiting on the same Redis confirmation record.
    event_name = (
        "DELETE_COMPLETED"
        if result["success"] and request.confirmed
        else "DELETE_CANCELLED"
        if result["success"] and not request.confirmed
        else "DELETE_FAILED"
    )

    await redis_publish(
        "kernel_events",
        {
            "event": event_name,
            "req_id": request.req_id,
            "task_id": request.task_id,
            "confirmation_id": request.confirmation_id,
            "path": result.get("path"),
            "result": result["message"],
            "error": (
                None
                if result["success"]
                else result["message"]
            ),
        },
    )

    return DeleteConfirmationResponse(
        success=result["success"],
        status=result["status"],
        message=result["message"],
        path=result.get("path"),
    )