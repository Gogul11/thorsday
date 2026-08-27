"""WebSocket manager and kernel-event handler — function-based interface.

WebSocket connections are stored in a module-level dict keyed by req_id.
The kernel event handler is wired to the repo and ws layer directly.
"""

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket

from Redis.redis_connection import redis_close, redis_subscribe
from repo.task_repo import add_task_event, create_task, get_task, update_task

# ---------------------------------------------------------------------------
# Module-level WebSocket store
# ---------------------------------------------------------------------------
# req_id -> list of active WebSocket connections
_connections: dict[str, list[WebSocket]] = {}


# ---------------------------------------------------------------------------
# WebSocket connection management
# ---------------------------------------------------------------------------

async def ws_connect(req_id: str, websocket: WebSocket) -> None:
    """Accept the WebSocket and register it under *req_id*."""
    await websocket.accept()
    _connections.setdefault(req_id, []).append(websocket)


def ws_disconnect(req_id: str, websocket: WebSocket) -> None:
    """Remove *websocket* from the registry for *req_id*."""
    connections = _connections.get(req_id, [])
    if websocket in connections:
        connections.remove(websocket)
    if not connections:
        _connections.pop(req_id, None)


async def ws_broadcast(req_id: str, data: dict) -> None:
    """Send a JSON message to every subscriber of *req_id*."""
    connections = list(_connections.get(req_id, []))
    dead: list[WebSocket] = []
    for ws in connections:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.append(ws)
    for ws in dead:
        ws_disconnect(req_id, ws)


# ---------------------------------------------------------------------------
# Kernel-event translation
# ---------------------------------------------------------------------------

_STAGE_MAP: dict[str, tuple[str, str]] = {
    "task.CREATED": ("task", "created"),
    "task.PLANNING": ("task", "planning"),
    "task.PLANNED": ("task", "planned"),
    "task.COMPLETED": ("task", "completed"),
    "agent.STARTED": ("agent", "started"),
    "agent.COMPLETED": ("agent", "completed"),
    "agent.FAILED": ("agent", "failed"),
    "agent.DESTROYED": ("agent", "destroyed"),
    "tool.STARTED": ("tool", "started"),
    "tool.COMPLETED": ("tool", "completed"),
    "tool.FAILED": ("tool", "failed"),
}


def build_event_from_kernel(data: dict) -> dict:
    """Translate a raw kernel event dict into the repo event schema."""
    event = data["event"]
    stage, status = _STAGE_MAP.get(event, ("task", event.lower()))

    agent_name = data.get("agent_name") or data.get("agent_id")
    tool_name = data.get("tool_name", "tool")

    messages: dict[str, str] = {
        "task.CREATED": "Task created.",
        "task.PLANNING": "Planning execution steps…",
        "task.PLANNED": f"Plan ready: {data.get('plan') or []}",
        "task.COMPLETED": "Task completed.",
        "agent.STARTED": f"Agent {agent_name or ''} started.",
        "agent.COMPLETED": f"Agent {agent_name or ''} completed.",
        "agent.FAILED": f"Agent {agent_name or ''} failed: {data.get('error', '')}",
        "agent.DESTROYED": f"Agent {agent_name or ''} destroyed.",
        "tool.STARTED": f"Tool started: {tool_name}",
        "tool.COMPLETED": f"Tool completed: {tool_name}",
        "tool.FAILED": f"Tool {tool_name} failed: {data.get('error', '')}",
    }

    return {
        "stage": stage,
        "status": status,
        "message": messages.get(event, event),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_name,
    }


# ---------------------------------------------------------------------------
# Kernel-event handler
# ---------------------------------------------------------------------------

async def handle_kernel_event(data: dict) -> None:
    """Process a single kernel event: persist state and broadcast to WS."""
    event = data.get("event", "")
    req_id = data.get("req_id", "")
    task_id = data.get("task_id", req_id)

    # 1. Persist state ---------------------------------------------------
    if event == "task.CREATED":
        if get_task(task_id) is None:
            create_task(task_id)

    if get_task(task_id) is not None:
        ev = build_event_from_kernel(data)
        add_task_event(
            task_id,
            stage=ev["stage"],
            status=ev["status"],
            message=ev["message"],
            agent_id=ev.get("agent_id"),
        )

        if event == "task.COMPLETED":
            update_task(task_id, status="completed", response=data.get("response"))
        elif event == "agent.FAILED":
            update_task(task_id, status="failed", error=data.get("error"))
        elif event == "task.PLANNING":
            update_task(task_id, status="running")

    # 2. Build WebSocket payload ------------------------------------------
    task_state = get_task(task_id)
    ws_payload = {
        "event": event,
        "req_id": req_id,
        "task_id": task_id,
        "latest_event": build_event_from_kernel(data),
        "status": task_state["status"] if task_state else None,
        "response": task_state["response"] if task_state else None,
        "error": task_state["error"] if task_state else None,
    }

    # 3. Broadcast -------------------------------------------------------
    await ws_broadcast(req_id, ws_payload)


# ---------------------------------------------------------------------------
# App lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start Redis subscriber on startup; cancel it and close on shutdown."""
    subscriber_task = asyncio.create_task(
        redis_subscribe("kernel_events", handle_kernel_event)
    )

    yield

    subscriber_task.cancel()
    await redis_close()
