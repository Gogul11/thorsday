from contextlib import asynccontextmanager
import asyncio
import json
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from Redis.redis_connection import RedisPubSub
from repo.task_repo import TaskRepository


class WebSocketManager:
    """Holds active WebSocket connections keyed by req_id (== task_id).

    Multiple browser tabs can subscribe to the same task simultaneously.
    """

    def __init__(self):
        # req_id -> list of connected WebSocket objects
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, req_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(req_id, []).append(websocket)

    def disconnect(self, req_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(req_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(req_id, None)

    async def broadcast(self, req_id: str, data: dict) -> None:
        """Send a JSON message to every subscriber of req_id."""
        connections = list(self._connections.get(req_id, []))
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(req_id, ws)


def build_event_from_kernel(data: dict) -> dict:
    """Translate a kernel event dict into the TaskRepository event schema."""
    event = data["event"]

    stage_map = {
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

    stage, status = stage_map.get(event, ("task", event.lower()))
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


def create_handle_kernel_event(
    repository: TaskRepository,
    ws_manager: WebSocketManager,
):
    """Factory that closes over the repository and WebSocket manager."""

    async def handle_kernel_event(data: dict):
        event = data.get("event", "")
        req_id = data.get("req_id", "")
        task_id = data.get("task_id", req_id)

        # ── 1. Persist state ────────────────────────────────────────────────
        if event == "task.CREATED":
            # Only create if not already present (idempotent)
            if repository.get(task_id) is None:
                repository.create(task_id)

        if repository.get(task_id) is not None:
            ev = build_event_from_kernel(data)
            repository.add_event(
                task_id,
                stage=ev["stage"],
                status=ev["status"],
                message=ev["message"],
                agent_id=ev.get("agent_id"),
            )

            if event == "task.COMPLETED":
                repository.update(
                    task_id,
                    status="completed",
                    response=data.get("response"),
                )
            elif event == "agent.FAILED":
                repository.update(
                    task_id,
                    status="failed",
                    error=data.get("error"),
                )
            elif event == "task.PLANNING":
                repository.update(task_id, status="running")

        # ── 2. Build WS payload ─────────────────────────────────────────────
        task_state = repository.get(task_id)
        ws_payload = {
            "event": event,
            "req_id": req_id,
            "task_id": task_id,
            # Include the freshly added event so the frontend can append it
            # without a round-trip
            "latest_event": build_event_from_kernel(data),
            # Also send the updated top-level fields
            "status": task_state["status"] if task_state else None,
            "response": task_state["response"] if task_state else None,
            "error": task_state["error"] if task_state else None,
        }

        # ── 3. Broadcast ────────────────────────────────────────────────────
        # The kernel uses req_id as the correlation id; broadcast on that.
        await ws_manager.broadcast(req_id, ws_payload)

    return handle_kernel_event


def create_lifespan(
    redis_client: RedisPubSub, repository: TaskRepository, ws_manager: WebSocketManager
):

    @asynccontextmanager
    async def lifespan(app: FastAPI):

        handler = create_handle_kernel_event(repository, ws_manager)

        subscriber_task = asyncio.create_task(
            redis_client.subscribe(
                "kernel_events",
                handler,
            )
        )

        yield

        subscriber_task.cancel()
        await redis_client.close()

    return lifespan
